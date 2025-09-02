import json
import importlib
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Optional
from abc import ABC, abstractmethod
from importlib import metadata
from importlib.metadata import Distribution
from .exceptions import PluginDiscoveryError
from .metadata import PluginMetadata
from .extensions import PluginMetadataExtension
from .mergers import LatestMerge, MergeExtension
from .utils import compute_file_checksum, get_distribution_checksum


logger = logging.getLogger(__name__)


class ModuleResolver:

    @staticmethod
    def from_path(plugin_json_path: Path, installable_path: Path, search_paths: List[Path]) -> str:
        """
        Resolve namespace for filesystem-discovered plugins.

        Rules:
        1. If the plugin has a nested `scholarmis` folder, use it as the root module.
        2. Replace hyphens with underscores for top-level folders.
        3. Fallback to top folder name if no scholarmis folder is found.
        """
        try:
            # Compute relative path to search root
            base = next(sp for sp in search_paths if plugin_json_path.is_relative_to(sp))
            relative = plugin_json_path.parent.relative_to(base)

            # Search for nested 'scholarmis' folder
            parts = list(relative.parts)
            if "scholarmis" in parts:
                scholarmis_index = parts.index("scholarmis")
                module_parts = parts[scholarmis_index:]  # include scholarmis and subfolders
            else:
                # fallback: use top folder, replace hyphens with underscores
                module_parts = [parts[0].replace("-", "_")] if parts else [installable_path.name.replace("-", "_")]

            # Replace any remaining hyphens in nested folders
            module_parts = [module_part.replace("-", "_") for module_part in module_parts]

            return ".".join(module_parts)
        except Exception:
            return installable_path.name.replace("-", "_")

    @staticmethod
    def from_distribution(dist: Distribution, module: ModuleType, pkg_name: str, top_level_txt: Optional[str]) -> str:
        """
        Resolve namespace for installed-package plugins (Package/EntryPoint).
        Priority:
          1. module.__name__ if scholarmis.*
          2. top_level.txt contains scholarmis → scholarmis.suffix
          3. fallback to normalized dist-name
        """
        if module.__name__.startswith("scholarmis."):
            return module.__name__

        if top_level_txt:
            top_packages = [line.strip() for line in top_level_txt.splitlines() if line.strip()]
            if "scholarmis" in top_packages:
                suffix = pkg_name.replace("-", "_").split("_", 1)[-1]
                return f"scholarmis.{suffix}"

        return dist.metadata["Name"].lower().replace("-", "_")



class PluginDiscoverer(ABC):
    """Base class for all discoverers."""

    def __init__(self, extensions: Optional[List[PluginMetadataExtension]] = None):
        self.extensions = extensions or []

    @abstractmethod
    def discover(self) -> List[PluginMetadata]:
        pass

    def add_to_sys_path(self, path: Path) -> None:
        """Add a folder to sys.path if not already present."""
        str_path = str(path.resolve())
        if str_path not in sys.path:
            sys.path.insert(0, str_path)

    def find(self, identifier: str) -> Optional[PluginMetadata]:
        discovered = self.discover()
        for plugin in discovered:
            if (
                plugin.name == identifier
                or plugin.name == identifier
                or plugin.module == identifier
                or str(plugin.source) == identifier
            ):
                return plugin
        return None

    def extend(self, metadata: PluginMetadata) -> PluginMetadata:
        for ext in self.extensions:
            metadata = ext.apply(metadata)
        return metadata



class FileSystemDiscoverer(PluginDiscoverer):
    
    def __init__(self, search_paths: List[Path], extensions: Optional[List[PluginMetadataExtension]] = None):
        super().__init__(extensions)
        self.search_paths = search_paths

    def discover(self) -> List[PluginMetadata]:
        discovered: List[PluginMetadata] = []
        processed_folders = set()

        for base_path in self.search_paths:
            if not base_path.exists():
                continue

            for plugin_json_path in base_path.rglob("plugin.json"):
                try:
                    # Compute top-level plugin folder relative to search root
                    relative_parts = plugin_json_path.relative_to(base_path).parts
                    top_folder_name = relative_parts[0]
                    installable_path = base_path / top_folder_name
                except Exception as e:
                    logger.warning(f"Failed to determine installable path for {plugin_json_path}: {e}")
                    continue

                if installable_path in processed_folders:
                    continue

                # Load plugin metadata
                try:
                    metadata_obj = self.load_metadata(plugin_json_path, installable_path)
                    discovered.append(self.extend(metadata_obj))
                    processed_folders.add(installable_path)
                    logger.info(f"Discovered plugin '{metadata_obj.name}' at {installable_path}")
                except (PluginDiscoveryError, json.JSONDecodeError) as e:
                    logger.warning(f"Failed to load plugin metadata from {plugin_json_path}: {e}")

        return discovered

    def load_metadata(self, plugin_json_path: Path, installable_path: Path) -> PluginMetadata:
        try:
            with open(plugin_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            raise PluginDiscoveryError(f"Failed to parse plugin metadata: {e}") from e
        
        self.add_to_sys_path(installable_path)

        # Ensure source points to the top-level folder
        data["source"] = str(installable_path)
        data["module"] = ModuleResolver.from_path(plugin_json_path, installable_path, self.search_paths)
        return PluginMetadata.from_dict(data)



class PackageDiscoverer(PluginDiscoverer):

    def __init__(self, package_prefix: str = "scholarmis_", extensions: Optional[List[PluginMetadataExtension]] = None):
        super().__init__(extensions)
        self.package_prefix = package_prefix.lower()

    def discover(self) -> List[PluginMetadata]:
        discovered = []

        for dist in metadata.distributions():
            dist_name = dist.metadata["Name"].lower()
            if not dist_name.startswith(self.package_prefix):
                continue

            top_level_txt = dist.read_text("top_level.txt")
            if top_level_txt:
                top_packages = [line.strip() for line in top_level_txt.splitlines() if line.strip()]
            else:
                top_packages = [dist_name.replace("-", "_")]

            for pkg_name in top_packages:
                try:
                    module = importlib.import_module(pkg_name)
                    metadata_obj = self.extract_metadata(dist, module, pkg_name, top_level_txt)
                    discovered.append(self.extend(metadata_obj))
                except ImportError as e:
                    logger.warning(f"Failed to import package {pkg_name}: {e}")

        return discovered

    def extract_metadata(self, dist: Distribution, module: ModuleType, pkg_name: str, top_level_txt: Optional[str]) -> PluginMetadata:
        module_path = Path(module.__file__).parent if hasattr(module, "__file__") else Path("unknown")
        requires = dist.requires or []
        version = dist.version
        pin = getattr(module, "__pin__", None)
        checksum = get_distribution_checksum(dist) or (
            compute_file_checksum(Path(module.__file__)) if hasattr(module, "__file__") else None
        )

        self.add_to_sys_path(module_path)

        return PluginMetadata(
            name=dist.metadata.get("Name"),
            author=dist.metadata.get("Author"),
            author_email=dist.metadata.get("Author-email"),
            source=str(module_path),
            version=version,
            requires=requires,
            pin=pin,
            checksum=checksum,
            module=ModuleResolver.from_distribution(dist, module, pkg_name, top_level_txt),
        )



class EntryPointDiscoverer(PluginDiscoverer):

    def __init__(self, prefix: str = "scholarmis_", extensions: Optional[List[PluginMetadataExtension]] = None):
        super().__init__(extensions)
        self.prefix = prefix.lower()

    def discover(self) -> List[PluginMetadata]:
        discovered: List[PluginMetadata] = []

        for dist in metadata.distributions():
            package_name = dist.metadata["Name"]
            package_name_lower = package_name.lower()

            if not package_name_lower.startswith(self.prefix):
                continue

            top_level_txt = dist.read_text("top_level.txt")
            if top_level_txt:
                top_packages = [line.strip() for line in top_level_txt.splitlines() if line.strip()]
            else:
                top_packages = [package_name.replace("-", "_")]

            for pkg_name in top_packages:
                try:
                    plugin_module = importlib.import_module(pkg_name)
                    metadata_obj = self.extract_metadata(dist, plugin_module, pkg_name, top_level_txt)
                    discovered.append(self.extend(metadata_obj))
                except ImportError as e:
                    logger.warning(f"Failed to import package {pkg_name}: {e}")

        return discovered

    def extract_metadata(self, dist: Distribution, plugin_module: ModuleType, pkg_name: str, top_level_txt: Optional[str]) -> PluginMetadata:
        module_path = Path(plugin_module.__file__).parent if hasattr(plugin_module, "__file__") else Path("unknown")
        requires = dist.requires or []
        version = dist.version
        pin = getattr(plugin_module, "__pin__", None)
        checksum = get_distribution_checksum(dist) or (
            compute_file_checksum(Path(plugin_module.__file__)) if hasattr(plugin_module, "__file__") else None
        )

        self.add_to_sys_path(module_path)

        return PluginMetadata(
            name=dist.metadata.get("Name"),
            author=dist.metadata.get("Author"),
            author_email=dist.metadata.get("Author-email"),
            source=str(module_path),
            version=version,
            requires=requires,
            pin=pin,
            checksum=checksum,
            module=ModuleResolver.from_distribution(dist, plugin_module, pkg_name, top_level_txt),
        )



class CompositeDiscoverer(PluginDiscoverer):
    """
    Runs multiple discoverers, applies extensions, and merges duplicates
    using a pluggable MergeExtension.
    """

    def __init__(self,
        discoverers: List[PluginDiscoverer],
        extensions: Optional[List[PluginMetadataExtension]] = None,
        merge_strategy: Optional[MergeExtension] = None,
    ):
        super().__init__(extensions)
        self.discoverers = discoverers
        self.merge_strategy = merge_strategy or LatestMerge()  # default

    def discover(self) -> List[PluginMetadata]:
        all_plugins: Dict[str, PluginMetadata] = {}

        for discoverer in self.discoverers:
            for plugin in discoverer.discover():
                plugin = self.extend(plugin)

                if plugin.name in all_plugins:
                    existing = all_plugins[plugin.name]
                    merged = self.merge_strategy.merge(existing, plugin)
                    all_plugins[plugin.name] = merged
                else:
                    all_plugins[plugin.name] = plugin

        return list(all_plugins.values())
