import subprocess
import sys
from typing import Optional
from pathlib import Path
from importlib import metadata


def pip_install(target: str) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", target])


def pip_install_editable(path: Path) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", str(path)])


def pip_install_from_dir(path: Path) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", str(path)])


def pip_upgrade(target: str) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", target])


def pip_uninstall(target: str) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", target])


def pip_show_version(package: str) -> Optional[str]:
    try:
        return metadata.version(package)
    except Exception:
        return None


def pip_list_outdated_json() -> str:
    out = subprocess.check_output([sys.executable, "-m", "pip", "list", "--outdated", "--format", "json"])
    return out.decode("utf-8")
