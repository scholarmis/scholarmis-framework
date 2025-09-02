import hashlib
import logging
from pathlib import Path
from typing import Dict, Optional, Protocol
from .metadata import PluginMetadata


logger = logging.getLogger(__name__)


class PluginMetadataExtension(Protocol):
    """Extensions that enrich or transform discovered PluginMetadata."""

    def apply(self, metadata: PluginMetadata) -> PluginMetadata:
        pass


class ChecksumExtension(PluginMetadataExtension):
    """Ensures checksum is computed if missing."""
    def apply(self, metadata: PluginMetadata) -> PluginMetadata:
        if not metadata.checksum and metadata.source and Path(metadata.source).exists():
            # compute SHA256 of all .py files in the source folder
            hasher = hashlib.sha256()
            for file in Path(metadata.source).rglob("*.py"):
                hasher.update(file.read_bytes())
            object.__setattr__(metadata, "checksum", f"sha256:{hasher.hexdigest()}")
        return metadata


class PinExtension(PluginMetadataExtension):
    """Smart pinning: manual override > module/json > auto version"""
    def __init__(self, manual_pins: Optional[Dict[str, str]] = None):
        self.manual_pins = manual_pins or {}

    def apply(self, metadata: PluginMetadata) -> PluginMetadata:
        if metadata.name in self.manual_pins:
            object.__setattr__(metadata, "pin", self.manual_pins[metadata.name])
        elif metadata.version:
            object.__setattr__(metadata, "pin", f"=={metadata.version}")
        return metadata


class ValidationExtension(PluginMetadataExtension):
    """Ensures required fields exist, applies fallbacks."""
    def __init__(self, defaults: Optional[Dict[str, str]] = None):
        self.defaults = defaults or {"version": "unknown", "source": "unknown"}

    def apply(self, metadata: PluginMetadata) -> PluginMetadata:
        errors = []
        if not metadata.name:
            errors.append("Missing name")
            object.__setattr__(metadata, "name", "unnamed-plugin")
        if not metadata.version:
            errors.append("Missing version")
            object.__setattr__(metadata, "version", self.defaults["version"])
        if not metadata.source:
            object.__setattr__(metadata, "source", self.defaults["source"])
        if metadata.requires is None:
            object.__setattr__(metadata, "requires", [])
        if errors:
            logger.warning(f"Validation issues for {metadata.name}: {', '.join(errors)}")
        return metadata