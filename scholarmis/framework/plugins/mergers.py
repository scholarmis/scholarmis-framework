from pathlib import Path
from typing import Protocol
from .metadata import PluginMetadata


class MergeExtension(Protocol):

    def merge(self, existing: PluginMetadata, new: PluginMetadata) -> PluginMetadata:
        pass


class FilesystemFirstMerge(MergeExtension):
    
    def merge(self, existing: PluginMetadata, new: PluginMetadata) -> PluginMetadata:
        if Path(new.source).exists():
            return new
        return existing


class FirstWinsMerge(MergeExtension):
    
    def merge(self, existing: PluginMetadata, new: PluginMetadata) -> PluginMetadata:
        return existing


class LatestMerge(MergeExtension):

    def parse_semver(self, version: str):
        if not version:
            return (0, 0, 0)

        # Remove pre-release or build info
        clean_version = version.split("-", 1)[0].split("+", 1)[0]

        parts = clean_version.split(".")
        major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
        minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        return (major, minor, patch)

    def merge(self, existing: PluginMetadata, new: PluginMetadata) -> PluginMetadata:
        ev = self.parse_semver(existing.version)
        nv = self.parse_semver(new.version)

        return new if nv > ev else existing
