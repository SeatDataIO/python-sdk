class SeatDataException(Exception):
    pass


class AuthenticationError(SeatDataException):
    pass


class RateLimitError(SeatDataException):
    pass
