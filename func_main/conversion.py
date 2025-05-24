# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime

from const.constants import FORMAT_DATETIME


def datetime_file_modification(path_to_file: Path) -> datetime:
    mtime = path_to_file.stat().st_mtime  # получаем время модификации файла
    # конвертируем из миллисекунд в datetime
    conv_timestamp = datetime.fromtimestamp(mtime)
    # переводим полученное значение в нужный формат
    return datetime.strptime(
        datetime.strftime(conv_timestamp, FORMAT_DATETIME),
        FORMAT_DATETIME)
