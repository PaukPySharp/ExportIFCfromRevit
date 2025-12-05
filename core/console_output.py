# -*- coding: utf-8 -*-
"""Консольное логирование для проекта.

Назначение:
    - Добавляет потоковый (stdout) хендлер к логгеру проекта.
    - Даёт аккуратный, читаемый вывод в консоль:
        * короткие теги уровней (DBG, INF, WRN, ERR, CRT),
        * опциональное время (до минут),
        * опциональные цвета (ANSI).

Контракты:
    - Используется только в коде, который работает из обычного CPython
      (не из-под Revit/pyRevit).
    - Внешний код должен:
        * получить логгер, например logging.getLogger("export_ifc"),
        * вызвать setup_console_logging(logger, ...),
        * дальше работать с логгером как обычно (info/warning/error).

Особенности:
    - Не вмешивается в другие хендлеры логгера (если будут добавлены,
      например, файловые хендлеры).
    - Автоматически отключает цвета, если stdout не TTY (редирект в файл).
"""
import sys
import time
import logging
from typing import Optional, TextIO

from config import FORMAT_DATETIME

__all__ = [
    "setup_console_logging",
]

# ----------------------------- константы -----------------------------
#: ANSI escape-последовательности для оформления вывода в консоль.
#:
#: Ключи:
#:   - "reset", "dim" — служебные коды сброса и приглушения.
#:   - "lvl_*"        — оформление сообщения в зависимости от уровня лога.
ANSI: dict[str, str] = {
    "reset": "\x1b[0m",
    "dim": "\x1b[2m",
    "lvl_debug": "\x1b[36m",      # cyan
    "lvl_info": "\x1b[37m",       # white
    "lvl_warning": "\x1b[33m",    # yellow
    "lvl_error": "\x1b[31m",      # red
    "lvl_critical": "\x1b[41m\x1b[97m",  # white on red bg
}

# Короткие метки уровней, чтобы вывод был компактный и однородный.
LEVEL_TAG: dict[int, str] = {
    logging.DEBUG: "DBG",
    logging.INFO: "INF",
    logging.WARNING: "WRN",
    logging.ERROR: "ERR",
    logging.CRITICAL: "CRT",
}


# ----------------------------- форматтер -----------------------------
class ConsoleFormatter(logging.Formatter):
    """Форматтер строк консольного лога.

    Назначение:
        - Преобразует logging.LogRecord в готовую строку для вывода.
        - Добавляет:
            * опциональное время (до минут),
            * короткий тег уровня (DBG/INF/...),
            * цветовое оформление (если разрешено).

    Контракты:
        - На вход получает живой LogRecord, который уже прошёл через logging.
        - Не должен кидать исключения (иначе logging будет ругаться).
    """

    def __init__(
        self,
        use_colors: bool = True,
        show_time: bool = True,
    ) -> None:
        """Инициализирует форматтер консольного лога.

        :param use_colors: Включать ли ANSI-раскраску уровней лога.
        :param show_time: Показывать ли в начале строки метку времени
                          (формат FORMAT_DATETIME).
        """
        super().__init__()
        self.use_colors = use_colors
        self.show_time = show_time

    def format(self, record: logging.LogRecord) -> str:
        """Формирует финальную строку для вывода.

        Формат:
            [при show_time=True] "YYYY-MM-DD HH:MM " (серым цветом, если есть
            цвета)
            "<TAG> " (цветом уровня)
            "<сообщение>"

        :param record: Лог-запись logging для форматирования.
        :return: Готовая строка для вывода в консоль.
        """
        # Локальное время, формат как в проекте — до минут (без секунд)
        ts = time.strftime(FORMAT_DATETIME) if self.show_time else ""
        # Короткий текстовый тег уровня (DBG/INF/WRN/ERR/CRT)
        tag = LEVEL_TAG.get(record.levelno, "LOG")

        # Базовый текст сообщения (logging сам подставит %s-плейсхолдеры)
        msg = record.getMessage()

        # Готовим части для времени и тега уровня:
        # - при использовании цветов заворачиваем их в ANSI-последовательности;
        # - без цветов оставляем обычный текст.
        if self.use_colors:
            color = self._color_for_level(record.levelno)
            reset = ANSI["reset"]

            # Метка времени — тусклым цветом (если включен вывод времени)
            ts_part = f"{ANSI['dim']}{ts}{reset}" if ts else ""
            # Тег уровня — цветом в зависимости от уровня (INFO/ERROR/...)
            tag_part = f"{color}{tag}{reset}"
        else:
            # Вариант без цветов: просто голый текст
            ts_part = ts
            tag_part = tag

        # Финальная сборка частей:
        #   [время, если есть] [тег уровня] [сообщение]
        parts: list[str] = []
        if ts_part:
            parts.append(ts_part)
        parts.append(tag_part)
        parts.append(msg)

        return " ".join(parts)

    @staticmethod
    def _color_for_level(level: int) -> str:
        """Подбирает цветовую схему под уровень логирования.

        :param level: Числовой уровень логирования (logging.DEBUG/INFO/...).
        :return: ANSI-последовательность для оформления уровня.
        """
        if level >= logging.CRITICAL:
            return ANSI["lvl_critical"]
        if level >= logging.ERROR:
            return ANSI["lvl_error"]
        if level >= logging.WARNING:
            return ANSI["lvl_warning"]
        if level >= logging.INFO:
            return ANSI["lvl_info"]
        return ANSI["lvl_debug"]


# ----------------------------- хендлер -----------------------------
class ConsoleLogHandler(logging.StreamHandler):
    """Потоковый хендлер для логирования в консоль (stdout).

    Назначение:
        - Писать логи в stdout (или другой поток).
        - Использовать ConsoleFormatter для человекочитаемого вывода.

    Контракты:
        - Не вмешивается в работу других хендлеров (например, файловых).
        - Не реализует никакой спец-логики (типа progress-bar) —
          просто красиво печатает строки.
    """

    def __init__(
        self,
        stream: TextIO = sys.stdout,
        use_colors: Optional[bool] = None,
        show_time: bool = True,
    ) -> None:
        """Инициализирует потоковый хендлер консольного лога.

        :param stream: Поток вывода (по умолчанию stdout).
        :param use_colors: Принудительно включить/выключить цвета.
                           Если None — включаем только если stream.isatty().
        :param show_time: Показывать ли время в каждой строке.
        """
        super().__init__(stream=stream)

        # Определяем, является ли поток "живой" консолью (TTY).
        self.is_tty = hasattr(stream, "isatty") and stream.isatty()

        # Если use_colors не задан, включаем цвета только для TTY.
        effective_use_colors = (
            self.is_tty if use_colors is None else bool(use_colors)
        )

        # Назначаем форматтер, отвечающий за время/уровень/цвет.
        self.setFormatter(ConsoleFormatter(effective_use_colors, show_time))


# ----------------------------- API установки -----------------------------
def setup_console_logging(
    logger: logging.Logger,
    level: int = logging.INFO,
    use_colors: Optional[bool] = None,
    show_time: bool = True,
) -> ConsoleLogHandler:
    """Создаёт и цепляет консольный хендлер к переданному логгеру.

    Назначение:
        - Быстро включить адекватный вывод в консоль для логгера проекта.

    Особенности:
        - Не мешает уже настроенным FileHandler (txt-логи остаются).
        - Цвета автоматически отключаются, если stdout не TTY
          (например, при редиректе в файл).

    :param logger: Логгер, к которому подключаем консольный вывод.
    :param level: Уровень логгирования для консоли (INFO/DEBUG/...).
    :param use_colors: Принудительно включить/выключить цвета (None — авто).
    :param show_time: Показывать время в начале каждой строки.
    :return: Созданный ConsoleLogHandler (на случай дальнейшей
             настройки/отключения).
    """
    handler = ConsoleLogHandler(
        stream=sys.stdout,
        use_colors=use_colors,
        show_time=show_time,
    )
    handler.setLevel(level)
    logger.addHandler(handler)

    # Если у логгера уровень выше, чем level (или NOTSET) —
    # понижаем до нужного.
    # Это гарантирует, что сообщения заданного уровня действительно будут
    # доходить до консоли.
    if logger.level > level or logger.level == logging.NOTSET:
        logger.setLevel(level)

    return handler

# ---------------------- пример локального запуска ----------------------
# Этот блок оставлен как справка по использованию модуля
# при тестировании из CPython-скрипта.
# if __name__ == "__main__":
#     log = logging.getLogger("export_ifc")
#     setup_console_logging(log, level=logging.INFO)
#     log.info("Начинаем экспорт…")
#     log.warning("Предупреждение: что-то заняло больше времени.")
#     log.error("Ошибка: не удалось экспортировать модель.")
