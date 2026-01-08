# Collection Request Schema System

This module provides a JSON schema format for defining and managing CollectionRequest objects, enabling round-trip export/import and decoupling collection definitions from Python code.

## Overview

The schema system consists of three main components:

- **CollectionRequestExporter**: Exports a CollectionRequest to JSON schema format
- **CollectionRequestBuilder**: Builds a CollectionRequest from JSON schema
- **CollectionSchemaSerializer**: Validates JSON schema structure

## Schema Format

### Basic Structure

```json
{
  "version": "1.0",
  "name": "My Checklist",
  "slug": "my-checklist",
  "description": "Optional description",
  "response_sets": {
    "yes-no": ["Yes", "No"],
    "yes-no-na": ["Yes", "No", "N/A"]
  },
  "sections": [
    {
      "name": "Section Name",
      "slug": "section-name",
      "questions": [...]
    }
  ]
}
```

### Questions

Each question in a section can have the following fields:

```json
{
  "measure_id": "unique-measure-id",
  "text": "Question text displayed to user",
  "type": "multiple-choice",
  "required": true,
  "order": 1,
  "description": "Optional longer description",
  "help_text": "Optional help text shown on request",
  "test_requirement_type": "all-pass",
  "responses": ["Option A", "Option B"],
  "response_set": "yes-no",
  "response_flags": {
    "Option B": {
      "comment_required": true,
      "is_considered_failure": true
    }
  },
  "conditions": [...]
}
```

#### Question Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `measure_id` | string | Yes | - | Unique identifier for the question |
| `text` | string | Yes | - | Question text displayed to user |
| `type` | string | No | "open" | Question type (see below) |
| `required` | boolean | No | true | Whether an answer is required |
| `order` | integer | No | auto | Display order within section |
| `description` | string | No | "" | Additional description text |
| `help_text` | string | No | "" | Help text (hidden until requested) |
| `test_requirement_type` | string | No | "all-pass" | How multiple conditions are evaluated |
| `responses` | array | No | [] | Inline response options |
| `response_set` | string | No | - | Reference to a named response set |
| `response_flags` | object | No | {} | Flags for specific response values |
| `conditions` | array | No | [] | Conditions for showing this question |

#### Question Types

| Type | Description |
|------|-------------|
| `open` | Free-form text input |
| `multiple-choice` | Select from predefined options |
| `integer` | Whole number input |
| `float` | Decimal number input |
| `date` | Date input |
| `cascading-select` | Hierarchical selection |

#### test_requirement_type Values

Controls how multiple conditions on a question are evaluated:

| Value | Description |
|-------|-------------|
| `all-pass` | All conditions must pass (AND logic) - default |
| `one-pass` | At least one condition must pass (OR logic) |
| `all-fail` | All conditions must fail (NONE logic) |

### Response Sets

Response sets allow defining reusable response option lists. A pattern must appear **2 or more times** in the schema to be automatically extracted into a response set during export.

```json
{
  "response_sets": {
    "yes-no": ["Yes", "No"],
    "yes-no-na": ["Yes", "No", "N/A"],
    "pass-fail": ["Pass", "Fail"]
  }
}
```

Questions can reference these sets:

```json
{
  "measure_id": "has-feature",
  "text": "Does the home have this feature?",
  "type": "multiple-choice",
  "response_set": "yes-no"
}
```

### Response Flags

Response flags define special behavior for specific response values:

```json
{
  "response_flags": {
    "No": {
      "comment_required": true,
      "is_considered_failure": true
    },
    "N/A": {
      "document_required": true
    }
  }
}
```

| Flag | Description |
|------|-------------|
| `comment_required` | User must provide a comment when selecting this response |
| `photo_required` | User must attach a photo when selecting this response |
| `document_required` | User must attach a document when selecting this response |
| `is_considered_failure` | This response is considered a failure/deficiency |

### Conditions

Conditions control when a question is displayed. Questions are hidden unless their conditions evaluate to true.

#### Simple Condition (Instrument-based)

Show question based on another question's answer:

```json
{
  "conditions": [
    {
      "type": "instrument",
      "source": "has-solar",
      "match_type": "match",
      "values": ["Yes"]
    }
  ]
}
```

#### Custom Condition Types

Applications can register custom condition types via the `ConditionResolverRegistry`:

```json
{
  "conditions": [
    {
      "type": "simulation",
      "source": "has-hpwh",
      "match_type": "match",
      "values": [true]
    }
  ]
}
```

#### Grouped Conditions (AND logic)

Show question only when ALL rules match:

```json
{
  "conditions": [
    {
      "logic": "all",
      "rules": [
        {
          "type": "instrument",
          "source": "heating-fuel",
          "match_type": "match",
          "values": ["Gas"]
        },
        {
          "type": "instrument",
          "source": "climate-zone",
          "match_type": "match",
          "values": ["4A", "4B", "4C"]
        }
      ]
    }
  ]
}
```

#### Grouped Conditions (OR logic)

Show question when ANY rule matches:

```json
{
  "conditions": [
    {
      "logic": "any",
      "rules": [
        {
          "type": "instrument",
          "source": "heating-type",
          "match_type": "match",
          "values": ["Heat Pump"]
        },
        {
          "type": "instrument",
          "source": "cooling-type",
          "match_type": "match",
          "values": ["Heat Pump"]
        }
      ]
    }
  ]
}
```

#### Condition Logic

| Logic Value | Description |
|-------------|-------------|
| `all` | All rules must match (AND) - default |
| `any` | At least one rule must match (OR) |
| `none` | No rules must match (NOT) |

#### Match Types

| Match Type | Description |
|------------|-------------|
| `match` | Value equals one of the specified values |
| `mismatch` | Value does not equal any of the specified values |
| `one` | At least one value matches |
| `zero` | No values match |
| `any` | Any value present |
| `none` | No value present |
| `greater_than` | Value is greater than specified |
| `less_than` | Value is less than specified |
| `contains` | Value contains the specified string |

## Usage

### Basic Export/Import

```python
from django_input_collection.schema import (
    CollectionRequestExporter,
    CollectionRequestBuilder,
)

# Export a CollectionRequest to dict
exporter = CollectionRequestExporter()
schema = exporter.export(collection_request)

# Export to file
exporter.export_to_file(collection_request, "schema.json")

# Build from dict
builder = CollectionRequestBuilder()
cr = builder.build(schema)

# Build from file
cr = builder.build_from_file("schema.json")

# Update existing CollectionRequest
cr = builder.build(schema, existing_cr=existing_collection_request)
```

### Extending with Custom Condition Types

Applications can register custom condition types for both import (building) and export:

```python
from django_input_collection.schema import (
    register_condition_resolver,
    register_condition_validator,
)

# Register import resolver (schema -> database)
@register_condition_resolver('simulation')
def resolve_simulation(source: str, values: list | None) -> str | None:
    """Return data_getter string or None if unresolved."""
    registry_entry = SimulationConditionRegistry.get_by_slug(source)
    if registry_entry:
        return f"simulation:{registry_entry.resolver_path}"
    return None

# Register export resolver (database -> schema)
@register_condition_resolver('simulation', direction='export')
def export_simulation(path: str) -> str | None:
    """Return slug from resolver path, or None."""
    return resolver_to_slug_cache.get(path)

# Register validator for serializer validation
@register_condition_validator('simulation')
def validate_simulation(source: str, values: list) -> tuple[bool, str | None]:
    """Validate condition source and values. Returns (is_valid, error_message)."""
    registry_entry = SimulationConditionRegistry.get_by_slug(source)
    if not registry_entry:
        return False, f"Unknown simulation condition slug: '{source}'"
    return True, None
```

### Extending with Bound Response Flags

Applications can register a handler for response flags (comment_required, photo_required, etc.):

```python
from django_input_collection.schema import register_bound_response_handler

@register_bound_response_handler()
class AxisBoundResponseHandler:
    @staticmethod
    def create(instrument, suggested_response, flags: dict):
        """Create bound response with flags."""
        AxisBoundSuggestedResponse.objects.create(
            collection_instrument=instrument,
            suggested_response=suggested_response,
            comment_required=flags.get('comment_required', False),
            photo_required=flags.get('photo_required', False),
            document_required=flags.get('document_required', False),
            is_considered_failure=flags.get('is_considered_failure', False),
        )

    @staticmethod
    def export(instrument) -> dict:
        """Export flags for instrument's responses."""
        flags = {}
        for bound in instrument.bound_suggested_responses.all():
            response_flags = {}
            if bound.comment_required:
                response_flags['comment_required'] = True
            if bound.photo_required:
                response_flags['photo_required'] = True
            if bound.document_required:
                response_flags['document_required'] = True
            if bound.is_considered_failure:
                response_flags['is_considered_failure'] = True
            if response_flags:
                flags[bound.suggested_response.data] = response_flags
        return flags
```

## Django Input Collection Models

The schema maps to the following `django_input_collection` models:

| Schema Element | Model |
|----------------|-------|
| CollectionRequest | `CollectionRequest` |
| Section | `CollectionGroup` |
| Question | `CollectionInstrument` |
| Question Type | `CollectionInstrumentType` |
| Response Option | `SuggestedResponse` |
| Response Policy | `ResponsePolicy` |
| Condition | `Condition` |
| Condition Group | `ConditionGroup` |
| Condition Case | `Case` |
| Measure | `Measure` |

## Round-Trip Fidelity

The schema system is designed for round-trip fidelity:

```
CollectionRequest → Export → JSON → Import → CollectionRequest
```

All significant data is preserved through this cycle, including:

- Question text, type, order
- Response options and flags
- Conditions (instrument and custom types)
- Response policies
- Section grouping
