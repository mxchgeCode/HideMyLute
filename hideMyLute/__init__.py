"""hideMyLute — инструмент стеганографии для правдоподобного отрицания.

Скрывает зашифрованный контейнер внутри файла-носителя с
использованием зашифрованного футера для метаданных.
"""

from ._version import VERSION_STRING as __version__

__all__ = [
    "__version__",
    "config",
    "crypto",
    "exceptions",
    "footer",
    "logging_config",
    "steganography",
    "worker",
]
