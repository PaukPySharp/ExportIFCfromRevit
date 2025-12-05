# -*- coding: utf-8 -*-
"""Загрузка конфигурации из ini-файла.

Назначение:
    - Читает настройки из settings.ini.
    - Предоставляет доступ к параметрам через Singleton Settings.

Контракты:
    - Поиск корня проекта выполняется по ENV, расположению config/, utils/
      и sys.argv[0].
    - Значения приводятся к нужным типам на уровне геттеров.
    - При отсутствии обязательных параметров выбрасывается KeyError,
      при отсутствии ini — FileNotFoundError.
"""
import os
import sys
from typing import List
from pathlib import Path
from threading import Lock
from configparser import ConfigParser

from config.constants import SETTINGS_INI


class Settings:
    """Singleton для конфигурационных настроек.

    Читает ini-файл и предоставляет параметры через свойства.
    Потокобезопасен за счёт внутреннего Lock.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls, ini_path: str = SETTINGS_INI):
        """Возвращает единственный экземпляр Settings.

        :param ini_path: Относительный путь к ini (от корня проекта).
        :return: Экземпляр Settings.
        """
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialize(ini_path)
                cls._instance = instance
        return cls._instance

    def _initialize(self, ini_path: str) -> None:
        """Выполняет первичную инициализацию парсера и пути к ini.

        :param ini_path: Относительный путь к ini (от корня проекта).
        """
        self.main_dir: Path = self._detect_project_root()

        # Путь до ini-файла относительно main_dir.
        self._ini_path = self.main_dir / ini_path

        # Парсер конфигурации.
        self._config = ConfigParser()
        self._load_ini()

    def _detect_project_root(self) -> Path:
        """Определяет корень проекта (main_dir).

        Порядок проверки:
            1. Переменная окружения EXPORTIFC_ROOT (если есть config/
               и utils/).
            2. Родительская директория config/ (по __file__).
            3. Директория из sys.argv[0].
            4. В противном случае выбрасывается RuntimeError.

        :return: Путь к корню проекта.
        :raises RuntimeError: Если корень определить не удалось.
        """
        env_root = os.environ.get("EXPORTIFC_ROOT")
        if env_root:
            env_path = Path(env_root).resolve()
            if ((env_path / "config").is_dir()
                    and (env_path / "utils").is_dir()):
                return env_path

        # .. (корень относительно файла config/settings.py)
        candidate = Path(__file__).resolve().parents[1]
        if (candidate / "config").is_dir() and (candidate / "utils").is_dir():
            return candidate

        # Папка, откуда запущен основной скрипт.
        from_argv = Path(sys.argv[0]).resolve().parent
        if (from_argv / "config").is_dir() and (from_argv / "utils").is_dir():
            return from_argv

        raise RuntimeError(
            "Не удалось определить корень проекта; задайте EXPORTIFC_ROOT"
        )

    def _load_ini(self) -> None:
        """Загружает ini в память или сообщает точный путь при ошибке.

        :raises FileNotFoundError: Если ini-файл не существует.
        """
        if self._ini_path.exists():
            self._config.read(str(self._ini_path), encoding="utf-8")
        else:
            raise FileNotFoundError(
                f"Не найден settings.ini: {self._ini_path}"
            )

    # --------------------- чтение/запись параметров ---------------------
    def _get(self, section: str, key: str, cast=None):
        """Возвращает значение параметра из ini-файла.

        :param section: Название секции ini.
        :param key:     Название параметра внутри секции.
        :param cast:    Функция преобразования типа значения (опц.).
        :return: Значение параметра (с приведением типа, если указано).
        :raises KeyError: Если параметр отсутствует.
        """
        if self._config.has_option(section, key):
            val = self._config.get(section, key)
        else:
            raise KeyError(
                f"В settings.ini отсутствует параметр: [{section}] {key}")

        return cast(val) if cast else val

    def _get_def(self, section: str, key: str, default: str):
        """Возвращает значение параметра или default, если он не задан.

        :param section: Название секции ini.
        :param key:     Название параметра внутри секции.
        :param default: Значение по умолчанию.
        :return: Значение параметра или default.
        """
        try:
            return self._get(section, key)
        except KeyError:
            return default

    def _set(self, section: str, key: str, value) -> None:
        """Устанавливает новое значение параметра и сохраняет ini-файл.

        :param section: Название секции ini.
        :param key:     Название параметра внутри секции.
        :param value:   Новое значение параметра.
        """
        if not self._config.has_section(section):
            self._config.add_section(section)
        self._config.set(section, key, str(value))
        with open(str(self._ini_path), "w", encoding="utf-8") as f:
            self._config.write(f)

    # ------------------------- Пути -------------------------
    @property
    def dir_scripts(self) -> str:
        """Возвращает путь к папке со скриптами (корень приложения).

        :return: Абсолютный путь к директории, где расположен main.
        """
        return str(self.main_dir)

    @property
    def dir_export_config(self) -> str:
        """Возвращает путь к папке с маппинг-файлами.

        :return: Путь к директории маппинга.
        """
        return self._get("Paths", "dir_export_config")

    @property
    def dir_admin_data(self) -> str:
        """Возвращает путь к папке admin_data.

        :return: Путь к директории admin_data.
        """
        return self._get("Paths", "dir_admin_data")

    # ------------------------- Файлы -------------------------
    @property
    def config_json(self) -> str:
        """Возвращает имя JSON-файла с настройками маппинга.

        :return: Имя JSON-файла без расширения.
        """
        return self._get("Files", "config_json")

    # ------------------------- Режимы работы -------------------------
    @property
    def is_prod_mode(self) -> bool:
        """Возвращает признак режима работы приложения.

        :return:
            True — production-режим;
            False — тестовый режим.
        """
        val = self._get("Settings", "is_prod_mode")
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("1", "true", "yes", "да")

    @property
    def enable_unmapped_export(self) -> bool:
        """Возвращает флаг выгрузки дополнительного IFC без маппирования.

        :return:
            True — выполнять параллельную выгрузку «пустых» IFC;
            False — выгружать только основную версию с маппированием.
        """
        val = self._get("Settings", "enable_unmapped_export")
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("1", "true", "yes", "да")

    # ------------------------- Revit -------------------------
    @property
    def revit_versions(self) -> List[int]:
        """Возвращает список поддерживаемых версий Revit.

        :return: Отсортированный список уникальных версий (int).
        """
        val = self._get("Revit", "revit_versions")
        return sorted(set(int(x.strip()) for x in val.split(",")))

    @property
    def export_view3d_name(self) -> str:
        """Возвращает имя 3D-вида, который используется для экспорта.

        :return: Имя 3D-вида (по умолчанию 'Navisworks').
        """
        return self._get_def("Revit", "export_view3d_name", "Navisworks")

    # ------------------------- Excel -------------------------
    @property
    def sheet_path(self) -> str:
        """Возвращает имя листа Excel с путями/настройками.

        :return: Имя листа (например, 'Path').
        """
        return self._get_def("Excel", "sheet_path", "Path")

    @property
    def sheet_ignore(self) -> str:
        """Возвращает имя листа Excel с игнор-списком.

        :return: Имя листа (например, 'IgnoreList').
        """
        return self._get_def("Excel", "sheet_ignore", "IgnoreList")

    @property
    def sheet_history(self) -> str:
        """Возвращает имя листа Excel с историей.

        :return: Имя листа (например, 'History').
        """
        return self._get_def("Excel", "sheet_history", "History")

    # ---------- Mapping (имена подпапок внутри DIR_EXPORT_CONFIG) ----------
    @property
    def mapping_dir_common(self) -> str:
        """Возвращает имя подпапки с общими конфигурациями маппинга.

        :return: Имя подпапки (например, '00_Common').
        """
        return self._get_def("Mapping", "dir_common", "00_Common")

    @property
    def mapping_dir_layers(self) -> str:
        """Возвращает имя подпапки с txt-слоями (Revit-категории → IFC).

        :return: Имя подпапки (например, '01_Export_Layers').
        """
        return self._get_def("Mapping", "dir_layers", "01_Export_Layers")


# ------------------------- Инициализация (Singleton) -------------------------
SETTINGS = Settings()
