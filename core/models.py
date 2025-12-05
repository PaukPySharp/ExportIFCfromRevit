# -*- coding: utf-8 -*-
"""Модель RevitModel: пути, метаданные и правила экспорта IFC.

Назначение:
    - Представлять одну Revit-модель (.rvt) в процессе экспорта IFC:
        * путь к файлу;
        * время последней модификации (нормализованное до минут);
        * целевые директории для IFC (mapped / nomap);
        * файлы конфигураций маппинга;
        * лениво определяемую версию Revit и build.

Контракты:
    - Все пути, переданные в конструктор, в __post_init__ нормализуются
      через resolve_if_exists:
        * для существующих путей приводятся к абсолютному виду
          (Path.resolve());
        * для несуществующих путей остаются без изменений;
        * None не трогаем.
    - Сравнение актуальности выполняется через:
        * HistoryLike.is_up_to_date(self)   — история экспорта;
        * IFCCheckerLike.is_ifc_up_to_date* — наличие/свежесть IFC на диске.
    - После вызова needs_export():
        * если по какому-то направлению (mapped/nomap) IFC актуален,
          соответствующий output_dir_* обнуляется (None), чтобы не попадать
          в <TMP_NAME>.csv и не инициировать лишний экспорт.

Особенности:
    - На этапе загрузки из <MANAGE_NAME>.xlsx поле output_dir_mapping всегда
      задано (строки без него игнорируются), но в процессе работы объекта
      может стать None после needs_export().
    - Версия Revit и build извлекаются лениво методом load_version()
      через RevitVersionInfo.
    - FLAG_UNMAPPED управляет сценарием «без маппинга».
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Protocol
from dataclasses import dataclass, field

from config import FLAG_UNMAPPED

from utils.fs import resolve_if_exists
from revit.versions import RevitVersionInfo


# ----------------------------- протоколы -----------------------------
class HistoryLike(Protocol):
    """Минимальный протокол для менеджера истории.

    Ожидается реализация метода:
        - is_up_to_date(model: RevitModel) -> bool
    """

    def is_up_to_date(self, model: "RevitModel") -> bool:
        """Проверяет, актуальна ли запись истории для указанной модели.

        :param model: Модель Revit, для которой нужно проверить историю.
        :return: True, если по данным истории модель не требует
                 повторного экспорта.
        """
        ...


class IFCCheckerLike(Protocol):
    """Минимальный протокол для проверки актуальности IFC на диске.

    Ожидается реализация методов:
        - is_ifc_up_to_date_mapping(model) -> bool
        - is_ifc_up_to_date_nomap(model)   -> bool
    """

    def is_ifc_up_to_date_mapping(self, model: "RevitModel") -> bool:
        """Проверяет, актуален ли IFC-файл для режима с маппингом.

        :param model: Модель Revit, для которой проверяется экспорт
                      с маппингом.
        :return: True, если соответствующий IFC-файл существует и
                 считается не старее исходной модели.
        """
        ...

    def is_ifc_up_to_date_nomap(self, model: "RevitModel") -> bool:
        """Проверяет, актуален ли IFC-файл для режима без маппинга.

        :param model: Модель Revit, для которой проверяется экспорт
                      без маппинга.
        :return: True, если соответствующий IFC-файл существует и
                 считается не старее исходной модели.
        """
        ...


# -------------------------- решение об экспорте --------------------------
@dataclass(slots=True)
class ExportDecision:
    """Результат проверки необходимости экспорта для модели.

    Назначение:
        - Хранит флаги актуальности истории и IFC по двум направлениям.
        - Даёт удобный доступ к тому, нужно ли что-то выгружать.

    Состояние:
        - history_ok   — True, если запись в <HISTORY_NAME>.xlsx актуальна;
        - ifc_map_ok   — True, если mapped-IFC считается актуальным;
        - ifc_nomap_ok — True, если nomap-IFC не нужен или актуален.
    """

    history_ok: bool
    ifc_map_ok: bool
    ifc_nomap_ok: bool

    @property
    def need_mapped(self) -> bool:
        """Возвращает признак необходимости экспорта с маппингом.

        :return:
            True — требуется экспорт по направлению с маппингом;
            False — экспорт по направлению с маппингом не требуется.
        """
        return not self.ifc_map_ok

    @property
    def need_nomap(self) -> bool:
        """Возвращает признак необходимости экспорта без маппинга.

        :return:
            True — требуется экспорт по направлению без маппинга;
            False — экспорт по направлению без маппинга не требуется.
        """
        return not self.ifc_nomap_ok

    @property
    def needs_any_export(self) -> bool:
        """Возвращает признак необходимости любого экспорта для модели.

        :return:
            True — требуется экспорт хотя бы по одному направлению;
            False — экспорт не требуется (история и оба IFC актуальны).
        """
        return not (self.history_ok and self.ifc_map_ok and self.ifc_nomap_ok)


@dataclass(slots=True)
class RevitModel:
    """
    Представление файла Revit и связанных с ним путей/настроек
    для экспорта IFC.

    Состояние:
        - rvt_path        — абсолютный путь к .rvt (resolve в __post_init__);
        - last_modified   — дата модификации RVT (нормализована до минут);
        - output_dir_mapping / output_dir_nomap — директории для IFC:
            * при создании из ManageDataLoader output_dir_mapping всегда задан;
            * после вызова needs_export() соответствующие поля могут быть
              обнулены (None), если по ним экспорт не требуется;
        - mapping_json / nomap_json / family_mapping_file — конфиги экспорта;
        - version         — год версии Revit (лениво вычисляется, либо None);
        - build           — строка build сборки Revit (если удалось извлечь).

    Правила:
        - Конфиги (папки, файлы JSON/txt) формирует DataLoader
          (<MANAGE_NAME>.xlsx), RevitModel только хранит и нормализует пути.
        - Нужность экспорта определяется связкой:
            * history.is_up_to_date(self),
            * IFCChecker.is_ifc_up_to_date_*.
        - После успешной проверки актуальности по направлению (mapped/nomap)
          соответствующие output_dir_* могут быть сброшены в None методом
          needs_export().
    """
    # Идентификация и состояние файла
    rvt_path: Path
    last_modified: datetime

    # --- Пути/конфиги для mapped-сценария ---
    # Папка для IFC с маппингом:
    #   - обязательна на этапе загрузки из <MANAGE_NAME>.xlsx;
    #   - может быть обнулена (None) после needs_export(),
    #     если экспорт по mapped-направлению не требуется.
    output_dir_mapping: Optional[Path]
    # JSON с настройками IFC-экспорта (mapped)
    mapping_json: Path
    # txt-сопоставление категорий Revit↔IFC
    family_mapping_file: Path

    # Версия Revit (лениво вычисляемая) и номер сборки (если доступен)
    version: Optional[int] = field(default=None, repr=False)
    build: Optional[str] = field(default=None, repr=False)

    # --- Опциональные поля для сценария «без маппинга» ---
    # Папка для IFC без маппинга (может отсутствовать)
    output_dir_nomap: Optional[Path] = None
    # JSON для «без маппинга» (если включено)
    nomap_json: Optional[Path] = None

    # ---------------------- инициализация ----------------------
    def __post_init__(self) -> None:
        """Нормализует только уже известные пути, приводя их к абсолютным.

        Если какое-то поле равно None — не трогаем его.
        """
        # Обязательные пути
        self.rvt_path = resolve_if_exists(self.rvt_path)
        self.output_dir_mapping = resolve_if_exists(self.output_dir_mapping)
        self.mapping_json = resolve_if_exists(self.mapping_json)
        self.family_mapping_file = resolve_if_exists(self.family_mapping_file)

        # Опциональные пути
        self.output_dir_nomap = resolve_if_exists(self.output_dir_nomap)
        self.nomap_json = resolve_if_exists(self.nomap_json)

    # ---------------------- свойства-удобности ----------------------
    @property
    def name(self) -> str:
        """Имя модели без расширения (используется для имени IFC).

        :return: Имя файла модели без расширения.
        """
        return self.rvt_path.stem

    # --------------------- основная логика ---------------------
    def load_version(self, strict: bool = False) -> None:
        """Загружает версию Revit и номер сборки через RevitVersionInfo.

        Поведение:
            - Если версия уже определена (self.version не None) — выходим.
            - Иначе читаем файл .rvt, извлекаем (год, build) и сохраняем
              в self.version и self.build.
            - strict=True  → выбрасываем ValueError, если определить версию
              не удалось (info is None).
            - strict=False → тихо выходим, оставляя self.version/self.build
              без изменений.

        Побочные эффекты:
            - Заполняет/обновляет self.version (int) и self.build (str | None).

        :param strict: Режим строгости при отсутствии версии.
        """
        if self.version is not None:
            return

        # Получаем (год, build) через RevitVersionInfo.as_tuple()
        info = RevitVersionInfo(self.rvt_path).as_tuple()
        if info is None:
            if strict:
                raise ValueError(
                    f"Не удалось определить версию Revit: {self.rvt_path}")
            return

        ver, build = info
        self.version = ver
        self.build = build

    # ------------------- принятие решения об экспорте -------------------
    def decide_export(
        self,
        history: HistoryLike,
        ifc_checker: IFCCheckerLike,
    ) -> ExportDecision:
        """Выполняет все проверки и возвращает структурированный результат.

        Поведение:
            - history.is_up_to_date(self) → history_ok;
            - ifc_checker.is_ifc_up_to_date_mapping(self) → ifc_map_ok;
            - ifc_checker.is_ifc_up_to_date_nomap(self) → ifc_nomap_ok.

        Ничего в состоянии RevitModel не меняет.

        :param history: Объект, реализующий HistoryLike.
        :param ifc_checker: Объект, реализующий IFCCheckerLike.
        :return: Экземпляр ExportDecision с флагами актуальности.
        """
        history_ok = history.is_up_to_date(self)
        ifc_map_ok = ifc_checker.is_ifc_up_to_date_mapping(self)
        ifc_nomap_ok = ifc_checker.is_ifc_up_to_date_nomap(self)

        return ExportDecision(
            history_ok=history_ok,
            ifc_map_ok=ifc_map_ok,
            ifc_nomap_ok=ifc_nomap_ok,
        )

    def needs_export(
        self,
        history: HistoryLike,
        ifc_checker: IFCCheckerLike,
    ) -> bool:
        """Решает, нужен ли экспорт модели, и обновляет её состояние.

        Правила:
            - Если:
                * запись в истории актуальна,
                * AND mapped-IFC актуален / не требуется,
                * AND nomap-IFC актуален / не требуется,
              то экспорт НЕ нужен.
            - Во всех остальных случаях — экспорт нужен.

        Дополнительно:
            - Если по направлению (mapped/nomap) IFC актуален или не нужен,
              соответствующий output_dir_* обнуляется (None), чтобы это
              направление не попадало в <TMP_NAME>.csv и не инициировался
              повторный экспорт по нему.

        :param history: Объект, реализующий HistoryLike.
        :param ifc_checker: Объект, реализующий IFCCheckerLike.
        :return: True, если требуется экспорт модели (по хотя бы одному
                 из направлений mapped/nomap).
        """
        decision = self.decide_export(history, ifc_checker)

        # «Отрубаем» те выгрузки, которые уже не нужны
        if decision.ifc_map_ok:
            self.output_dir_mapping = None
        if decision.ifc_nomap_ok:
            self.output_dir_nomap = None

        return decision.needs_any_export

    # ---------------------- ожидаемые пути IFC ----------------------
    def expected_ifc_path_mapping(self) -> Optional[Path]:
        """Ожидаемый путь к IFC в папке «mapped».

        :return: Путь к <output_dir_mapping>/<name>.ifc или None,
                 если output_dir_mapping не задан (например, обнулён после
                 needs_export()).
        """
        if self.output_dir_mapping:
            return self.output_dir_mapping / f"{self.name}.ifc"
        return None

    def expected_ifc_path_nomap(self) -> Optional[Path]:
        """Ожидаемый путь к IFC в папке «nomap», если включено в настройках.

        Учитывает глобальный флаг FLAG_UNMAPPED: если он выключен,
        путь считается неактуальным и возвращается None.

        :return: Путь к <output_dir_nomap>/<name>.ifc или None.
        """
        if FLAG_UNMAPPED and self.output_dir_nomap:
            return self.output_dir_nomap / f"{self.name}.ifc"
        return None
