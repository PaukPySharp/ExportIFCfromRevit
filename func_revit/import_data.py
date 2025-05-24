# -*- coding: utf-8 -*-
import csv
from pathlib import Path


def get_data_about_path_and_mapping(folder_admin_data: str) -> tuple:
    # создаем путь до tmp
    path_tmp_file = str(Path(folder_admin_data, 'tmp.csv'))
    with open(path_tmp_file, encoding='utf-8', newline='') as tmp:
        # считываем данные с путями и шаблонами маппинга
        data_about_path_and_mapping = tuple(csv.reader(tmp, delimiter=';'))
    return data_about_path_and_mapping
