# Django Input Collection

A flexible Django application for collecting user input through configurable instruments, supporting complex conditional logic, data collection workflows, and JSON schema-based checklist management.

## Features

- **Flexible Input Collection**: Define measures, instruments, and response policies to collect various types of user input
- **Conditional Logic**: Support for parent/child questions with complex condition groups and case matching
- **JSON Schema Support**: Export and import checklist definitions as JSON schemas for easy management and migration
- **REST API**: Full Django REST Framework integration with ViewSet mixins for checklist schema management and consumer endpoints
- **Multiple Response Types**: Support for open text, multiple choice, restricted/unrestricted responses, and more
- **Swappable Models**: Use custom CollectedInput and BoundSuggestedResponse models to extend functionality

## Requirements

- Python 3.12+
- Django 5.2+
- Django REST Framework

## Installation

```bash
pip install django-input-collection
```

Add to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    'django_input_collection',
    'rest_framework',
]
```

## Configuration

Configure swappable models in your settings (optional):

```python
# Use default models
INPUT_COLLECTEDINPUT_MODEL = 'django_input_collection.CollectedInput'
INPUT_BOUNDSUGGESTEDRESPONSE_MODEL = 'django_input_collection.BoundSuggestedResponse'
```

## Core Concepts

### Models

- **Measure**: The underlying identity of a question, independent of phrasing or context
- **CollectionRequest**: A contextual grouping for data collection, with global integrity settings
- **CollectionInstrument**: A specific presentation of a measure with response policies and suggested responses
- **CollectionGroup**: Groupings for organizing instruments into sections
- **ResponsePolicy**: Flags defining response behavior (restrict, multiple, required)
- **SuggestedResponse**: Pre-identified valid responses for instruments
- **CollectedInput**: Stored user responses
- **Condition/ConditionGroup/Case**: Complex conditional logic for showing/hiding instruments

### Condition Types

Instruments can be conditionally displayed based on answers to other instruments:

- `all-pass`: All conditions must be met
- `one-pass`: At least one condition must be met
- `all-fail`: All conditions must fail

### Match Types for Cases

- `any`: Any input allowed
- `none`: No input allowed
- `all-suggested`: All responses must be from suggested values
- `one-suggested`: At least one response from suggested values
- `match`/`mismatch`: Exact match/non-match with data
- `greater_than`/`less_than`: Numeric comparisons
- `contains`/`not-contains`: Substring matching
- `one`/`zero`: Value in/not in a set

## JSON Schema

Export and import checklist definitions as JSON:

```python
from django_input_collection.schema.exporter import CollectionRequestExporter
from django_input_collection.schema.builder import CollectionRequestBuilder

# Export
exporter = CollectionRequestExporter()
schema = exporter.export(collection_request, name="My Checklist")

# Import/Build
builder = CollectionRequestBuilder()
new_collection_request = builder.build(schema)
```

### Schema Structure

```json
{
  "version": "1.0",
  "name": "Checklist Name",
  "sections": [
    {
      "name": "Section Name",
      "questions": [
        {
          "measure_id": "unique-measure-id",
          "text": "Question text",
          "type": "multiple-choice",
          "responses": ["Yes", "No"],
          "response_policy": {
            "restrict": true,
            "multiple": false,
            "required": true
          },
          "conditions": [
            {
              "rules": [
                {
                  "type": "instrument",
                  "source": "parent-measure-id",
                  "match_type": "match",
                  "values": ["Yes"]
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

## REST API Integration

Use the provided mixins to add checklist endpoints to your ViewSets:

```python
from rest_framework.viewsets import ModelViewSet
from django_input_collection.schema.mixins import ChecklistSchemaMixin, ChecklistConsumerMixin

class MyViewSet(ChecklistSchemaMixin, ChecklistConsumerMixin, ModelViewSet):
    def get_collection_request(self, obj):
        return obj.collection_request

    def get_collector(self, obj, user, user_role="rater"):
        return Collector(obj.collection_request, user=user)
```

This adds endpoints:
- `GET/PUT /{pk}/checklist-schema/` - Export/update schema
- `GET /{pk}/checklist/` - Get checklist with answers and progress
- `GET /{pk}/checklist/instruments/` - List all instruments
- `GET /{pk}/checklist/instruments/{id}/` - Get single instrument
- `POST /{pk}/checklist/answers/` - Submit answers

## Development

### Running Tests

```bash
# Install test dependencies
pip install -e ".[test]"

# Run tests with coverage
coverage run
coverage report
```

### Code Quality

```bash
# Format code
black django_input_collection

# Lint
ruff django_input_collection

# Security check
bandit -r django_input_collection
```

## License

Apache License 2.0

## Links

- [GitHub Repository](https://github.com/pivotal-energy-solutions/django-input-collection)
- [Issue Tracker](https://github.com/pivotal-energy-solutions/django-input-collection/issues)
