# -*- coding: utf-8 -*-
import os
import openpyxl
from pathlib import Path

from const.constants import (
    SCRIPT_EXPORT_IFC,
    MODELS_DICT_PATH,
    MANAGE_PATH,
    FOLDER_LOGS,
    HISTORY_PATH,
    LIST_VERSION_REVIT,
    FOLDER_ADMIN_DATA,
)

from func_main.logs import create_logs_file
from func_main.checks import check_unload_ifc
from func_main.versions import get_version_rvt
from func_main.unification import union_new_with_history
from func_main.import_data import (
    search_rvt_files,
    get_history_rvt_files,
    get_ifc_from_main_folder,
    get_ignore_files,
)
from func_main.records import (
    create_task_files,
    record_history_rvt_files,
    create_file_with_path_and_mapping,
    create_folder_not_mapping,
)


# получаем данные из Excel (пути, игнор лист и историю)
manage = openpyxl.load_workbook(MANAGE_PATH, read_only=True)
data_about_rvt_files = search_rvt_files(manage)
ignore_list = get_ignore_files(manage)
manage.close()  # закрывает файл с путями

history = openpyxl.load_workbook(HISTORY_PATH)
history_data_about_files = get_history_rvt_files(history)

# ОСНОВНОЙ АЛГОРИТМ: создание заданий для передачи в ExportIFC

# получаем словарь {имя папки: список путей до ifc}
all_files_ifc = get_ifc_from_main_folder(data_about_rvt_files)

# создаем папки для не смаппированных ifc
create_folder_not_mapping(data_about_rvt_files)

# создаем пустой словарь для заполнения путями до rvt,
# которые надо экспортировать в ifc
dict_path_for_tasks = dict((ver, [])
                           for ver in LIST_VERSION_REVIT)
# минимальная версия Revit, которая обрабатывается скриптом
min_version_in_script = LIST_VERSION_REVIT[0]

# создание списка для файлов в которых не нашлась версия Revit
version_not_found = []
# создание списка для файлов в которых версия Revit больше заявленных
version_very_large = []
# цикл для заполнения словаря dict_path_for_tasks в соответствии с версией Revit
for data_file in data_about_rvt_files:
    # извлекает данные о файле из словаря
    abs_path_to_file = str(data_file['Путь_до_файла'])
    folder_for_mapping = data_file['ШаблонМаппирования']

    # проверяем, нужно ли выгружать ifc из файла rvt
    if (not check_unload_ifc(history_data_about_files,
                             data_file,
                             all_files_ifc) or
            abs_path_to_file in ignore_list):
        continue

    # получаем версию Revit в которой изменили модель,
    # чтобы правильно сформировать задания
    version = get_version_rvt(abs_path_to_file)

    if version is None:
        # если мы не смогли определить версию Revit, то попускаем файл
        version_not_found.append(
            f'{abs_path_to_file} - у модели не найдена версия Revit')
        continue
    elif version < min_version_in_script:
        dict_path_for_tasks[min_version_in_script].append(
            (abs_path_to_file, folder_for_mapping))
    elif version in LIST_VERSION_REVIT:
        dict_path_for_tasks[version].append(
            (abs_path_to_file, folder_for_mapping))
    else:
        version_very_large.append(
            f'{abs_path_to_file} - у модели версия Revit выше заявленных')

# записываем полученные списки файлов для заданий в txt
create_task_files(dict_path_for_tasks, MODELS_DICT_PATH)
# объединяем новые данные по rvt файлам и старые из истории
union_new_with_history_data = union_new_with_history(data_about_rvt_files,
                                                     history_data_about_files)
# изменяем список с историями в Excel
record_history_rvt_files(history, union_new_with_history_data)
# завершение работы с Excel history
history.save(HISTORY_PATH)
history.close()

# проверка на то во всех ли файлах версии Revit ниже заявленных
if version_very_large:
    create_logs_file(
        FOLDER_LOGS,
        version_very_large,
        '3_not_supported_versions_rvt'
    )

# проверка на то во всех ли файлах определились версии
if version_not_found:
    create_logs_file(
        FOLDER_LOGS,
        version_not_found,
        '4_not_found_versions_in_rvt'
    )


# основной цикл для передачи задания в pyrevit и запуск скрипта ExportIFC
for year in MODELS_DICT_PATH:
    path_task_file = MODELS_DICT_PATH[year]
    # получаем путь до файла со списком файлов для задания командной строке
    data_from_tmp_file = dict_path_for_tasks[year]
    # делаем проверку были ли записаны в задания пути до rvt файлов
    if data_from_tmp_file:
        path_tmp_file = str(Path(FOLDER_ADMIN_DATA, 'tmp.csv'))
        # создаем файл tmp с данными о путях до rvt и шаблоном маппирования
        create_file_with_path_and_mapping(data_from_tmp_file, path_tmp_file)

        # передача задания командной строке windows
        # запуск с дебагом
        # command = (f'pyrevit run "{script_export_ifc}" '
        #            f'--models="{path_task_file}" --revit={year} --debug')

        # запуск без дэбага
        command = (f'pyrevit run "{SCRIPT_EXPORT_IFC}" '
                   f'--models="{path_task_file}" --revit={year}')

        os.system(command)
        os.remove(path_tmp_file)  # удаляем временный tmp файл
