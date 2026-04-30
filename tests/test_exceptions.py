import pytest

from seatdata.exceptions import (
    SeatDataError,
    SeatDataAuthError,
    SeatDataRateLimitError,
    SeatDataNotFoundError,
    SeatDataInvalidRequestError,
    SeatDataSubscriptionError,
    SeatDataServerError,
    CursorExpiredError,
    SeatDataException,
    AuthenticationError,
    RateLimitError,
    SubscriptionError,
    NotFoundError,
    ServiceUnavailableError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_base(self):
        for cls in [
            SeatDataAuthError,
            SeatDataRateLimitError,
            SeatDataNotFoundError,
            SeatDataInvalidRequestError,
            SeatDataSubscriptionError,
            SeatDataServerError,
            CursorExpiredError,
        ]:
            assert issubclass(cls, SeatDataError)

    def test_cursor_expired_inherits_invalid_request(self):
        assert issubclass(CursorExpiredError, SeatDataInvalidRequestError)

    def test_legacy_aliases_are_same_class(self):
        assert SeatDataException is SeatDataError
        assert AuthenticationError is SeatDataAuthError
        assert RateLimitError is SeatDataRateLimitError
        assert SubscriptionError is SeatDataSubscriptionError
        assert NotFoundError is SeatDataNotFoundError
        assert ServiceUnavailableError is SeatDataServerError

    def test_rate_limit_error_carries_retry_after(self):
        err = SeatDataRateLimitError("rate limited", retry_after=60)
        assert err.retry_after == 60

    def test_rate_limit_error_default_retry_after_is_none(self):
        err = SeatDataRateLimitError("rate limited")
        assert err.retry_after is None

    def test_invalid_request_error_carries_param_and_code(self):
        err = SeatDataInvalidRequestError("bad", param="event_id", error_code="missing_parameter")
        assert err.param == "event_id"
        assert err.error_code == "missing_parameter"

    def test_cursor_expired_carries_iteration_state(self):
        err = CursorExpiredError("cursor expired", items_yielded=42, last_cursor="abc123")
        assert err.items_yielded == 42
        assert err.last_cursor == "abc123"

    def test_base_error_carries_diagnostic_fields(self):
        err = SeatDataAuthError(
            "bad key",
            error_type="authentication_error",
            error_code="invalid_api_key",
            status_code=401,
            response_body={"error": {"type": "authentication_error"}},
        )
        assert err.error_type == "authentication_error"
        assert err.error_code == "invalid_api_key"
        assert err.status_code == 401
        assert err.response_body == {"error": {"type": "authentication_error"}}
