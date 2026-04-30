import httpx
import pytest
import respx

from seatdata._transport import _Transport
from seatdata.exceptions import (
    CursorExpiredError,
    SeatDataAuthError,
    SeatDataInvalidRequestError,
    SeatDataNotFoundError,
    SeatDataRateLimitError,
    SeatDataServerError,
    SeatDataSubscriptionError,
)


@pytest.fixture
def transport():
    t = _Transport(
        api_key="a" * 64,
        base_url="https://seatdata.io",
        timeout=10,
        max_retries=0,
    )
    yield t
    t.close()


@respx.mock
def test_request_json_returns_parsed_body(transport):
    respx.get("https://seatdata.io/api/v1/account").mock(
        return_value=httpx.Response(200, json={"user_id": 1, "email": "x@y.z"})
    )
    result = transport.request_json("GET", "/api/v1/account")
    assert result == {"user_id": 1, "email": "x@y.z"}


@respx.mock
def test_request_json_sends_bearer_auth(transport):
    route = respx.get("https://seatdata.io/api/v1/account").mock(
        return_value=httpx.Response(200, json={})
    )
    transport.request_json("GET", "/api/v1/account")
    sent = route.calls.last.request
    assert sent.headers["authorization"] == f"Bearer {'a' * 64}"


@respx.mock
def test_request_json_sends_user_agent(transport):
    route = respx.get("https://seatdata.io/api/v1/account").mock(
        return_value=httpx.Response(200, json={})
    )
    transport.request_json("GET", "/api/v1/account")
    ua = route.calls.last.request.headers["user-agent"]
    assert ua.startswith("seatdata-python/")
    assert "httpx/" in ua


@respx.mock
def test_request_json_returns_envelope_for_list_endpoints(transport):
    envelope = {"data": [1, 2, 3], "has_more": False, "next_cursor": None}
    respx.get("https://seatdata.io/api/v1/events/search").mock(
        return_value=httpx.Response(200, json=envelope)
    )
    result = transport.request_json("GET", "/api/v1/events/search")
    assert result == envelope


@respx.mock
def test_request_json_passes_params(transport):
    route = respx.get("https://seatdata.io/api/v1/events/search").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    transport.request_json("GET", "/api/v1/events/search", params={"event_name": "Taylor"})
    assert route.calls.last.request.url.params["event_name"] == "Taylor"


@respx.mock
def test_request_json_passes_json_body(transport):
    import json as json_mod

    route = respx.post("https://seatdata.io/api/v0.4/events/event-request-add").mock(
        return_value=httpx.Response(202, json={"job_id": "x"})
    )
    transport.request_json("POST", "/api/v0.4/events/event-request-add", json={"search_query": "X"})
    body = json_mod.loads(route.calls.last.request.content)
    assert body == {"search_query": "X"}


class TestErrorMapping:
    @respx.mock
    def test_400_invalid_request(self, transport):
        respx.get("https://seatdata.io/api/v1/x").mock(
            return_value=httpx.Response(
                400,
                json={
                    "error": {
                        "type": "invalid_request",
                        "code": "missing_parameter",
                        "message": "event_id is required",
                        "param": "event_id",
                    }
                },
            )
        )
        with pytest.raises(SeatDataInvalidRequestError) as exc_info:
            transport.request_json("GET", "/api/v1/x")
        assert exc_info.value.param == "event_id"
        assert exc_info.value.error_code == "missing_parameter"
        assert exc_info.value.status_code == 400

    @respx.mock
    def test_400_invalid_cursor_maps_to_cursor_expired(self, transport):
        respx.get("https://seatdata.io/api/v1/x").mock(
            return_value=httpx.Response(
                400,
                json={
                    "error": {
                        "type": "invalid_request",
                        "code": "invalid_cursor",
                        "message": "cursor expired",
                    }
                },
            )
        )
        with pytest.raises(CursorExpiredError):
            transport.request_json("GET", "/api/v1/x")

    @respx.mock
    def test_401_authentication_error(self, transport):
        respx.get("https://seatdata.io/api/v1/x").mock(
            return_value=httpx.Response(
                401,
                json={
                    "error": {
                        "type": "authentication_error",
                        "code": "invalid_api_key",
                        "message": "bad key",
                    }
                },
            )
        )
        with pytest.raises(SeatDataAuthError):
            transport.request_json("GET", "/api/v1/x")

    @respx.mock
    def test_401_subscription_required(self, transport):
        respx.get("https://seatdata.io/api/v1/x").mock(
            return_value=httpx.Response(
                401,
                json={
                    "error": {
                        "type": "subscription_required",
                        "code": "no_active_plan",
                        "message": "no plan",
                    }
                },
            )
        )
        with pytest.raises(SeatDataSubscriptionError):
            transport.request_json("GET", "/api/v1/x")

    @respx.mock
    def test_404_not_found(self, transport):
        respx.get("https://seatdata.io/api/v1/x").mock(
            return_value=httpx.Response(
                404,
                json={
                    "error": {
                        "type": "not_found",
                        "code": "event_not_found",
                        "message": "missing",
                    }
                },
            )
        )
        with pytest.raises(SeatDataNotFoundError):
            transport.request_json("GET", "/api/v1/x")

    @respx.mock
    def test_429_rate_limit_with_retry_after_header(self, transport):
        respx.get("https://seatdata.io/api/v1/x").mock(
            return_value=httpx.Response(
                429,
                headers={"Retry-After": "60"},
                json={
                    "error": {
                        "type": "rate_limit_error",
                        "code": "rate_limited",
                        "message": "too many",
                    }
                },
            )
        )
        with pytest.raises(SeatDataRateLimitError) as exc_info:
            transport.request_json("GET", "/api/v1/x")
        assert exc_info.value.retry_after == 60

    @respx.mock
    def test_429_plain_text_v0x(self, transport):
        respx.get("https://seatdata.io/api/v0.3/salesdata/get").mock(
            return_value=httpx.Response(429, text="Too Many Requests")
        )
        with pytest.raises(SeatDataRateLimitError):
            transport.request_json("GET", "/api/v0.3/salesdata/get")

    @respx.mock
    def test_500_server_error(self, transport):
        respx.get("https://seatdata.io/api/v1/x").mock(
            return_value=httpx.Response(
                500,
                json={
                    "error": {
                        "type": "server_error",
                        "code": "internal",
                        "message": "boom",
                    }
                },
            )
        )
        with pytest.raises(SeatDataServerError):
            transport.request_json("GET", "/api/v1/x")

    @respx.mock
    def test_5xx_non_json_body(self, transport):
        respx.get("https://seatdata.io/api/v1/x").mock(
            return_value=httpx.Response(502, text="<html>Bad Gateway</html>")
        )
        with pytest.raises(SeatDataServerError) as exc_info:
            transport.request_json("GET", "/api/v1/x")
        assert "Bad Gateway" in exc_info.value.message
