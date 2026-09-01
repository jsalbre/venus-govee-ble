from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parent.parent / "version"

try:
    __version__ = _VERSION_FILE.read_text().strip().lstrip("v")
except OSError:
    __version__ = "0.0.0"
