# -*- coding: utf-8 -*-

def get_version_rvt(file_path: str) -> int | None:
    # попытка открыть файл в битовом формате
    # при неудаче возвращаем None
    try:
        # читаем содержимое файла Revit в битовом формате
        with open(file_path, 'rb') as f:
            data = f.read()
    except Exception:
        return None

    # кодируем строчку Build для поиска внутри файла Revit
    str_for_search = 'Format:'.encode('UTF-16-LE')
    index_text_ver = data.find(str_for_search)
    # проверяем найден ли индекс
    if index_text_ver > 0:
        # получает строку длиною 24 символа из данных и декодируем ее
        build_string = data[index_text_ver: index_text_ver + 24]
        build_string = build_string.decode('UTF-16-LE')
        # разделяем полученную строку по пробелу
        build_string = build_string.split()[1]
        # переводим строку в число
        build_int = int(build_string)
        return build_int
    else:
        return None
