# -*- coding: utf-8 -*-
"""Хелперы для чтения Excel (openpyxl).

Назначение:
    - Определение пустых значений/строк (для аккуратного обхода таблиц).
    - Безопасное извлечение ячеек как строк.
    - Парсинг дат из Excel в datetime (строковый формат, datetime,
    Excel-сериал).

Контракты:
    - Ожидается, что строки приходят из openpyxl с values_only=True
      (кортежи простых значений, а не объекты ячеек).
    - Пустые значения трактуются как:
        * None;
        * строки, состоящие только из пробелов.
    - При ошибках парсинга parse_datetime() всегда возвращает None,
      исключения наружу не выбрасываются.

Особенности:
    - Никаких зависимостей от Workbook/Sheet: все функции работают
      только с примитивными значениями (tuple, str, int, float, datetime).
    - Класс Xlsx используется как статический namespace — создавать
      экземпляры не требуется и не предполагается.
"""
from datetime import datetime
from typing import Any, Iterable, Optional, Sequence

from openpyxl.utils.datetime import from_excel as _excel_from_serial

from config import FORMAT_DATETIME


# --------------------- api: пустые значения/строки ---------------------
class Xlsx:
    """Утилиты для разбора данных Excel (статические методы).

    Назначение:
        - Сгруппировать часто используемые операции над "сырыми" значениями
          строк Excel (values_only=True):
            * проверка пустых строк/ячеек;
            * безопасное извлечение значений как строк;
            * парсинг дат.
    """

    @staticmethod
    def is_blank_value(v: Any) -> bool:
        """Возвращает True для пустых значений.

        Пустыми считаются:
            - None;
            - строки, состоящие только из пробелов.

        :param v: Любое значение ячейки.
        :return:  True, если значение считается пустым:
                    - None;
                    - строка, состоящая только из пробелов.
        """
        return v is None or (isinstance(v, str) and not v.strip())

    @staticmethod
    def is_blank_row(row: Optional[Iterable[Any]]) -> bool:
        """Проверяет, что вся строка пуста.

        :param row: Последовательность значений ячеек строки
                    (обычно кортеж из values_only=True) или None.
        :return:    True, если row is None ИЛИ все значения в строке
                    считаются пустыми (см. is_blank_value).

        Применяется при обходе листа: первая пустая строка по договорённости
        означает "дальше данных нет", и цикл чтения можно прервать.
        """
        if row is None:
            return True
        return all(Xlsx.is_blank_value(v) for v in row)

    # -------------------- api: извлечение ячейки --------------------
    @staticmethod
    def cell(row: Sequence[Any], idx: int) -> Optional[str]:
        """Безопасно извлекает ячейку как нормализованную строку.

        :param row: Кортеж/список значений строки (values_only=True).
        :param idx: 0-based индекс ячейки.
        :return:    Строка без пробелов по краям или None, если:
                      - индекс вне диапазона;
                      - значение None;
                      - значение после приведения к строке и strip()
                        даёт пустую строку.

        Пример:
            >>> Xlsx.cell(("  A  ", None, 10), 0)
            'A'
            >>> Xlsx.cell(("  A  ", None, 10), 1) is None
            True
        """
        if idx < 0 or idx >= len(row):
            return None
        val = row[idx]
        if val is None:
            return None
        s = str(val).strip()
        return s if s else None

    # ------------------------- api: парсинг дат -------------------------
    @staticmethod
    def parse_datetime(value: Any) -> Optional[datetime]:
        """Преобразует значение ячейки Excel в datetime.

        Поддерживаемые варианты:
            - datetime  → возвращается как есть;
            - str       → парсинг по FORMAT_DATETIME;
            - int/float → Excel-сериал (дни с 1899-12-30) через openpyxl.

        :param value: Значение ячейки (str | int | float | datetime | None).
        :return:     Объект datetime или None при неуспехе.

        Особенности:
            - Для строк строго используется FORMAT_DATETIME из config.
            - Для Excel-сериала используется from_excel из openpyxl,
              исключения переводятся в None.
            - Логика не бросает исключений наружу, чтобы не ронять парсер
              из-за единичной кривой ячейки.
        """
        # None или пустая строка — нет даты.
        if value is None:
            return None

        # Нативный datetime — возвращаем как есть.
        if isinstance(value, datetime):
            return value

        # Строка строго по FORMAT_DATETIME.
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            try:
                return datetime.strptime(s, FORMAT_DATETIME)
            except ValueError:
                return None

        # Числовой Excel-сериал (int/float), исключаем bool (наследник int).
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                return _excel_from_serial(float(value))
            except Exception:
                return None

        # Иные типы (list, dict, bool и т.п.) — не поддерживаются.
        return None
