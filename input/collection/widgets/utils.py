from inspect import isclass

__all__ = ['serialize_widget']


def serialize_widget(widget):
    if isclass(widget):
        widget = widget()

    info = widget.serialize()
    info['meta'] = {
        '_class': widget.__class__.__name__,
    }

    return info
