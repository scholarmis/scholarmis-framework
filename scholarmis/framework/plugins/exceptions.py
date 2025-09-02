class PluginError(Exception):
    """Base exception for all plugin-related errors."""
    pass

class PluginDiscoveryError(PluginError):
    """Raised when plugin discovery fails."""
    pass

class PluginLoadError(PluginError):
    """Raised when a plugin fails to load."""
    pass

class PluginDependencyError(PluginLoadError):
    """Raised when plugin dependencies cannot be resolved."""
    pass

class PluginValidationError(PluginLoadError):
    """Raised when a plugin fails validation."""
    pass
