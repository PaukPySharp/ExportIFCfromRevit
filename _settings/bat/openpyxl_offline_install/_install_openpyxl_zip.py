# -*- coding: utf-8 -*-
"""Оффлайн-установка пакета openpyxl из локального архива.

Назначение:
    - Распаковать содержимое архива openpyxl.zip (пакет openpyxl и зависимости)
      в каталог site-packages текущего интерпретатора CPython.
    - Выступает офлайн-альтернативой установке через `pip install openpyxl`
      и вызывается из install_openpyxl_zip.bat.

Контракты:
    - Путь к архиву openpyxl.zip передаётся первым аргументом CLI.
    - Архив содержит структуру, совместимую с корнем site-packages.

Особенности:
    - Путь к каталогу site-packages определяется через модули site и
      sysconfig (ключи "purelib" или "platlib").
    - Перед распаковкой выполняется проверка от уязвимости «zip-slip»:
      файлы не могут быть извлечены за пределы каталога site-packages.
    - При ошибках скрипт пишет сообщения в stdout и возвращает код, отличный
      от нуля (см. main()).
"""

import sys
import zipfile
import site
import sysconfig
from pathlib import Path


def find_site_packages() -> Path:
    """
    Определяет путь к каталогу site-packages для текущего Python.

    Логика:
        - Сначала пробует использовать site.getsitepackages() и возвращает
          первый путь, оканчивающийся на "site-packages".
        - Если этот способ недоступен или не дал результатов, использует
          sysconfig.get_paths() и берёт значения ключей "purelib" или
          "platlib".

    :return:          Путь к каталогу site-packages.
    :raises RuntimeError: Если ни один из способов не дал валидный путь.
    """
    # 1) Пробуем стандартный путь через site.getsitepackages()
    try:
        for p in site.getsitepackages():
            path = Path(p)
            if path.name.lower() == "site-packages":
                return path
    except Exception:
        # site.getsitepackages() может не поддерживаться в некоторых окружениях
        pass

    # 2) Резервный вариант — sysconfig
    cfg = sysconfig.get_paths()
    for key in ("purelib", "platlib"):
        raw_path = cfg.get(key)
        if raw_path:
            return Path(raw_path)

    raise RuntimeError("Не удалось определить путь к каталогу site-packages")


def extract_zip_safe(archive_path: Path, target_dir: Path) -> None:
    """Распаковывает ZIP-архив в каталог с защитой от выхода за его пределы.

    Назначение:
        - Извлечь все файлы архива в target_dir.
        - Заблокировать записи с путями вида '../../...' (zip-slip),
          которые выходят за пределы целевого каталога.

    :param archive_path: Путь к ZIP-архиву с пакетами openpyxl.
    :param target_dir:   Каталог назначения (обычно site-packages).
    :raises RuntimeError: Если обнаружен некорректный путь внутри архива.
    """
    archive_path = archive_path.resolve()
    target_dir = target_dir.resolve()

    with zipfile.ZipFile(str(archive_path), "r") as zf:
        for member in zf.infolist():
            # Вычисляем итоговый путь и нормализуем его
            dest_path = (target_dir / member.filename).resolve()
            # Проверяем, что результирующий путь внутри target_dir
            # (предотвратим zip-slip)
            if not str(dest_path).startswith(str(target_dir)):
                raise RuntimeError(
                    "Некорректный путь в архиве (выходит за пределы "
                    f"site-packages): {member.filename}"
                )
        # Если проверки пройдены, распаковываем всё в target_dir
        zf.extractall(str(target_dir))


def main(argv: list[str]) -> int:
    """Точка входа для оффлайн-установки openpyxl из архива.

    Назначение:
        - Принять путь к openpyxl.zip.
        - Найти каталог site-packages текущего Python.
        - Распаковать архив в site-packages с базовой проверкой безопасности.

    :param argv: Список аргументов командной строки (обычно sys.argv).
    :return:     Код завершения: 0 при успехе, 1 при ошибке.
    """
    if len(argv) < 2:
        print("[ОШИБКА] Не передан путь к архиву openpyxl.zip")
        print(
            "  Использование: python _install_openpyxl_zip.py "
            "path/to/openpyxl.zip"
        )
        return 1

    # Путь к архиву
    archive_path = Path(argv[1]).expanduser().resolve()
    print(f"Архив с пакетами:\n  {archive_path}")

    if not archive_path.is_file():
        print("[ОШИБКА] Архив не найден.")
        return 1

    # Определяем каталог site-packages
    try:
        target = find_site_packages()
    except Exception as exc:
        print(f"[ОШИБКА] {exc}")
        return 1

    print(f"Каталог site-packages для текущего Python:\n  {target}")

    # Создаём каталог site-packages, если он не существует
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        print(f"[ОШИБКА] Не удалось создать каталог:\n  {target}\n  {exc}")
        return 1

    print("Распаковываю архив в site-packages...")

    # Распаковываем архив с проверкой
    try:
        extract_zip_safe(archive_path, target)
    except Exception as exc:
        print(f"[ОШИБКА] Не удалось распаковать архив: {exc}")
        return 1

    print("[OK] Архив успешно распакован.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
