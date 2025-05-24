# -*- coding: utf-8 -*-


def union_new_with_history(data_about_rvt_files: list[dict],
                           history_data_about_files: list[dict]) -> list[dict]:
    for data_rvt in data_about_rvt_files:
        abs_path_to_file = str(data_rvt['Путь_до_файла'])
        date_time = data_rvt['ДатаВремя']
        history_data_about_files.append({'Путь_до_файла': abs_path_to_file,
                                         'ДатаВремя': date_time})
    history_data_about_files = sorted(
        history_data_about_files,
        key=lambda x: (x['Путь_до_файла'],
                       -x['ДатаВремя'].timestamp()))
    return history_data_about_files
