import re
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Dict, List, Optional
from .utils import verbose_case


@dataclass
class DjangoAppConfig:
    class_name: str
    module_name: str
    module_label: str
    verbose_name: str

    def to_dict(self) -> dict:
        data = asdict(self)
        return data


@dataclass
class PluginConfig:
    name: str
    version: str
    author: str
    author_email: str
    license: str
    official: bool
    editable: bool
    output_dir: Path
    repo_name: Optional[str] = None
    pkg_name: Optional[str] = None

    @property
    def verbose_name(self):
        return verbose_case(self.pkg_name)

    def to_dict(self) -> dict:
        data = asdict(self)
        # Convert Path objects to strings
        for f in fields(self):
            if isinstance(data[f.name], Path):
                data[f.name] = str(data[f.name])
        return data

    
@dataclass(frozen=True)
class PluginMetadata:
    name: str
    source: str
    module: str
    version: str = "unknown"
    author: Optional[str] = None
    author_email: Optional[str] = None
    requires: List[str] = field(default_factory=list)
    pin: Optional[str] = None
    checksum: Optional[str] = None
    official: Optional[bool] = None

    def __post_init__(self):
        # Auto-detect official only if the flag is None
        if self.official is None:
            is_official = bool(
                re.match(r"^scholarmis([_-]|$)", self.name, re.IGNORECASE)
            )
            object.__setattr__(self, "official", is_official)

        # Enforce requires as a list (immutable safety)
        if self.requires is None:
            object.__setattr__(self, "requires", [])

    @property
    def pkg_label(self) -> str:
        """Return a normalized package label (safe identifier)."""
        return self.name.replace("-", "_")

    @property
    def pkg_path(self) -> Path:
        """Return Path object for the source location."""
        return Path(self.source)

    def to_dict(self) -> dict:
        """Convert metadata to a JSON-safe dictionary."""
        return {
            "name": self.name,
            "source": str(self.source),
            "module": str(self.module),
            "version": self.version,
            "author": self.author,
            "author_email": self.author_email,
            "requires": list(self.requires),  # copy for safety
            "pin": self.pin,
            "checksum": self.checksum,
            "official": self.official,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'PluginMetadata':
        return cls(
            name=data.get("name", ""),
            source=str(data.get("source", "")),
            module=str(data.get("module", "")),
            version=data.get("version", "unknown"),
            author=data.get("author", None),
            author_email=data.get("author_email", None),
            requires=data.get("requires", []),
            pin=data.get("pin", None),
            checksum=data.get("checksum", None),
            official=data.get("official", None), 
        )
