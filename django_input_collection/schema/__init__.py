"""schema: Collection request schema building and export"""

__author__ = "Steven Klass"
__date__ = "01/08/26 02:30 PM"
__copyright__ = "Copyright 2011-2026 Pivotal Energy Solutions. All rights reserved."
__credits__ = ["Steven Klass"]

from .builder import CollectionRequestBuilder
from .exporter import CollectionRequestExporter
from .registry import (
    ConditionResolverRegistry,
    BoundResponseRegistry,
    register_condition_resolver,
    register_bound_response_handler,
)
from .serializers import (
    CollectionSchemaSerializer,
    ChecklistSchemaSerializer,  # Alias for backward compatibility
    ConditionValidatorRegistry,
    register_condition_validator,
)
from .mixins import (
    ChecklistSchemaMixin,
    ChecklistConsumerMixin,
)
from .merged import consumer_payload, merged_checklist_payload, response_flags
from .collisions import (
    COLLISION_FIELDS,
    CollisionReport,
    MeasureCollision,
    MeasureCollisionError,
    MeasureSignature,
    check_measure_collisions,
    find_measure_collisions,
    normalize_flags,
    signatures_for_request,
    signatures_from_schema,
)

__all__ = [
    # Builder and Exporter
    "CollectionRequestBuilder",
    "CollectionRequestExporter",
    # Condition Resolver Registry (for builder/exporter)
    "ConditionResolverRegistry",
    "register_condition_resolver",
    # Bound Response Registry (for response flags)
    "BoundResponseRegistry",
    "register_bound_response_handler",
    # Serializers
    "CollectionSchemaSerializer",
    "ChecklistSchemaSerializer",
    # Condition Validator Registry (for serializers)
    "ConditionValidatorRegistry",
    "register_condition_validator",
    # ViewSet Mixins
    "ChecklistSchemaMixin",
    "ChecklistConsumerMixin",
    # Merged (multi-request) checklist response
    "merged_checklist_payload",
    "consumer_payload",
    "response_flags",
    # Measure-collision validation
    "COLLISION_FIELDS",
    "CollisionReport",
    "MeasureCollision",
    "MeasureCollisionError",
    "MeasureSignature",
    "check_measure_collisions",
    "find_measure_collisions",
    "normalize_flags",
    "signatures_for_request",
    "signatures_from_schema",
]
