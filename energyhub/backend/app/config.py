from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv


def _load_env_files() -> None:
    """Carga .env sin asumir una profundidad de ruta concreta.

    En el contenedor el archivo está en /app/app/config.py y no existe
    parents[3]; en local sí. Buscamos hacia arriba y nunca indexamos fuera
    de la lista.
    """
    config_path = Path(__file__).resolve()
    for parent in list(config_path.parents)[:4]:
        candidate = parent / ".env"
        if candidate.is_file():
            load_dotenv(candidate)
            break
    load_dotenv()


_load_env_files()

APP_NAME = "EnergyHub"
APP_VERSION = "0.3.6"
DEFAULT_TIMEZONE = "Europe/Madrid"
GITHUB_REPO_URL = "https://github.com/merchedev/EnergyHub"
CHANGELOG_URL = os.getenv(
    "ENERGYHUB_CHANGELOG_URL",
    "https://raw.githubusercontent.com/merchedev/EnergyHub/main/energyhub/CHANGELOG.md",
)
FULL_CHANGELOG_URL = f"{GITHUB_REPO_URL}/blob/main/energyhub/CHANGELOG.md"


def _read_addon_options() -> dict:
    path = Path("/data/options.json")
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


ADDON_OPTIONS = _read_addon_options()


def _env_or_option(name: str, option: str, default: str) -> str:
    if name in os.environ:
        return os.environ[name]
    value = ADDON_OPTIONS.get(option)
    if value is None:
        return default
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def data_dir() -> Path:
    raw = os.getenv("ENERGYHUB_DATA_DIR")
    if raw:
        path = Path(raw)
    elif Path("/data").exists() and os.getenv("SUPERVISOR_TOKEN"):
        path = Path("/data")
    else:
        path = Path.cwd() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


DATA_DIR = data_dir()
DATABASE_URL = os.getenv("ENERGYHUB_DATABASE_URL", f"sqlite:///{DATA_DIR / 'energyhub.db'}")
STATIC_DIR = os.getenv("ENERGYHUB_STATIC_DIR", "")
DEMO_MODE = _env_or_option("ENERGYHUB_DEMO", "demo_mode", "0") == "1"
DEV_MODE = _env_or_option("ENERGYHUB_DEV", "dev_mode", "0") == "1" or not os.getenv("SUPERVISOR_TOKEN")
LOG_LEVEL = _env_or_option("ENERGYHUB_LOG_LEVEL", "log_level", "info").upper()
PEPE_API_URL = os.getenv(
    "ENERGYHUB_PEPE_API_URL",
    "https://shared-api.pepeenergy.com/prices/electricity/last-month",
)
PEPE_TIMEOUT_SECONDS = float(os.getenv("ENERGYHUB_PEPE_TIMEOUT", "15"))
HA_URL = os.getenv("HA_URL", "").strip()
HA_TOKEN = os.getenv("HA_TOKEN", "").strip()
SUPERVISOR_TOKEN = os.getenv("SUPERVISOR_TOKEN", "").strip()
