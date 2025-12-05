# -*- coding: utf-8 -*-
"""Определение версии Revit и номера сборки из файла *.rvt.

Назначение:
    - Быстро и без запуска Revit извлечь из бинарного *.rvt:
        * год версии (например, 2023) — по маркерам `Format:` или по подписи
          `Autodesk Revit 20xx` (fallback);
        * номер сборки — по маркеру `Build:` (например, `20200909_1515`
          или `21.1.10.26`).

Алгоритм:
    1) Читается «голова» файла фиксированного размера (для скорости).
    2) В ней ищутся маркеры в UTF-16 LE и UTF-16 BE.
    3) Если год не найден — выполняется fallback по строке `Autodesk Revit`,
       где год идёт ПОСЛЕ маркера.
    4) При необходимости читается весь файл и поиск повторяется.
    5) Результат доступен через `as_tuple()` или поля `year` / `build`.

Контракты:
    - Ошибки ввода-вывода наружу не выбрасываются: при ошибке чтения
      получаем `year=None`, `build=None`.
    - Год валидируется по диапазону 2000…2100 (защита от ложных совпадений).
    - Строки в *.rvt* закодированы в UTF-16 LE/BE; поиск ведётся по коротким
      фрагментам после маркеров.

Особенности:
    - Сначала используется быстрый путь (чтение головы), затем при
      необходимости более медленный (читается весь файл).
    - Класс полностью автономен и не требует подключения Revit API.
"""
import re
from pathlib import Path
from typing import Optional, Tuple

# ----------------------------- константы модуля -----------------------------
# В *.rvt* строки ресурсов хранятся в UTF-16 (как LE, так и BE).
ENC_LE = "utf-16le"
ENC_BE = "utf-16be"

# Маркеры (в байтах) для обоих вариантов UTF-16
_FMT_LE = "Format:".encode(ENC_LE)
_FMT_BE = "Format:".encode(ENC_BE)
_BLD_LE = "Build:".encode(ENC_LE)
_BLD_BE = "Build:".encode(ENC_BE)
_AUT_LE = "Autodesk Revit".encode(ENC_LE)
_AUT_BE = "Autodesk Revit".encode(ENC_BE)

# ------------------------ Ограничения чтения/разбора -------------------------
# Сколько БАЙТ читаем из начала файла (быстрый путь)
_READ_HEAD_BYTES = 128 * 1024  # 128 KiB
# Сколько БАЙТ берём ПОСЛЕ 'Format:' для поиска года
_YEAR_TAIL_BYTES = 32
# Сколько БАЙТ берём ПОСЛЕ 'Build:' для поиска версии сборки
_BUILD_TAIL_BYTES = 64
# Для fallback по 'Autodesk Revit' смотрим ТОЛЬКО ВПЕРЁД от маркера
_AUTODESK_SUFFIX_BYTES = 128

# Фильтр от ложных совпадений
_MIN_YEAR, _MAX_YEAR = 2000, 2100

# Предкомпилированные шаблоны
_RE_YEAR = re.compile(r"\b(20\d{2})\b")
_RE_BUILD = re.compile(r"[\d._]+")

__all__ = ["RevitVersionInfo"]

# Кортеж (год_версии, build_строкой или None, если сборка не найдена)
YearBuild = Tuple[int, Optional[str]]


class RevitVersionInfo:
    """Извлекает год версии Revit и номер сборки из бинарного *.rvt.

    Состояние:
        - path  : Path           — путь к файлу RVT;
        - year  : int | None     — год версии (например, 2023);
        - build : str | None     — номер сборки (например, '20200909_1515').

    Правила извлечения:
        - Сначала ищется `Format: 20xx` (UTF-16 LE/BE).
        - Если не удалось — ищется `Autodesk Revit 20xx` и берётся год ПОСЛЕ
          маркера (fallback).
        - Номер сборки берётся из `Build:` (первое совпадение `[\\d._]+`).

    Детали:
        - Для скорости сначала читается «голова» файла, затем при необходимости
          весь файл.
        - Ошибки I/O не пробрасываются наружу: атрибуты остаются None.
    """

    # --------------------------- инициализация/представление -----------------
    def __init__(self, path: Path | str) -> None:
        """Инициализация и разбор файла.

        :param path: Путь к .rvt-файлу.
        """
        self.path = Path(path)
        self.year: Optional[int] = None
        self.build: Optional[str] = None
        self._parse_file()

    def __repr__(self) -> str:
        """Возвращает краткое текстовое представление версии.

        :return: Строка вида "<RevitVersionInfo 2023 build=...>" или
                 "<RevitVersionInfo unknown>".
        """
        if self.year is not None:
            return f"<RevitVersionInfo {self.year} build={self.build or '?'}>"
        return "<RevitVersionInfo unknown>"

    # ----------------------------- публичный API -----------------------------
    def as_tuple(self) -> Optional[YearBuild]:
        """Возвращает пару (год, build) или None.

        :return: Кортеж (year, build) при успешном разборе или None,
                 если год не определён.
        """
        if self.year is None:
            return None
        return self.year, self.build

    # --------------------------------- разбор --------------------------------
    def _parse_file(self) -> None:
        """Основной алгоритм разбора: быстрый путь + при необходимости полный.

        Шаги:
            1. Попытка извлечь год/сборку из «головы» файла.
            2. Fallback по 'Autodesk Revit', если год не найден.
            3. При необходимости — повторный разбор на полном содержимом.
        """
        # 1) Быстрый путь — читаем фиксированный префикс
        try:
            with open(self.path, "rb") as f:
                head = f.read(_READ_HEAD_BYTES)
        except Exception:
            # Ошибка доступа/чтения — остаёмся с None
            return

        # Пытаемся вытащить год/сборку из «головы»
        self.year = self._extract_year(head)
        self.build = self._extract_build(head)

        if self.year is None:
            # Fallback по 'Autodesk Revit' (год идёт после маркера)
            self.year = self._extract_year_from_autodesk(head)

        # Если уже нашли и год, и сборку — читать весь файл не обязательно
        if self.year is not None and self.build is not None:
            return

        # 2) Медленный путь — читаем весь файл и повторяем
        try:
            with open(self.path, "rb") as f:
                data = f.read()
        except Exception:
            return

        # Если год всё ещё не найден — пробуем снова (Format || Autodesk Revit)
        if self.year is None:
            self.year = (
                self._extract_year(data)
                or self._extract_year_from_autodesk(data)
            )

        # Build могли не найти в «голове» — повторяем на полном содержимом
        if self.build is None:
            self.build = self._extract_build(data)

    # ------------------------ извлечение по маркерам ------------------------
    @classmethod
    def _extract_year(cls, data: bytes) -> Optional[int]:
        """Ищет 'Format:' и берёт год (20xx) из короткого «хвоста» после
           маркера.

        :param data: Бинарный блок файла (голова или всё содержимое).
        :return: Год версии или None, если маркер не найден, год не распознан
                 или выходит за допустимый диапазон.
        """
        idx, enc, mlen = cls._find_marker(
            data, ((_FMT_LE, ENC_LE), (_FMT_BE, ENC_BE))
        )
        if idx is None or enc is None:
            return None

        # длина LE/BE по байтам совпадает
        start = idx + mlen
        tail = data[start: start + _YEAR_TAIL_BYTES]
        txt = tail.decode(enc, errors="ignore")

        # Ищем "20xx" — самые надёжные четыре цифры
        m = _RE_YEAR.search(txt)
        if not m:
            return None

        try:
            year = int(m.group(1))
        except ValueError:
            return None

        return year if _MIN_YEAR <= year <= _MAX_YEAR else None

    @classmethod
    def _extract_build(cls, data: bytes) -> Optional[str]:
        """Ищет 'Build:' и парсит номер сборки из «хвоста».

        :param data: Бинарный блок файла (голова или всё содержимое).
        :return: Строка с номером сборки или None, если маркер/номер не найден.
        """
        idx, enc, mlen = cls._find_marker(
            data, ((_BLD_LE, ENC_LE), (_BLD_BE, ENC_BE))
        )
        if idx is None or enc is None:
            return None

        start = idx + mlen
        tail = data[start: start + _BUILD_TAIL_BYTES]
        txt = tail.decode(enc, errors="ignore")

        # Чистим типичные «шумы»: нулевые байты, скобки, переводы строк.
        txt = txt.replace("\x00", " ")
        txt = txt.split(")")[0].split("\r")[0].split("\n")[0].strip()

        m = _RE_BUILD.search(txt)
        return m.group(0) if m else None

    @classmethod
    def _extract_year_from_autodesk(cls, data: bytes) -> Optional[int]:
        """Fallback: ищет четырёхзначный год ПОСЛЕ 'Autodesk Revit'.

        :param data: Бинарный блок файла (голова или всё содержимое).
        :return: Год версии или None, если найти не удалось или год вне
                 диапазона.
        """
        for marker, enc in ((_AUT_LE, ENC_LE), (_AUT_BE, ENC_BE)):
            i = data.find(marker)
            if i == -1:
                continue

            # Ищем только ВПЕРЁД от маркера: известные файлы пишут
            # "Autodesk Revit 20xx ..."
            start = i + len(marker)
            end = min(len(data), start + _AUTODESK_SUFFIX_BYTES)
            frag = data[start:end].decode(enc, errors="ignore")

            m = _RE_YEAR.search(frag)
            if not m:
                continue

            try:
                year = int(m.group(1))
            except ValueError:
                continue

            if _MIN_YEAR <= year <= _MAX_YEAR:
                return year

        return None

    @staticmethod
    def _find_marker(
        data: bytes,
        variants: tuple[tuple[bytes, str], ...],
    ) -> tuple[Optional[int], Optional[str], int]:
        """
        Ищет позицию маркера (LE/BE) и возвращает (индекс, кодировка, длина).

        :param data: Бинарное содержимое файла или его части.
        :param variants: Набор пар (маркер_в_байтах, имя_кодировки).
        :return: (index, encoding, marker_len), где:
                 - index    — позиция маркера или None, если не найден;
                 - encoding — 'utf-16le' / 'utf-16be' или None;
                 - marker_len — длина найденного маркера в байтах
                 (0, если не найден).
        """
        for marker, enc in variants:
            idx = data.find(marker)
            if idx != -1:
                return idx, enc, len(marker)
        return None, None, 0


# ===== Archive =====
# Локальный пример использования:
# if __name__ == "__main__":
#     info = RevitVersionInfo(Path(
#         r"путь\к\файлу.rvt"
#     ))
#     year_build = info.as_tuple()
#     print(year_build)
