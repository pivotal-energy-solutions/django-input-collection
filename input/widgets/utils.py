from inspect import isclass

__all__ = ['serialize_widget']


def serialize_widget(widget):
    if isclass(widget):
        widget = widget()
    return {
        '_class': widget.__class__.__name__,
        '_repr': repr(widget),
    }
