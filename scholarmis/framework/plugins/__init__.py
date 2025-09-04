from scholarmis.framework.plugins.installer import PluginInstaller
from scholarmis.framework.plugins.loader import PluginLoader
from scholarmis.framework.plugins.registry import PluginRegistry
from scholarmis.framework.services import service_registry


plugin_loader = PluginLoader(service_registry)
plugin_installer = PluginInstaller(plugin_loader) 
plugin_registry = PluginRegistry()
