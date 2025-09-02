import re
import click # type: ignore


def validate_name(name: str) -> str:
    if not re.match(r"^[A-Za-z0-9_\-]+$", name):
        raise click.BadParameter("Name can only contain letters, numbers, dashes, and underscores.")
    return name


def validate_version(version: str) -> str:
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        raise click.BadParameter("Version must follow semantic versioning (e.g., 0.1.0).")
    return version


def validate_email(email: str) -> str:
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise click.BadParameter("Invalid email format.")
    return email