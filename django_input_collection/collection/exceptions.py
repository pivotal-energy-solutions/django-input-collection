class CollectorException(Exception):
    pass


class CollectorRegistrationException(CollectorException):
    message = "Collector cannot be registered."
