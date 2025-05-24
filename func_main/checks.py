# -*- coding: utf-8 -*-

from func_main.conversion import datetime_file_modification


def check_unload_ifc(history_data_about_files: list[dict],
                     data_file: dict,
                     all_files_ifc: dict) -> bool:
    # изначально устанавливаем флаг, что выгружать ifc нужно
    flag = True
    for history_data in history_data_about_files:
        if (str(data_file['Путь_до_файла']) == history_data['Путь_до_файла']
                and data_file['ДатаВремя'] == history_data['ДатаВремя']):
            # удаление данных из истории если пути и дата/время совпали
            history_data_about_files.remove(history_data)
            if any(
                    ifc_file.stem == data_file['ИмяФайла'] and
                    data_file['ДатаВремя'] <= datetime_file_modification(
                        ifc_file)
                    for ifc_file in
                    all_files_ifc[data_file['Путь_до_глав_папки']]):
                # если все проверки прошли, то устанавливаем флаг,
                # что выгружать ifc не нужно
                flag = False
                break

    return flag
