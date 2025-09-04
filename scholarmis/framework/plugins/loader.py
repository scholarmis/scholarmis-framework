import importlib
import inspect
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
from scholarmis.framework.exceptions import ServiceAlreadyRegisteredError
from scholarmis.framework.services import ServiceRegistry
from .discoverers import CompositeDiscoverer, EntryPointDiscoverer, FileSystemDiscoverer, PackageDiscoverer
from .extensions import ChecksumExtension, PinExtension, ValidationExtension
from .exceptions import PluginDependencyError, PluginValidationError
from .metadata import PluginMetadata
from .lockfile import LockFile
from .validators import ChecksumValidator, DependencyValidator


logger = logging.getLogger(__name__)


class PluginLoader:
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.loaded_plugins: Dict[str, PluginMetadata] = {}

        self.base_dir = Path.cwd()
        self.plugin_dir = self.base_dir / ".plugins"
        self.plugin_dir.mkdir(parents=True, exist_ok=True)

        self.lock_file = LockFile(self.base_dir / "plugins.lock")

        self.dependency_validator = DependencyValidator()
        self.checksum_validator = ChecksumValidator(self.lock_file)

        # Initialize composite discoverer with extensions and semver merge
        self.discoverer = CompositeDiscoverer(
            discoverers=[
                FileSystemDiscoverer([self.plugin_dir]),
                PackageDiscoverer(),
                EntryPointDiscoverer(),
            ],
            extensions=[
                ChecksumExtension(),
                PinExtension(),
                ValidationExtension(),
            ]
        )

    def discover_plugins(self) -> List[PluginMetadata]:
        return self.discoverer.discover()
    
    def discover_plugin(self, identifier: str) -> Optional[PluginMetadata]:
        # Normalize identifier if it’s a path
        id_path = Path(identifier).resolve() if Path(identifier).exists() else None

        plugin = self.discoverer.find(identifier)
        if plugin:
            return plugin
        
        discovered = self.discoverer.discover()

        # If identifier is a path, try matching source path exactly
        if id_path:
            for plugin in discovered:
                plugin_source = Path(plugin.source).resolve()
                if plugin_source == id_path:
                    return plugin

        # fallback: attempt partial name match (zip stem, folder name)
        for plugin in discovered:
            if identifier.lower() in (plugin.name.lower(), plugin.module.lower(), plugin.source.lower()):
                return plugin

        return None

    def validate_plugin(self, plugin: PluginMetadata) -> bool:
        try:
            dependency_valid = self.dependency_validator.validate(plugin, self.loaded_plugins)
            checksum_valid = self.checksum_validator.validate(plugin)
            return (dependency_valid and checksum_valid)
        except PluginValidationError as e:
            logger.error(f"Plugin {plugin.name} failed validation: {e}")
            return False

    def topo_sort(self, plugins: List[PluginMetadata]) -> List[PluginMetadata]:
        plugin_map = {plugin.name: plugin for plugin in plugins}
        graph = {plugin.name: set() for plugin in plugins}
        for plugin in plugins:
            for dep in plugin.requires:
                dep_name, _ = self.dependency_validator.parse_dependency(dep)
                if dep_name in plugin_map:
                    graph[plugin.name].add(dep_name)

        in_degree = {name: 0 for name in graph}
        for deps in graph.values():
            for dep in deps:
                in_degree[dep] += 1

        queue = [name for name, degree in in_degree.items() if degree == 0]
        sorted_plugins = []

        while queue:
            name = queue.pop(0)
            sorted_plugins.append(plugin_map[name])
            for dep_name, deps in graph.items():
                if name in deps:
                    in_degree[dep_name] -= 1
                    if in_degree[dep_name] == 0:
                        queue.append(dep_name)

        if len(sorted_plugins) != len(plugins):
            remaining = set(plugin_map.keys()) - {plugin.name for plugin in sorted_plugins}
            raise PluginDependencyError(f"Circular dependency detected among: {remaining}")
        return sorted_plugins

    def load_plugins(self) -> None:
        discovered = self.discover_plugins()
        ordered = self.topo_sort(discovered)
        for plugin in ordered:
            self.load_plugin(plugin)
        self.service_registry.start_singletons()

    def load_plugin(self, plugin: PluginMetadata):
        if plugin.name in self.loaded_plugins:
            return

        if not self.validate_plugin(plugin):
            logger.warning(f"Plugin {plugin.name} failed validation and will not be loaded.")
            return

        # Attempt standard import first
        try:
            module = importlib.import_module(plugin.module)
            self._register_plugin(plugin, module)
        except ModuleNotFoundError:
            self._fallback_load(plugin)

    def _fallback_load(self, plugin: PluginMetadata):
        try:
            fs_discoverer = FileSystemDiscoverer([self.plugin_dir])
            fs_plugin = fs_discoverer.find(plugin.name)
            if fs_plugin:
                plugin_path = str(fs_plugin.source)
                if plugin_path not in sys.path:
                    sys.path.insert(0, plugin_path)  # Temporarily add plugin path
                try:
                    module = importlib.import_module(fs_plugin.module) 
                    self._register_plugin(fs_plugin, module)
                finally:
                    if plugin_path in sys.path:
                        sys.path.remove(plugin_path)
        except Exception as e2:
            logger.error(f"Failed to load plugin {plugin.name} from plugins directory: {e2}")

    def _register_plugin(self, plugin: PluginMetadata, module: Any):
        self.register_services(module)
        self.loaded_plugins[plugin.name] = plugin
        logger.info(f"Plugin {plugin.name} loaded successfully from plugins directory.")

    def unload_plugin(self, plugin_name: str):
        if plugin_name not in self.loaded_plugins:
            return
        plugin = self.loaded_plugins.pop(plugin_name)
        self.unregister_services(plugin)
        if plugin.module in sys.modules:
            del sys.modules[plugin.module]

    def start_all_services(self):
        """Delegate lifecycle start to ServiceRegistry"""
        self.service_registry.start_singletons()

    def stop_all_services(self):
        """Delegate lifecycle stop to ServiceRegistry"""
        self.service_registry.start_singletons()

    def register_services(self, plugin_module: Any):
        """
        Scans a loaded plugin module for contracts and their implementations
        and registers them with the ServiceRegistry.
        """
        for name, obj in inspect.getmembers(plugin_module, inspect.isclass):
            if inspect.isabstract(obj):
                # We found a contract (an ABC)
                contract: Type = obj
                try:
                    # Look for a concrete implementation with the same name, without 'I' prefix
                    # e.g., 'IUserService' -> 'UserService'
                    impl_name = name[1:] if name.startswith("I") else name
                    implementation: Type = getattr(plugin_module, impl_name)
                    
                    # We can use a convention to determine lifetime, or let the plugin specify
                    lifetime = getattr(implementation, '__lifetime__', 'singleton')
                    
                    self.service_registry.register(contract, implementation, lifetime)
                    logger.info(f"Auto-registered service {implementation.__name__} for contract {contract.__name__}.")
                except (AttributeError, TypeError, ServiceAlreadyRegisteredError) as e:
                    logger.warning(f"Failed to auto-register service for contract {contract.__name__}: {e}")

    def unregister_services(self, plugin: PluginMetadata):
        """
        Unregisters services provided by the plugin from the ServiceRegistry.
        This is a placeholder, as the registry needs to manage unregistration.
        """
        logger.warning(f"Unregistration of services for plugin {plugin.name} is not fully implemented.")


   