"""Horstmann Smart Logger DNP3 Gateway paketi.

DNP3 protokolu uzerinden Horstmann SN 2.0 cihazlarina baglanip sahadan okunan
sinyalleri RabbitMQ uzerinden catinin tag-engine servisine ileten standalone
gateway servisi.
"""

from pathlib import Path

__all__ = ["__version__"]


def _load_version() -> str:
    version_file = Path(__file__).resolve().parents[2] / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


__version__ = _load_version()
