from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model
from django.forms.models import model_to_dict
from django.utils.functional import Promise
from django.utils.encoding import force_text


class CollectionSpecificationJSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, Model):
            return model_to_dict(o)
        elif isinstance(o, Promise):  # Catch reverse_lazy, among other simple things
            return force_text(o)

        return super(CollectionSpecificationJSONEncoder, self).default(o)
