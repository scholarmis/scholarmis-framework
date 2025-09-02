from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple
from .exceptions import PluginDependencyError
from .lockfile import LockFile
from .metadata import PluginMetadata
from .utils import match_version


class PluginValidator(ABC):

    @abstractmethod
    def validate(self, plugin: PluginMetadata, loaded_plugins: Dict[str, PluginMetadata]) -> bool:
        pass


class DependencyValidator(PluginValidator):
    """
    Validates plugin dependencies using semantic versioning (self-contained, no external library).
    """

    def validate(self, plugin: PluginMetadata, loaded_plugins: Dict[str, PluginMetadata]) -> bool:
        for dep in plugin.requires:
            dep_name, dep_version = self.parse_dependency(dep)
            if dep_name not in loaded_plugins:
                raise PluginDependencyError(f"Plugin {plugin.name} requires missing plugin: {dep_name}")

            installed_version = loaded_plugins[dep_name].version
            if installed_version != "unknown" and dep_version and not match_version(installed_version, dep_version):
                raise PluginDependencyError(
                    f"Plugin {plugin.name} requires {dep_name} with version {dep_version}, "
                    f"but found incompatible version {installed_version}"
                )
        return True

    def parse_dependency(self, dep: str) -> Tuple[str, Optional[str]]:
        # Simple parsing: "plugin_name >=1.2.3"
        parts = dep.strip().split(" ")
        if len(parts) > 1:
            return parts[0], "".join(parts[1:])
        return dep, None


class ChecksumValidator(PluginValidator):

    def __init__(self, lock_file: LockFile):
        self.lock_file = lock_file

    def validate(self, plugin: PluginMetadata) -> bool:
        locked_plugin = self.lock_file.get_plugin(plugin.name)
        stored_checksum = locked_plugin.get("checksum")
        if not stored_checksum:
            return False
        return plugin.checksum == stored_checksum