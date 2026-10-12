class CollectorException(Exception):
    pass


class CollectorRegistrationException(CollectorException):
    message = "Collector cannot be registered."


class ResolverException(Exception):
    pass


class ResolverRegistrationException(ResolverException):
    message = "Resolver cannot be registered."


class UnknownRepeatSource(CollectorException):
    message = "Repeat group count source has no resolver in this collector."
