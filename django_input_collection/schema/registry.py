"""registry.py: Pluggable registries for schema extension points"""

__author__ = "Steven Klass"
__date__ = "01/08/26 02:30 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

import logging
from typing import Callable, Any

log = logging.getLogger(__name__)


class ConditionResolverRegistry:
    """
    Registry for condition resolvers that translate schema conditions to data_getter strings.

    Allows applications to register custom condition types beyond the default 'instrument'.

    Usage:
        # Register a simulation condition resolver
        @register_condition_resolver('simulation')
        def resolve_simulation(source: str, values: list | None) -> str | None:
            '''Return data_getter string or None if unresolved.'''
            registry_entry = SimulationConditionRegistry.get_by_slug(source)
            if registry_entry:
                return f"simulation:{registry_entry.resolver_path}"
            return None

        # Register an exporter reverse-resolver
        @register_condition_resolver('simulation', direction='export')
        def export_simulation(path: str) -> str | None:
            '''Return slug from resolver path, or None.'''
            return slug_cache.get(path)
    """

    _import_resolvers: dict[str, Callable[[str, list | None], str | None]] = {}
    _export_resolvers: dict[str, Callable[[str], str | None]] = {}

    @classmethod
    def register(
        cls,
        condition_type: str,
        resolver: Callable,
        direction: str = "import",
    ):
        """
        Register a resolver for a condition type.

        Args:
            condition_type: The condition type (e.g., 'simulation', 'custom')
            resolver: Callable that resolves source to data_getter (import) or path to slug (export)
            direction: 'import' (schema->db) or 'export' (db->schema)
        """
        if direction == "import":
            cls._import_resolvers[condition_type] = resolver
        elif direction == "export":
            cls._export_resolvers[condition_type] = resolver
        else:
            raise ValueError(f"Invalid direction: {direction}. Use 'import' or 'export'.")

    @classmethod
    def resolve_import(
        cls, condition_type: str, source: str, values: list | None = None
    ) -> str | None:
        """
        Resolve a condition type and source to a data_getter string.

        Args:
            condition_type: The condition type from schema (e.g., 'instrument', 'simulation')
            source: The source identifier (e.g., measure_id, slug)
            values: Optional list of values for type inference

        Returns:
            data_getter string or None if unresolved
        """
        # Built-in instrument type
        if condition_type == "instrument":
            return f"instrument:{source}"

        # Check registered resolvers
        resolver = cls._import_resolvers.get(condition_type)
        if resolver:
            return resolver(source, values)

        log.warning(f"No resolver registered for condition type: {condition_type}")
        return None

    @classmethod
    def resolve_export(cls, condition_type: str, path: str) -> str | None:
        """
        Reverse-resolve a data_getter path to schema source.

        Args:
            condition_type: The condition type (e.g., 'simulation')
            path: The data_getter path to reverse resolve

        Returns:
            Schema source (e.g., slug) or None to use path as-is
        """
        resolver = cls._export_resolvers.get(condition_type)
        if resolver:
            return resolver(path)
        return None

    @classmethod
    def get_registered_types(cls) -> set[str]:
        """Return all registered condition types."""
        return set(cls._import_resolvers.keys()) | {"instrument"}


class BoundResponseRegistry:
    """
    Registry for bound response handlers that manage response flags.

    Allows applications to register custom handlers for creating and exporting
    bound suggested responses with flags (comment_required, photo_required, etc.).

    Usage:
        @register_bound_response_handler()
        class AxisBoundResponseHandler:
            @staticmethod
            def create(instrument, suggested_response, flags: dict):
                '''Create bound response with flags.'''
                AxisBoundSuggestedResponse.objects.create(
                    collection_instrument=instrument,
                    suggested_response=suggested_response,
                    comment_required=flags.get('comment_required', False),
                    ...
                )

            @staticmethod
            def export(instrument) -> dict:
                '''Export flags for instrument's responses.'''
                flags = {}
                for bound in instrument.bound_suggested_responses.all():
                    response_flags = {}
                    if bound.comment_required:
                        response_flags['comment_required'] = True
                    ...
                    if response_flags:
                        flags[bound.suggested_response.data] = response_flags
                return flags
    """

    _handler: Any = None

    @classmethod
    def register(cls, handler):
        """
        Register a bound response handler.

        Args:
            handler: Object with create() and export() methods
        """
        cls._handler = handler

    @classmethod
    def create(cls, instrument, suggested_response, flags: dict):
        """
        Create a bound suggested response with flags.

        Falls back to just adding response to instrument if no handler registered.
        """
        if cls._handler:
            cls._handler.create(instrument, suggested_response, flags)
        else:
            # Default: just add to many-to-many, no flags
            instrument.suggested_responses.add(suggested_response)

    @classmethod
    def export(cls, instrument) -> dict:
        """
        Export response flags for an instrument.

        Returns empty dict if no handler registered.
        """
        if cls._handler:
            return cls._handler.export(instrument)
        return {}

    @classmethod
    def has_handler(cls) -> bool:
        """Check if a handler is registered."""
        return cls._handler is not None


def register_condition_resolver(condition_type: str, direction: str = "import"):
    """
    Decorator to register a condition resolver.

    Args:
        condition_type: The condition type to handle
        direction: 'import' or 'export'

    Usage:
        @register_condition_resolver('simulation')
        def resolve_simulation(source, values):
            ...

        @register_condition_resolver('simulation', direction='export')
        def export_simulation(path):
            ...
    """

    def decorator(func):
        ConditionResolverRegistry.register(condition_type, func, direction)
        return func

    return decorator


def register_bound_response_handler():
    """
    Decorator to register a bound response handler class.

    Usage:
        @register_bound_response_handler()
        class MyBoundResponseHandler:
            @staticmethod
            def create(instrument, suggested_response, flags):
                ...

            @staticmethod
            def export(instrument):
                ...
    """

    def decorator(cls):
        BoundResponseRegistry.register(cls)
        return cls

    return decorator
