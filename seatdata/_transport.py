from typing import Any, Dict, Optional

import httpx

from .exceptions import (
    CursorExpiredError,
    SeatDataAuthError,
    SeatDataError,
    SeatDataInvalidRequestError,
    SeatDataNotFoundError,
    SeatDataRateLimitError,
    SeatDataServerError,
    SeatDataSubscriptionError,
)

try:
    from importlib.metadata import PackageNotFoundError, version as _pkg_version
except ImportError:
    from importlib_metadata import PackageNotFoundError, version as _pkg_version  # type: ignore


def _sdk_version() -> str:
    try:
        return _pkg_version("seatdata-sdk")
    except PackageNotFoundError:
        return "0.0.0+unknown"


def _user_agent() -> str:
    return f"seatdata-python/{_sdk_version()} httpx/{httpx.__version__}"


_ERROR_TYPE_MAP = {
    "authentication_error": SeatDataAuthError,
    "subscription_required": SeatDataSubscriptionError,
    "invalid_request": SeatDataInvalidRequestError,
    "not_found": SeatDataNotFoundError,
    "rate_limit_error": SeatDataRateLimitError,
    "server_error": SeatDataServerError,
}


def _parse_error_body(response: "httpx.Response") -> Dict[str, Any]:
    try:
        body = response.json()
    except Exception:
        return {
            "error": {
                "type": "rate_limit_error" if response.status_code == 429 else "server_error",
                "code": "non_json_response",
                "message": response.text or response.reason_phrase or "",
            }
        }
    if not isinstance(body, dict) or "error" not in body or not isinstance(body["error"], dict):
        return {
            "error": {
                "type": "rate_limit_error" if response.status_code == 429 else "server_error",
                "code": "non_envelope_response",
                "message": response.text or "",
            }
        }
    return body


def _raise_from_response(response: "httpx.Response") -> None:
    body = _parse_error_body(response)
    err = body["error"]
    err_type = err.get("type", "server_error")
    err_code = err.get("code")
    message = err.get("message", "")

    if err_type == "invalid_request" and err_code == "invalid_cursor":
        raise CursorExpiredError(
            message,
            error_code=err_code,
            error_type=err_type,
            status_code=response.status_code,
            response_body=body,
        )

    cls = _ERROR_TYPE_MAP.get(err_type, SeatDataError)
    kwargs: Dict[str, Any] = {
        "error_type": err_type,
        "error_code": err_code,
        "status_code": response.status_code,
        "response_body": body,
    }
    if cls is SeatDataInvalidRequestError:
        kwargs["param"] = err.get("param")
    if cls is SeatDataRateLimitError:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                kwargs["retry_after"] = int(retry_after)
            except ValueError:
                kwargs["retry_after"] = None
    raise cls(message, **kwargs)


class _Transport:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://seatdata.io",
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": _user_agent(),
            },
        )
        self._async_client: Optional[httpx.AsyncClient] = None

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        retry_safe: bool = True,
    ) -> Any:
        url = self._base_url + path
        response = self._client.request(method, url, params=params, json=json)
        if response.status_code >= 400:
            _raise_from_response(response)
        return response.json()

    def close(self) -> None:
        self._client.close()
        if self._async_client is not None:
            pass
