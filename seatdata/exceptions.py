class SeatDataException(Exception):
    pass


class AuthenticationError(SeatDataException):
    pass


class RateLimitError(SeatDataException):
    pass


class SubscriptionError(SeatDataException):
    pass


class NotFoundError(SeatDataException):
    pass


class ServiceUnavailableError(SeatDataException):
    pass
