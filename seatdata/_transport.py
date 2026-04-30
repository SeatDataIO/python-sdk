import asyncio
import random
import time
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

_RETRY_STATUS = {429, 502, 503, 504}
_RETRYABLE_NETWORK_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
)
_BACKOFF_BASE_SECONDS = 0.5
_BACKOFF_CAP_SECONDS = 30.0


def _should_retry(response: Optional["httpx.Response"], exc: Optional[Exception]) -> bool:
    if exc is not None:
        return isinstance(exc, _RETRYABLE_NETWORK_EXCEPTIONS)
    if response is not None:
        return response.status_code in _RETRY_STATUS
    return False


def _sleep_seconds(response: Optional["httpx.Response"], attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(0, int(retry_after))
            except ValueError:
                pass
    return random.uniform(0, min(_BACKOFF_BASE_SECONDS * (2**attempt), _BACKOFF_CAP_SECONDS))


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
    fallback_type = {
        401: "authentication_error",
        404: "not_found",
        429: "rate_limit_error",
    }.get(response.status_code, "server_error")
    try:
        body = response.json()
    except Exception:
        return {
            "error": {
                "type": fallback_type,
                "code": "non_json_response",
                "message": response.text or response.reason_phrase or "",
            }
        }
    if isinstance(body, dict) and isinstance(body.get("error"), str):
        legacy_message = body["error"]
        legacy_type = fallback_type
        if response.status_code == 401 and "subscription" in legacy_message.lower():
            legacy_type = "subscription_required"
        return {
            "error": {
                "type": legacy_type,
                "code": "legacy_string_body",
                "message": legacy_message,
            }
        }
    if not isinstance(body, dict) or "error" not in body or not isinstance(body["error"], dict):
        return {
            "error": {
                "type": fallback_type,
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
        attempts = self._max_retries + 1 if retry_safe else 1
        last_response: Optional[httpx.Response] = None
        for attempt in range(attempts):
            last_response = None
            try:
                response = self._client.request(method, url, params=params, json=json)
            except _RETRYABLE_NETWORK_EXCEPTIONS as e:
                if retry_safe and attempt < attempts - 1:
                    time.sleep(_sleep_seconds(None, attempt))
                    continue
                raise SeatDataServerError(str(e), error_type="server_error")
            last_response = response
            if response.status_code < 400:
                return response.json()
            if retry_safe and attempt < attempts - 1 and _should_retry(response, None):
                time.sleep(_sleep_seconds(response, attempt))
                continue
            _raise_from_response(response)
        if last_response is not None:
            _raise_from_response(last_response)
        raise SeatDataServerError("request failed without response", error_type="server_error")

    def request_text(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        retry_safe: bool = True,
    ) -> str:
        url = self._base_url + path
        attempts = self._max_retries + 1 if retry_safe else 1
        last_response: Optional[httpx.Response] = None
        for attempt in range(attempts):
            last_response = None
            try:
                response = self._client.request(method, url, params=params)
            except _RETRYABLE_NETWORK_EXCEPTIONS as e:
                if retry_safe and attempt < attempts - 1:
                    time.sleep(_sleep_seconds(None, attempt))
                    continue
                raise SeatDataServerError(str(e), error_type="server_error")
            last_response = response
            if response.status_code < 400:
                return response.text
            if retry_safe and attempt < attempts - 1 and _should_retry(response, None):
                time.sleep(_sleep_seconds(response, attempt))
                continue
            _raise_from_response(response)
        if last_response is not None:
            _raise_from_response(last_response)
        raise SeatDataServerError("request failed without response", error_type="server_error")

    def close(self) -> None:
        self._client.close()

    def _ensure_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "User-Agent": _user_agent(),
                },
            )
        return self._async_client

    async def arequest_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        retry_safe: bool = True,
    ) -> Any:
        client = self._ensure_async_client()
        url = self._base_url + path
        attempts = self._max_retries + 1 if retry_safe else 1
        last_response: Optional[httpx.Response] = None
        for attempt in range(attempts):
            last_response = None
            try:
                response = await client.request(method, url, params=params, json=json)
            except _RETRYABLE_NETWORK_EXCEPTIONS as e:
                if retry_safe and attempt < attempts - 1:
                    await asyncio.sleep(_sleep_seconds(None, attempt))
                    continue
                raise SeatDataServerError(str(e), error_type="server_error")
            last_response = response
            if response.status_code < 400:
                return response.json()
            if retry_safe and attempt < attempts - 1 and _should_retry(response, None):
                await asyncio.sleep(_sleep_seconds(response, attempt))
                continue
            _raise_from_response(response)
        if last_response is not None:
            _raise_from_response(last_response)
        raise SeatDataServerError("request failed without response", error_type="server_error")

    async def arequest_text(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        retry_safe: bool = True,
    ) -> str:
        client = self._ensure_async_client()
        url = self._base_url + path
        attempts = self._max_retries + 1 if retry_safe else 1
        last_response: Optional[httpx.Response] = None
        for attempt in range(attempts):
            last_response = None
            try:
                response = await client.request(method, url, params=params)
            except _RETRYABLE_NETWORK_EXCEPTIONS as e:
                if retry_safe and attempt < attempts - 1:
                    await asyncio.sleep(_sleep_seconds(None, attempt))
                    continue
                raise SeatDataServerError(str(e), error_type="server_error")
            last_response = response
            if response.status_code < 400:
                return response.text
            if retry_safe and attempt < attempts - 1 and _should_retry(response, None):
                await asyncio.sleep(_sleep_seconds(response, attempt))
                continue
            _raise_from_response(response)
        if last_response is not None:
            _raise_from_response(last_response)
        raise SeatDataServerError("request failed without response", error_type="server_error")

    async def aclose(self) -> None:
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None
        self._client.close()
