import swapper

__all__ = ['get_input_model']

def get_input_model():
    return swapper.load_model('input', 'CollectedInput')
