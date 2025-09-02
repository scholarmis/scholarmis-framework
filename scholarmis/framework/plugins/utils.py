import os
import re
import shutil
import subprocess
import sys
import hashlib
import semver # type: ignore
from pathlib import Path
from typing import Optional


def pascal_case(name: str) -> str:
    # Split by underscore or dash
    parts = re.split(r"[._-]", name)
    # Capitalize each part
    return "".join(p.capitalize() for p in parts if p)


def verbose_case(name: str) -> str:
    # Split by underscore or dash
    parts = re.split(r"[._-]", name)
    # Capitalize each part and join with space
    return " ".join(p.capitalize() for p in parts if p)


def ensure_django_installed():
    """Ensure Django is installed, install if missing."""
    try:
        import django  # type: ignore # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "django"])


def get_stub_content(stub_path, **kwargs) -> str:
    """
    Loads a template file and formats it with provided keyword arguments.
    Uses Python's str.format() for placeholders.
    """
    stub_path = Path(stub_path)
    if not stub_path.exists():
        raise FileNotFoundError(f"stub file not found at {stub_path}")

    content = stub_path.read_text(encoding="utf-8")
    return content.format(**kwargs)


def generate_stub(stub_path, output_path, **context):
    """
    Generates a single .py file from a stub template.
    
    Parameters:
    - stub_path: path to the stub file
    - output_path: path to write the resulting file
    - context: placeholders to replace in the stub using str.format()
    """
    stub_path = Path(stub_path)
    output_path = Path(output_path)

    if not stub_path.exists():
        raise FileNotFoundError(f"Stub file not found at {stub_path}")

    # Read stub and replace placeholders
    content = stub_path.read_text(encoding="utf-8")
    rendered = content.format(**context)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write output
    output_path.write_text(rendered, encoding="utf-8")
    return output_path


def generate_stubs(stubs_dir, output_dir, **context):
    """
    Generates .py files from all .stub files in a directory (except __init__.stub).
    Returns a list of generated module names.
    """
    os.makedirs(output_dir, exist_ok=True)
    modules = []

    stub_files = {
        f.replace(".stub", ""): f
        for f in os.listdir(stubs_dir)
        if f.endswith(".stub")
    }

    for module_name, filename in stub_files.items():
        stub_path = Path(stubs_dir) / filename
        output_path = Path(output_dir) / f"{module_name}.py"
        generate_stub(stub_path, output_path, **context)
        modules.append(module_name)

    # Remove generated .py files whose stub no longer exists
    for module_name in modules:
        py_path = Path(output_dir) / f"{module_name}.py"
        if not (Path(stubs_dir) / f"{module_name}.stub").exists() and py_path.exists():
            py_path.unlink()

    return modules


def copy_file(src_path, dest_path):
    """
    Copies a file from src_path to dest_path.
    Ensures that the destination directory exists.
    """
    src_path = Path(src_path)
    dest_path = Path(dest_path)

    if not src_path.exists():
        raise FileNotFoundError(f"Source file not found: {src_path}")

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src_path, dest_path)
    return dest_path


def match_version(version: str, constraint: Optional[str]) -> bool:
    """
    Checks if a version string satisfies a semantic versioning constraint.
    """
    if not constraint:
        return True
    try:
        return semver.match(version, constraint)
    except Exception:
        return version == constraint        


def compare_version(a: str, b: str) -> int:
    """
    Compares two semantic version strings.
    """
    try:
        return semver.compare(a, b)
    except Exception:
        return (a > b) - (a < b)


def compute_file_checksum(file_path: Path) -> str:
    """Compute SHA256 of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return f"sha256:{hasher.hexdigest()}"


def get_distribution_checksum(dist) -> Optional[str]:
    """
    Extract a checksum from RECORD if available.
    Returns the first sha256 entry found, else None.
    """
    dist_info_path = Path(dist.locate_file(""))
    record_file = dist_info_path / "RECORD"

    if not record_file.exists():
        return None

    try:
        with open(record_file, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 2 and parts[1].startswith("sha256="):
                    return parts[1]
    except Exception:
        return None

    return None

