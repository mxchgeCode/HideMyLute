# hideMyLute

![](resources/666.jpg)

Утилита для объединения и разделения файлов.

## Установка

Требуется Python >= 3.9.

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

## Запуск

```bash
python -m hideMyLute
```

## Тесты

```bash
pytest hideMyLute/tests/ -v
```

## Сборка

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
```

Результат: `dist\hideMyLute.exe`.

## Лицензия

MIT
