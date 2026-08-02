"""Сборка ресурса версии Windows (VSVersionInfo) для hideMyLute.

Используется PyInstaller-спецификацией hideMyLute.spec (параметр version=),
чтобы исполняемый файл содержал корректную версию и описание (SIG-15).

Импортируется только во время сборки на Windows.
"""

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

from hideMyLute._version import VERSION_STRING

_ver_parts = [int(x) for x in VERSION_STRING.split(".")]
while len(_ver_parts) < 4:
    _ver_parts.append(0)

version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=tuple(_ver_parts),
        prodvers=tuple(_ver_parts),
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "hideMyLute"),
                        StringStruct(
                            "FileDescription",
                            "hideMyLute — стеганография для правдоподобного отрицания",
                        ),
                        StringStruct("FileVersion", VERSION_STRING),
                        StringStruct("InternalName", "hideMyLute"),
                        StringStruct("OriginalFilename", "hideMyLute.exe"),
                        StringStruct("ProductName", "hideMyLute"),
                        StringStruct("ProductVersion", VERSION_STRING),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
    ],
)
