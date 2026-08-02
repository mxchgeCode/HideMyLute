# -*- mode: python ; coding: utf-8 -*-
# Версионируемая спецификация сборки hideMyLute (SIG-11).
# Сборка: pyinstaller hideMyLute.spec
from PyInstaller.utils.hooks import collect_data_files

from version_info import version_info  # noqa: E402

datas = []
datas += collect_data_files('customtkinter')


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='hideMyLute',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                       # SIG-14: без UPX (AV-фолс-позитивы и демультиплексируемость)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=True, # SIG-14: без traceback-диалогов в продакшене
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=version_info,            # SIG-15: версия/описание в свойствах файла
)
