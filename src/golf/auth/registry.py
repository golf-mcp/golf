"""Provider registry system for extensible authentication providers.

This module provides a registry-based dispatch system that allows custom
authentication providers to be added without modifying the core factory code.
"""

from typing import Protocol, TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from fastmcp.server.auth.auth import AuthProvider

from .providers import AuthConfig


class AuthProviderFactory(Protocol):
    """Protocol for auth provider factory functions.

    Custom provider factories must implement this interface to be compatible
    with the registry system.
    """

    def __call__(self, config: AuthConfig) -> "AuthProvider":
        """Create an AuthProvider from configuration.

        Args:
            config: Authentication configuration object

        Returns:
            Configured FastMCP AuthProvider instance

        Raises:
            ValueError: If configuration is invalid
            ImportError: If required dependencies are missing
        """
        ...


class BaseProviderPlugin(ABC):
    """Base class for auth provider plugins.

    Provider plugins can extend this class to provide both configuration
    and factory logic in a single cohesive unit.
    """

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Return the provider type identifier."""
        ...

    @property
    @abstractmethod
    def config_class(self) -> type[AuthConfig]:
        """Return the configuration class for this provider."""
        ...

    @abstractmethod
    def create_provider(self, config: AuthConfig) -> "AuthProvider":
        """Create the auth provider from configuration.

        Args:
            config: Authentication configuration (must be instance of config_class)

        Returns:
            Configured FastMCP AuthProvider instance
        """
        ...

    def validate_config(self, config: AuthConfig) -> None:
        """Validate the configuration before creating provider.

        Override this method to add custom validation logic.
        Default implementation checks config is correct type.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If configuration is invalid
        """
        if not isinstance(config, self.config_class):
            raise ValueError(
                f"Expected {self.config_class.__name__} for {self.provider_type} provider, got {type(config).__name__}"
            )


class AuthProviderRegistry:
    """Registry for authentication provider factories and plugins.

    This registry allows custom authentication providers to be registered
    without modifying the core factory code. Providers can be registered
    either as simple factory functions or as full plugin classes.
    """

    def __init__(self) -> None:
        self._factories: dict[str, AuthProviderFactory] = {}
        self._plugins: dict[str, BaseProviderPlugin] = {}

    def register_factory(self, provider_type: str, factory: AuthProviderFactory) -> None:
        """Register a factory function for a provider type.

        Args:
            provider_type: Unique identifier for the provider type
            factory: Factory function that creates providers

        Raises:
            ValueError: If provider_type is already registered
        """
        if provider_type in self._factories or provider_type in self._plugins:
            raise ValueError(f"Provider type '{provider_type}' is already registered")

        self._factories[provider_type] = factory

    def register_plugin(self, plugin: BaseProviderPlugin) -> None:
        """Register a provider plugin.

        Args:
            plugin: Provider plugin instance

        Raises:
            ValueError: If provider type is already registered
        """
        provider_type = plugin.provider_type
        if provider_type in self._factories or provider_type in self._plugins:
            raise ValueError(f"Provider type '{provider_type}' is already registered")

        self._plugins[provider_type] = plugin

    def unregister(self, provider_type: str) -> None:
        """Unregister a provider type.

        Args:
            provider_type: Provider type to remove

        Raises:
            KeyError: If provider type is not registered
        """
        if provider_type in self._factories:
            del self._factories[provider_type]
        elif provider_type in self._plugins:
            del self._plugins[provider_type]
        else:
            raise KeyError(f"Provider type '{provider_type}' is not registered")

    def get_factory(self, provider_type: str) -> AuthProviderFactory:
        """Get factory function for a provider type.

        Args:
            provider_type: Provider type to look up

        Returns:
            Factory function for the provider type

        Raises:
            KeyError: If provider type is not registered
        """
        # Check factories first
        if provider_type in self._factories:
            return self._factories[provider_type]

        # Check plugins
        if provider_type in self._plugins:
            plugin = self._plugins[provider_type]

            # Wrap plugin method to match factory signature
            def plugin_factory(config: AuthConfig) -> "AuthProvider":
                plugin.validate_config(config)
                return plugin.create_provider(config)

            return plugin_factory

        raise KeyError(f"No provider registered for type '{provider_type}'")

    def create_provider(self, config: AuthConfig) -> "AuthProvider":
        """Create a provider from configuration using the registry.

        Args:
            config: Authentication configuration

        Returns:
            Configured AuthProvider instance

        Raises:
            KeyError: If provider type is not registered
            ValueError: If configuration is invalid
        """
        provider_type = getattr(config, "provider_type", None)
        if not provider_type:
            raise ValueError(f"Configuration {type(config).__name__} missing provider_type attribute")

        factory = self.get_factory(provider_type)
        return factory(config)

    def list_providers(self) -> list[str]:
        """List all registered provider types.

        Returns:
            List of provider type identifiers
        """
        return sorted(list(self._factories.keys()) + list(self._plugins.keys()))

    def is_registered(self, provider_type: str) -> bool:
        """Check if a provider type is registered.

        Args:
            provider_type: Provider type to check

        Returns:
            True if provider type is registered
        """
        return provider_type in self._factories or provider_type in self._plugins


# Global registry instance
_default_registry = AuthProviderRegistry()


def get_provider_registry() -> AuthProviderRegistry:
    """Get the default provider registry.

    Returns:
        Default AuthProviderRegistry instance
    """
    return _default_registry


def register_provider_factory(provider_type: str, factory: AuthProviderFactory) -> None:
    """Register a factory function in the default registry.

    Args:
        provider_type: Unique identifier for the provider type
        factory: Factory function that creates providers
    """
    _default_registry.register_factory(provider_type, factory)


def register_provider_plugin(plugin: BaseProviderPlugin) -> None:
    """Register a provider plugin in the default registry.

    Args:
        plugin: Provider plugin instance
    """
    _default_registry.register_plugin(plugin)


def create_auth_provider_from_registry(config: AuthConfig) -> "AuthProvider":
    """Create an auth provider using the default registry.

    Args:
        config: Authentication configuration

    Returns:
        Configured AuthProvider instance
    """
    return _default_registry.create_provider(config)
