# hideMyLute

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

- [`cryptography`](https://cryptography.io) ≥ 42.0 — AES-256-GCM,
  PBKDF2HMAC
- [`customtkinter`](https://customtkinter.tomschimansky.com) ≥ 5.2 —
  современный GUI на базе tkinter
- `pytest`, `pytest-cov`, `ruff` — только для разработки

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

## Структура футера

```
┌──────────────────────────────────────────────────┐
│ Payload: footer_data_len байт                     │
│  = salt(32) || AES-256-GCM(JSON {                 │
│      carrier_size, container_size,               │
│      carrier_hash_sha256, timestamp              │
│    })                                             │
├──────────────────────────────────────────────────┤
│ Заголовок (12 байт, последние в файле):           │
│  magic(b'HMLF') || version || flags || data_len  │
└──────────────────────────────────────────────────┘
```

## Формат вывода

Выходной файл: `[carrier_data][container_data][payload][header]`

- Магические байты `b'HMLF'` всегда в последних 12 байтах
- Расширение совпадает с расширением носителя
- Нет внешних файлов метаданных

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

### Сборка одним файлом (Nuitka)

```bash
pip install nuitka
nuitka --standalone --onefile --windows-console-mode=disable hideMyLute/__main__.py
```

## Безопасность

- Пароль не хранится — только производный ключ в оперативной памяти
- AES-256-GCM обеспечивает конфиденциальность и целостность
- PBKDF2 с 600 000 итераций (OWASP 2023) усложняет перебор
- Проверка SHA-256 хеша носителя предотвращает подмену
- Футер неотличим от случайных данных в конце файла

## Архитектура

```
hideMyLute/
├── __init__.py          # Версия 2.0.0
├── __main__.py          # Точка входа
├── config.py            # AppConfig (frozen DC), константы, переводы
├── crypto.py            # AES-256-GCM, PBKDF2-HMAC-SHA256
├── exceptions.py        # Иерархия исключений
├── footer.py            # Упаковка/распаковка футера
├── logging_config.py    # Конфигурация логирования (NullHandler)
├── steganography.py     # join_files, split_file, generate_output_path
├── worker.py            # BackgroundWorker (threading)
├── ui/
│   ├── __init__.py
│   ├── join_panel.py    # Панель «Соединение»
│   ├── main_window.py   # Главное окно с вкладками
│   ├── split_panel.py   # Панель «Разделение»
│   └── widgets.py       # Переиспользуемые виджеты
└── tests/
    ├── __init__.py
    ├── test_config.py
    ├── test_crypto.py
    ├── test_footer.py
    └── test_steganography.py
```

## Лицензия

MIT
