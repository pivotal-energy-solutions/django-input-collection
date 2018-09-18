from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model
from django.forms.models import model_to_dict


class ModelJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, Model):
            return model_to_dict(obj)
        return super(ModelJSONEncoder, self).default(obj)
