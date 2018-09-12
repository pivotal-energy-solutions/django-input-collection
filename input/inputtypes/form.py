from .base import InputMethod


class FormMethod(InputMethod):
    """ Requests input through an HTML-rendered Django form, returns a dict of cleaned_data. """

    # NOTE: This collects multiple data points for a SINGLE CollectionInstrument, and would
    # therefore potentially expect all data points to be stored in a SINGLE CollectedInput.  A more
    # sophisticated CollectedInput user model would need to be swapped in to handle that.
    # Alternately, data points could be divided and multiple CollectedInputs created for each part
    # if the save() process is built to allow a sane representation of those disparate data points.

    form_class = None


class FormFieldMethod(InputMethod):
    """
    Requests input through an HTML-rendered Django field, returns a single python object
    representing the cleaned result.
    """

    formfield_class = None
