# Сборка автономного исполняемого файла hideMyLute (PyInstaller).
# Единственный поддерживаемый способ сборки — версионируемая спецификация
# hideMyLute.spec (SIG-11, MIN-08).
#
# Использование:
#   powershell -ExecutionPolicy Bypass -File scripts\build.ps1
#
# Результат: dist\hideMyLute.exe

$ErrorActionPreference = "Stop"

Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==> Устанавливаю dev-зависимости (если нужно)..."
python -m pip install -r requirements-dev.txt

Write-Host "==> Запускаю тесты..."
python -m pytest hideMyLute/tests/ -q

if ($LASTEXITCODE -ne 0) {
    Write-Error "Тесты не прошли — сборка прервана."
}

Write-Host "==> Сборка PyInstaller (hideMyLute.spec)..."
python -m PyInstaller --noconfirm --clean hideMyLute.spec

if ($LASTEXITCODE -ne 0) {
    Write-Error "Сборка завершилась с ошибкой."
}

Write-Host "==> Готово: dist\hideMyLute.exe"
