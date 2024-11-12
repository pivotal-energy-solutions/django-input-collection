from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from django_input_collection import collection


class ReadWriteToggleMixin(object):
    def __init__(self, *args, **kwargs):
        context = kwargs.get("context", {})
        write_mode = context.pop("write_mode", False)

        super(ReadWriteToggleMixin, self).__init__(*args, **kwargs)

        if write_mode:
            include_fields = getattr(self.Meta, "include_write", "__all__")
            exclude_fields = getattr(self.Meta, "exclude_write", [])

            if include_fields == "__all__":
                include_fields = list(self.fields.keys())

            if include_fields:
                for name in list(self.fields.keys()):
                    if name not in include_fields:
                        del self.fields[name]

            if exclude_fields:
                for name in exclude_fields:
                    del self.fields[name]


class RegisteredCollectorField(serializers.Field):
    def to_internal_value(self, identifier):
        try:
            return collection.resolve(identifier)
        except KeyError:
            raise ValidationError("Unknown collector reference")
