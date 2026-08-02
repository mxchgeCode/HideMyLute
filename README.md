# hideMyLute
![](resources/666.jpg)

Инструмент стеганографии для «правдоподобного отрицания» (plausible deniability).

Соединяет файл-носитель (например, JPEG) и зашифрованный контейнер
(например, VeraCrypt-том) в один неотличимый файл-носитель.
Разделение возможно только при знании пароля и наличии корректного
собранного файла.

## Возможности

- **Соединение (join)**: носитель + контейнер → один файл с
  зашифрованным футером метаданных
- **Разделение (split)**: извлечение контейнера при правильном пароле
- **Правдоподобное отрицание**: выходной файл сохраняет расширение
  носителя и визуально/структурно идентичен ему
- **AES-256-GCM**: аутентифицированное шифрование метаданных футера
- **PBKDF2-HMAC-SHA256**: 600 000 итераций для стойкости к перебору
- **SHA-256**: проверка целостности носителя при разделении
- **Потоковое копирование**: 1 МБ буфер, файлы любого размера
- **GUI**: CustomTkinter с двумя вкладками
- **Три стратегии именования**: WINDOWS_STYLE, UUID, SAME_AS_CARRIER

## Установка

Требуется Python ≥ 3.9. Рекомендуется виртуальное окружение:

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

## Зависимости

- [`cryptography`](https://cryptography.io) ≥ 50.0 — AES-256-GCM,
  PBKDF2HMAC
- [`customtkinter`](https://customtkinter.tomschimansky.com) ≥ 6.0 —
  современный GUI на базе tkinter
- `pytest`, `pytest-cov`, `ruff`, `pyinstaller` — только для разработки

## Быстрый старт

### GUI

```bash
python -m hideMyLute
```

Откроется окно с двумя вкладками:
- **Соединение** — выбор носителя, контейнера, пароля, стратегии имени
- **Разделение** — выбор собранного файла, пароля, каталога для
  извлечения

### Командная строка (API)

```python
from hideMyLute.steganography import join_files, split_file
from hideMyLute.steganography import generate_output_path, NamingStrategy
from hideMyLute import __version__

print(__version__)  # 3.0.0

# Соединение
output = join_files(
    "photo.jpg",           # носитель
    "container.bin",       # зашифрованный контейнер
    "photo (2).jpg",       # выходной файл
    "my_secret_password",  # пароль
)

# Разделение
container, metadata = split_file(
    output,
    "extracted_dir",
    "my_secret_password",
)
print(f"Контейнер извлечён: {container}")
print(f"Размер носителя: {metadata['carrier_size']}")

# Генерация имени выходного файла
path = generate_output_path(
    "photo.jpg",
    strategy=NamingStrategy.UUID,
)
```

Версию приложения можно получить без запуска GUI:

```bash
python -m hideMyLute --version
# hideMyLute 3.0.0
```

## Структура футера

```
┌──────────────────────────────────────────────────┐
│ Payload: footer_data_len байт                    │
│  = salt(32) || AES-256-GCM(JSON {                │
│      carrier_size, container_size,               │
│      carrier_hash_sha256, timestamp              │
│    })                                            │
├──────────────────────────────────────────────────┤
│ Заголовок (12 байт, последние в файле):          │
│  magic(b'HMLF') || version || flags || data_len  │
└──────────────────────────────────────────────────┘
```

## Формат вывода

Выходной файл: `[carrier_data][container_data][payload][header]`

- Магические байты `b'HMLF'` всегда в последних 12 байтах
- Расширение совпадает с расширением носителя
- Нет внешних файлов метаданных

## Версионирование

Версия приложения — `MAJOR.MINOR.PATCH` (см. `hideMyLute/_version.py`):

- **MAJOR** — несовместимые изменения формата футера или публичного API
- **MINOR** — новые возможности
- **PATCH** — количество изменений (исправлений и доработок) с момента
  предыдущего минорного релиза

Единый источник версии — модуль `hideMyLute/_version.py`; `__version__`
в `hideMyLute/__init__.py` импортируется из него. Версия выводится в
заголовке окна и через `python -m hideMyLute --version`. История
изменений ведётся в [`CHANGELOG.md`](CHANGELOG.md).

Текущая версия: **3.0.0** (несовместимые изменения формата футера).

## Разработка

### Запуск тестов

```bash
pytest hideMyLute/tests/ -v
```

### Покрытие

```bash
pytest hideMyLute/tests/ --cov=hideMyLute --cov-report=term-missing
```

### Линтинг

```bash
ruff check hideMyLute/
```

### Сборка одним файлом (PyInstaller)

Готовый автономный исполняемый файл: `dist/hideMyLute.exe`.
Ему не нужен установленный Python, он не создаёт дополнительных файлов
при работе и не оставляет следов (логирование отключено по умолчанию,
конфигурационные файлы не создаются).

Единственный поддерживаемый способ сборки — версионируемая спецификация
`hideMyLute.spec` (она закоммичена, сборка воспроизводима):

```bash
pip install -r requirements-dev.txt
pyinstaller --noconfirm hideMyLute.spec
```

или автоматизированный скрипт (устанавливает зависимости, прогоняет тесты
и собирает исполняемый файл):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
```

Результат: один файл `dist/hideMyLute.exe` (с ресурсом версии).

### Командная строка

Помимо GUI доступны CLI-подкоманды (пароль запрашивается интерактивно
через getpass, если не передан флаг `--password`):

```bash
python -m hideMyLute join carrier.jpg container.bin out.jpg --password "secret"
python -m hideMyLute split out.jpg --output-dir extracted
python -m hideMyLute info out.jpg
```

## Безопасность

- Пароль не хранится — только производный ключ в оперативной памяти
- AES-256-GCM обеспечивает конфиденциальность и целостность
- PBKDF2 с 600 000 итераций (OWASP 2023) усложняет перебор
- Проверка SHA-256 хеша носителя предотвращает подмену
- Футер неотличим от случайных данных в конце файла

## Архитектура

```
launcher.py               # Точка входа для сборки исполняемого файла
hideMyLute/
├── _version.py           # Версия 3.0.0 (единый источник версии)
├── __init__.py           # Экспорт __version__
├── __main__.py           # Точка входа (+ --version)
├── config.py             # AppConfig (frozen DC), константы, переводы
├── crypto.py             # AES-256-GCM, PBKDF2-HMAC-SHA256
├── exceptions.py         # Иерархия исключений
├── footer.py             # Упаковка/распаковка футера
├── logging_config.py     # Конфигурация логирования (NullHandler)
├── password_strength.py  # Оценка надёжности пароля
├── steganography.py      # join_files, split_file, generate_output_path
├── worker.py             # BackgroundWorker (threading)
├── ui/
│   ├── __init__.py
│   ├── join_panel.py     # Панель «Соединение»
│   ├── main_window.py    # Главное окно с вкладками
│   ├── split_panel.py    # Панель «Разделение»
│   └── widgets.py        # Переиспользуемые виджеты
└── tests/
    ├── __init__.py
    ├── test_config.py
    ├── test_crypto.py
    ├── test_footer.py
    ├── test_password_strength.py
    ├── test_steganography.py
    └── test_version.py
```

## Лицензия

MIT
