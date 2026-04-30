from typing import Any, Dict, Optional


class SeatDataError(Exception):
    def __init__(
        self,
        message: str = "",
        *,
        error_type: Optional[str] = None,
        error_code: Optional[str] = None,
        status_code: Optional[int] = None,
        response_body: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.error_code = error_code
        self.status_code = status_code
        self.response_body = response_body


class SeatDataAuthError(SeatDataError):
    pass


class SeatDataRateLimitError(SeatDataError):
    def __init__(
        self,
        message: str = "",
        *,
        retry_after: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class SeatDataNotFoundError(SeatDataError):
    pass


class SeatDataInvalidRequestError(SeatDataError):
    def __init__(
        self,
        message: str = "",
        *,
        param: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.param = param


class SeatDataSubscriptionError(SeatDataError):
    pass


class SeatDataServerError(SeatDataError):
    pass


class CursorExpiredError(SeatDataInvalidRequestError):
    def __init__(
        self,
        message: str = "",
        *,
        items_yielded: int = 0,
        last_cursor: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.items_yielded = items_yielded
        self.last_cursor = last_cursor


SeatDataException = SeatDataError
AuthenticationError = SeatDataAuthError
RateLimitError = SeatDataRateLimitError
SubscriptionError = SeatDataSubscriptionError
NotFoundError = SeatDataNotFoundError
ServiceUnavailableError = SeatDataServerError
