import inspect
import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar
from .exceptions import ServiceAlreadyRegisteredError, ServiceResolutionError


class IStartable(ABC):
    """Interface for services that need to be started."""
    @abstractmethod
    def start(self) -> None:
        """Called when the service lifecycle starts (optional)."""
        pass

class IStoppable(ABC):
    """Interface for services that need to be stopped."""
    @abstractmethod
    def stop(self) -> None:
        """Called when the service lifecycle stops (optional)."""
        pass


T = TypeVar("T")
Contract = TypeVar("Contract", bound=object)

# Lifetime constants
LIFETIME_SINGLETON = "singleton"
LIFETIME_SCOPED = "scoped"
LIFETIME_TRANSIENT = "transient"


class ServiceRegistry:
    """
    A robust service registry with dependency injection.
    
    This registry supports:
    - Multiple service lifetimes: singleton, scoped, and transient.
    - Automatic dependency resolution via constructor injection.
    - Lifecycle management for startable and stoppable services.
    - Scoped context management for request-based services.
    - Centralized service lookup and introspection.
    """
    
    def __init__(self):
        # Stores registrations: contract -> (implementation_type, lifetime)
        self._registry: Dict[Type, Tuple[Type, str]] = {}
        
        # Cache for singleton instances
        self._singletons: Dict[Type, Any] = {}
        
        # Tracks singleton instances for ordered lifecycle management
        self._singleton_order: List[Any] = []
        
        # Stack for managing nested scopes. Each scope is a dict: contract -> instance
        self._scope_stack: List[Dict[Type, Any]] = []

        self._logger = logging.getLogger(self.__class__.__name__)

    # --- Registration ---

    def register(self, contract: Type[Contract], implementation: Type[Contract], lifetime: str = LIFETIME_SINGLETON) -> None:
        """
        Registers a service implementation for a given contract.
        
        Args:
            contract: The abstract service interface or class.
            implementation: The concrete class that implements the contract.
            lifetime: The service's lifetime strategy ('singleton', 'scoped', 'transient').
            
        Raises:
            ServiceAlreadyRegisteredError: If the contract is already registered.
            TypeError: If the implementation doesn't subclass the contract.
            ValueError: If an invalid lifetime is provided.
        """
        if contract in self._registry:
            raise ServiceAlreadyRegisteredError(f"Contract {contract.__name__} already registered.")
        
        if not inspect.isclass(implementation):
            raise TypeError("Implementation must be a class/type.")
            
        if not issubclass(implementation, contract):
            # This check enforces type safety at registration time.
            raise TypeError(f"Implementation {implementation.__name__} must inherit from contract {contract.__name__}.")

        if lifetime not in {LIFETIME_SINGLETON, LIFETIME_SCOPED, LIFETIME_TRANSIENT}:
            raise ValueError("Invalid lifetime. Use 'singleton', 'scoped' or 'transient'.")

        self._registry[contract] = (implementation, lifetime)
        self._logger.info(f"Registered {contract.__name__} -> {implementation.__name__} ({lifetime})")

    def register_singleton(self, contract: Type[Contract], implementation: Type[Contract]) -> None:
        """Convenience method to register a singleton service."""
        self.register(contract, implementation, LIFETIME_SINGLETON)

    def register_transient(self, contract: Type[Contract], implementation: Type[Contract]) -> None:
        """Convenience method to register a transient service."""
        self.register(contract, implementation, LIFETIME_TRANSIENT)

    def register_scoped(self, contract: Type[Contract], implementation: Type[Contract]) -> None:
        """Convenience method to register a scoped service."""
        self.register(contract, implementation, LIFETIME_SCOPED)

    # --- Service Resolution ---

    def get(self, contract: Type[Contract]) -> Contract:
        """
        Resolves and returns a service instance based on its contract.
        
        This method is the core of the registry. It handles caching for singletons,
        scoped instance management within a scope, and creating new instances
        for transient services.
        
        Args:
            contract: The type of the service to retrieve.
            
        Returns:
            An instance of the requested service.
            
        Raises:
            ServiceResolutionError: If the service is not registered or a dependency fails to resolve.
        """
        if contract not in self._registry:
            raise ServiceResolutionError(f"No registration found for contract: {contract.__name__}")
        
        implementation, lifetime = self._registry[contract]
        
        if lifetime == LIFETIME_SINGLETON:
            if contract not in self._singletons:
                instance = self._instantiate(implementation)
                self._singletons[contract] = instance
                self._singleton_order.append(instance) # Track for shutdown
            return self._singletons[contract]
            
        elif lifetime == LIFETIME_SCOPED:
            scope = self._get_current_scope()
            if scope is None:
                self._logger.warning(
                    f"Attempted to resolve scoped service {contract.__name__} outside of a scope. "
                    "A new transient instance will be created. Use 'with registry.create_scope():'."
                )
                return self._instantiate(implementation)
            
            if contract not in scope:
                instance = self._instantiate(implementation)
                scope[contract] = instance
            return scope[contract]
            
        elif lifetime == LIFETIME_TRANSIENT:
            return self._instantiate(implementation)
        
        raise ServiceResolutionError(f"Unknown lifetime '{lifetime}' for {contract.__name__}.")
        
    def _instantiate(self, implementation: Type) -> Any:
        """
        Recursively resolves dependencies and instantiates a service.
        
        This private method handles the heavy lifting of Dependency Injection.
        """
        try:
            # Use inspect.signature to get constructor's parameters
            sig = inspect.signature(implementation.__init__)
            params = sig.parameters
        except (ValueError, AttributeError):
            # No __init__ method or trivial init, so no dependencies to resolve
            return implementation()

        dependencies: Dict[str, Any] = {}
        for name, param in params.items():
            if name == 'self':
                continue
            
            if param.annotation is inspect.Parameter.empty:
                raise ServiceResolutionError(
                    f"Missing type hint for dependency '{name}' in {implementation.__name__}'s constructor."
                )
            
            # Recursive call to resolve dependencies
            dependencies[name] = self.get(param.annotation)
            
        return implementation(**dependencies)

    def _get_current_scope(self) -> Optional[Dict[Type, Any]]:
        """Returns the current scope from the stack, if one exists."""
        return self._scope_stack[-1] if self._scope_stack else None

    @contextmanager
    def create_scope(self):
        """
        Context manager for a service scope.
        
        Services with a 'scoped' lifetime will be resolved and cached within this
        context and destroyed on exit.
        """
        scope: Dict[Type, Any] = {}
        self._scope_stack.append(scope)
        try:
            self._logger.debug("Scope created.")
            yield
        finally:
            self._logger.debug("Scope exiting, stopping scoped services...")
            # Stop scoped instances in reverse order of creation
            for instance in reversed(list(scope.values())):
                try:
                    if isinstance(instance, IStoppable):
                        instance.stop()
                except Exception as exc:
                    self._logger.exception(f"Error stopping scoped instance {instance.__class__.__name__}: {exc}")
            
            self._scope_stack.pop()
            self._logger.debug("Scope destroyed.")

    # --- Lifecycle Management ---

    def start_singletons(self) -> None:
        """
        Starts all singleton services that implement IStartable.
        
        This should be called once during application startup.
        """
        self._logger.info("Starting singleton services...")
        # Force instantiation of all singletons to ensure start() is called
        for contract, (impl, lifetime) in self._registry.items():
            if lifetime == LIFETIME_SINGLETON and contract not in self._singletons:
                self.get(contract)
                
        for inst in self._singleton_order:
            if isinstance(inst, IStartable):
                try:
                    inst.start()
                    self._logger.info(f"Started service: {inst.__class__.__name__}")
                except Exception as exc:
                    self._logger.error(f"Failed to start singleton {inst.__class__.__name__}.")
                    raise

    def stop_singletons(self) -> None:
        """
        Stops all singleton services that implement IStoppable.
        
        This should be called once during application shutdown. Services are stopped
        in the reverse order of their creation.
        """
        self._logger.info("Stopping singleton services...")
        for inst in reversed(self._singleton_order):
            if isinstance(inst, IStoppable):
                try:
                    inst.stop()
                    self._logger.info(f"Stopped service: {inst.__class__.__name__}")
                except Exception as exc:
                    self._logger.error(f"Failed to stop singleton {inst.__class__.__name__}.")
                    raise


service_registry = ServiceRegistry()