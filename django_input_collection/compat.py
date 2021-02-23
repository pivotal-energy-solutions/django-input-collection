try:
    from collections import UserDict
except ImportError:
    from UserDict import IterableUserDict
    class UserDict(IterableUserDict, object):
        pass
