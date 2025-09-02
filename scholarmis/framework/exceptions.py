class ServiceResolutionError(Exception):
    """Raised when a service or one of its dependencies cannot be resolved."""
    pass

class ServiceAlreadyRegisteredError(Exception):
    """Raised when attempting to register a contract twice."""
    pass