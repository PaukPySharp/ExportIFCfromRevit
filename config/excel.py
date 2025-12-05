# -*- coding: utf-8 -*-
"""Единая схема Excel: листы и индексы колонок.

Назначение:
    - Фиксирует структуру рабочих книг Excel
      (<MANAGE_NAME>.xlsx, <HISTORY_NAME>.xlsx).
    - Описывает, какие листы и какие столбцы за что отвечают.

Контракты:
    - Индексы колонок 0-based (A=0, B=1, ...), удобно для
      iter_rows(values_only=True).
    - Группировка по назначению:
        * MANAGE_* — <MANAGE_NAME>.xlsx;
        * HISTORY_* — <HISTORY_NAME>.xlsx.
    - Имена листов (SHEET_PATH, SHEET_IGNORE, SHEET_HISTORY) задаются
      во внешних настройках (settings.ini) и здесь не хардкодятся.
    - Любые изменения структуры Excel отражаются в этом модуле, чтобы не
      размазывать «магические числа» по коду.
"""

FORMAT_DATETIME_EXCEL = "yyyy-mm-dd hh:mm"
"""Excel number format: общий формат даты/времени для записи в ячейки."""

# ---------------------------- <MANAGE_NAME>.xlsx ----------------------------
# Листы:
#   SHEET_PATH, SHEET_IGNORE — задаются в settings.ini.
# Ниже — индексы колонок для соответствующих листов. Держим их в одном месте,
# чтобы при изменении структуры править только здесь.

# Колонки листа SHEET_PATH (manage)
MANAGE_COL_RVT_DIR = 0
"""A: Папка с .rvt (обяз.)."""

MANAGE_COL_OUT_MAP = 1
"""B: Папка выгрузки с маппингом (обяз.)."""

MANAGE_COL_MAP_DIR = 2
"""C: Папка настроек маппинга (внутри JSON_CONFIG_FILENAME)."""

MANAGE_COL_FAMILY_MAP = 3
"""D: Имя .txt для сопоставления категорий."""

MANAGE_COL_OUT_NOMAP = 4
"""E: Папка выгрузки без маппинга (опц.)."""

MANAGE_COL_NOMAP_NAME = 5
"""F: Имя .json для выгрузки без маппинга (опц.)."""

# Колонки листа SHEET_IGNORE (manage)
MANAGE_IGNORE_COL_PATH = 0
"""A: Путь для игнора."""

# --------------------------- <HISTORY_NAME>.xlsx ---------------------------
# Лист:
#   SHEET_HISTORY — задаётся в settings.ini.
# Здесь — заголовки, имя таблицы и индексы колонок для листа истории.

HISTORY_HDR_COL1 = "Файл RVT (полный путь)"
"""Текст заголовка колонки пути к RVT (ячейка A1)."""

HISTORY_HDR_COL2 = "Дата модификации файла"
"""Текст заголовка колонки даты модификации (ячейка B1)."""

HISTORY_TBL_NAME = "HistoryTable"
"""Стандартное имя Excel-таблицы на листе истории (openpyxl.Table)."""

# Колонки листа SHEET_HISTORY (history)
HISTORY_COL_RVT_PATH = 0
"""A: Полный путь к файлу .rvt."""

HISTORY_COL_DATETIME = 1
"""B: Дата модификации RVT (округлённая до минут)."""
