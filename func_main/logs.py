# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime as dt


def create_logs_file(folder_logs: str,
                     data_list: list,
                     name_log: str) -> None:
    date_now = dt.strftime(dt.now(), '%Y.%m.%d')
    path_to_txt_log = Path(folder_logs, f'{name_log}_{date_now}.txt')

    with open(str(path_to_txt_log), 'a', encoding='utf-8') as log:
        for data in data_list:
            log.write(f'{data}\n')
        log.write('-' * 50 + '\n')
