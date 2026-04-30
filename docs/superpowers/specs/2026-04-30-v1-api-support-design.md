# SeatData Python SDK — v1 API Support (v1.0.0)

**Status:** Draft
**Date:** 2026-04-30
**Branch:** `feat/v1-api-support`
**Target version:** `seatdata-sdk` v1.0.0

## 1. Goal

Add support for the SeatData v1 REST API surface (Stripe-style envelopes, cursor pagination, Bearer auth, ISO-8601 timestamps) to the official Python SDK while keeping all existing v0.x endpoints functional. Ship a synchronous and an asynchronous client together. Default new code paths to v1; expose v0.x endpoints as legacy.

## 2. Scope

### In scope

- Four new v1 endpoints: `account`, `usage`, `events/search`, `events/{event_id}/stats`.
- Envelope handling (single-resource and list).
- Cursor-based auto-pagination via iterators, plus explicit page-at-a-time accessors.
- Typed exception hierarchy mapped from the v1 `error.type` field, with `retry_after` exposed structurally on rate-limit errors and `items_yielded`/`last_cursor` exposed on cursor-expiry errors.
- Retry/backoff with full jitter, honoring `Retry-After`.
- TypedDicts for v1 response shapes.
- A timestamp parsing helper (`parse_timestamp`).
- Synchronous and asynchronous clients sharing one transport core.
- Migration of HTTP layer from `requests` to `httpx` (keeps Python 3.8+ compatibility).
- Bearer auth applied uniformly to v0.x and v1 requests.
- `search_events()` repointed to v1 GET; legacy v0.3.1 POST kept as `search_events_legacy()` with `DeprecationWarning`.
- Renames of v0.x request helpers to Pythonic names, keeping deprecated aliases:
  - `event_request_add` → `create_event_request`
  - `event_request_status` → `get_event_request_status`

### Out of scope (deferred or never)

- Webhooks, GraphQL, streaming responses, API key management endpoints (none on the server).
- Reading `X-RateLimit-Remaining` headers (server does not yet emit them).
- Caching server-advertised rate limits on the client (would mislead users with stale data).
- Validating or rewriting v0.x return shapes (`Dict[str, Any]` stays).
- Datetime objects inside TypedDicts (would break `json.dumps` round-trips).

## 3. Decisions Locked In

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Flat client; v1 takes canonical method names | Matches existing SDK style; no namespace ceremony for ~10 methods |
| 2 | Sync + async ship together (`SeatDataClient`, `AsyncSeatDataClient`) | Brief calls out dashboard/FastAPI users explicitly |
| 3 | TypedDicts for v1; v0.x stays untyped | Dict-compatible, zero runtime cost, no migration friction |
| 4 | Iterator pattern (`iter_*` + `*_page`) | Stripe/OpenAI convention; predictable type hints; no surprise full-corpus pulls |
| 5 | v1.0.0 with `search_events_legacy()` shim | Clean v1 surface with explicit opt-out for one release |
| 6 | `max_retries=3`, full-jitter exponential backoff | Industry-standard defaults |
| 7 | Bearer auth for all requests | v0.x server accepts it; one consistent code path |
| 8 | Python 3.8+ retained | Add `httpx>=0.27`, `typing_extensions>=4.0`; drop `requests` |

## 4. Module Layout

```
seatdata/
├── __init__.py            # Public exports
├── client.py              # SeatDataClient (sync) — thin facade
├── async_client.py        # AsyncSeatDataClient — thin facade
├── _transport.py          # Shared transport: URL building, headers,
│                          # envelope unwrap, error mapping, retry/backoff.
│                          # Houses both sync and async request methods.
├── exceptions.py          # New hierarchy + legacy aliases
├── pagination.py          # PageIterator + AsyncPageIterator
├── types.py               # TypedDicts + parse_timestamp helper
└── _version.py            # Optional: holds fallback version string
```

### Why one `_transport.py` instead of split sync/async files

The shared logic — URL building, header injection, envelope unwrapping, error-envelope-to-exception mapping, retry math — is the bulk of the module. Splitting into `_transport_sync.py` + `_transport_async.py` + `_transport_base.py` would add inheritance scaffolding for code that is naturally co-located. The one cost is import-time: `httpx.AsyncClient` is referenced even for sync-only users. Mitigation: the `httpx.AsyncClient` instance is lazily created on first async call (not in `__init__`), so sync-only programs never instantiate it. The `httpx` package itself is imported either way, which is unavoidable.

## 5. Public API

### 5.1. Constructors

```python
from seatdata import SeatDataClient, AsyncSeatDataClient

client = SeatDataClient(
    api_key="...",                      # 64-char hex; required
    base_url="https://seatdata.io",     # override for staging/tests
    timeout=30,                          # seconds; passed to httpx
    max_retries=3,                       # 0 disables auto-retry
)

async with AsyncSeatDataClient(api_key="...") as aclient:
    ...
```

Both clients support context-manager use (`with` / `async with`) and an explicit `close()` / `aclose()`. Sync `SeatDataClient` also accepts `__enter__`/`__exit__` to preserve current behavior.

### 5.2. Sync method surface

| Method | Endpoint | Returns | Paid? |
|--------|----------|---------|-------|
| `get_account()` | `GET /v1/account` | `AccountResponse` | Free |
| `get_usage()` | `GET /v1/usage` | `UsageResponse` | Free |
| `search_events(...)` | `GET /v1/events/search` | `List[EventSearchItem]` (one page) | Free |
| `search_events_page(starting_after=None, limit=None, **filters)` | `GET /v1/events/search` | `EventSearchPage` (envelope) | Free |
| `iter_search_events(**filters)` | `GET /v1/events/search` (auto) | `Iterator[EventSearchItem]` | Free |
| `get_event_stats(event_id, starting_after=None, ...)` | `GET /v1/events/{id}/stats` | `EventStatsPage` envelope (first page also includes `available_zones`, `total_count`) | Paid (first page only, per freshness rule) |
| `iter_event_stats(event_id, ...)` | `GET /v1/events/{id}/stats` (auto) | `Iterator[EventStatsSnapshot]` | Paid (first page only, per freshness rule) |
| `get_sales_data(event_id=..., event_id_sh=...)` | `GET /v0.3/salesdata/get` | `List[Dict[str, Any]]` | Paid (v0.x) |
| `get_listings(event_id=..., event_id_sh=...)` | `GET /v0.1.1/listings/get` | `Dict[str, Any]` | Paid (v0.x) |
| `download_daily_csv(date=None)` | `GET /v0.5/daily-csv/download` | `str` (CSV body) | Paid (v0.x) |
| `create_event_request(search_query)` | `POST /v0.4/events/event-request-add` | `Dict[str, Any]` | v0.x |
| `get_event_request_status(job_id)` | `GET /v0.4/events/event-request-status/{job_id}/` | `Dict[str, Any]` | v0.x |
| `search_events_legacy(...)` | `POST /v0.3.1/events/search` | `List[Dict[str, Any]]` | Free; emits `DeprecationWarning` |
| `event_request_add(...)` | (deprecated alias for `create_event_request`) | — | Emits `DeprecationWarning` |
| `event_request_status(...)` | (deprecated alias for `get_event_request_status`) | — | Emits `DeprecationWarning` |

### 5.3. Async method surface

`AsyncSeatDataClient` exposes the same names, all `async def`. Iterators become async iterators (use `async for`).

### 5.4. Iterator semantics

Each `iter_*` method returns a `PageIterator[T]` (sync) or `AsyncPageIterator[T]` (async). Iterators:

- Auto-fetch the next page when the current page is exhausted, using `next_cursor`.
- Stop when `has_more` is `False`.
- Expose `current_cursor: Optional[str]` as a property — the cursor of the last successfully fetched page. Useful for checkpointing.
- Do NOT implement `__len__`. `total_count` is endpoint-dependent and only present on the first page; a cached length would mislead.
- Propagate transport exceptions (auth, rate-limit, server errors) when they occur during fetch.
- Raise `CursorExpiredError` (subclass of `SeatDataError`) if a 400 with `error.code == "invalid_cursor"` (or equivalent) is returned mid-iteration. The exception carries `items_yielded: int` and `last_cursor: Optional[str]` so the caller can resume from the next `*_page` call.

### 5.5. Public exports (`seatdata/__init__.py`)

```python
from .client import SeatDataClient
from .async_client import AsyncSeatDataClient
from .exceptions import (
    SeatDataError,
    SeatDataAuthError,
    SeatDataRateLimitError,
    SeatDataNotFoundError,
    SeatDataInvalidRequestError,
    SeatDataSubscriptionError,
    SeatDataServerError,
    CursorExpiredError,
    # Legacy aliases (preserved):
    SeatDataException,
    AuthenticationError,
    RateLimitError,
    SubscriptionError,
    NotFoundError,
    ServiceUnavailableError,
)
from . import types

__version__ = "1.0.0"
```

`types` is a submodule, so users access TypedDicts as `seatdata.types.AccountResponse`, etc.

## 6. TypedDicts (`seatdata/types.py`)

All optional fields use `typing_extensions.NotRequired` for Python 3.8–3.10 compatibility (resolves to `typing.NotRequired` on 3.11+). All collection annotations use the `typing` module forms (`Dict`, `List`) rather than the PEP 585 builtin generics (`dict`, `list`), since the latter are illegal as runtime base types on Python 3.8. Modules using collection generics inside function bodies / locals can use `from __future__ import annotations` to keep code uniform.

### 6.1. Response shapes

```python
from typing import Dict, List, Optional
from typing_extensions import NotRequired, TypedDict

class RateLimitInfo(TypedDict):
    limit: int
    window_seconds: int

class Plan(TypedDict):
    id: str
    name: str
    status: str
    billing_period_start: Optional[str]   # ISO-8601 or None
    billing_period_end: Optional[str]
    renews_at: Optional[str]

class AccountResponse(TypedDict):
    user_id: int
    email: str
    company: NotRequired[str]
    plans: List[Plan]
    rate_limits: Dict[str, RateLimitInfo]   # str-keyed; concrete keys per spec

class UsageTotals(TypedDict):
    api_calls: int
    events_searched: int
    salesdata_pulls: int
    listings_pulls: int
    stats_pulls: int
    daily_csv_downloads: int

class UsageByEndpoint(TypedDict):
    endpoint: str
    count: int

class UsageResponse(TypedDict):
    period_start: str   # ISO-8601
    period_end: str     # ISO-8601
    totals: UsageTotals
    by_endpoint: List[UsageByEndpoint]

class EventSearchItem(TypedDict):
    event_id: int
    event_name: str
    event_date: str            # YYYY-MM-DD (server provides date-only here)
    event_time: NotRequired[str]
    tm_event_id: NotRequired[Optional[str]]
    days_on_seatdata: int
    first_seen_date: str
    venue_name: str
    venue_city: str
    venue_state: str
    venue_country_code: NotRequired[Optional[str]]
    venue_country: NotRequired[Optional[str]]
    venue_lat: NotRequired[Optional[float]]
    venue_lng: NotRequired[Optional[float]]
    venue_slug: NotRequired[Optional[str]]
    venue_tm_id: NotRequired[Optional[str]]
    std_event_id: NotRequired[Optional[int]]
    std_venue_id: NotRequired[Optional[int]]
    performer: NotRequired[Optional[str]]
    event_type: NotRequired[Optional[str]]
    tour_name: NotRequired[Optional[str]]

class EventSearchPage(TypedDict):
    data: List[EventSearchItem]
    has_more: bool
    next_cursor: Optional[str]

class EventStatsZone(TypedDict):
    zone_name: str
    avg_price: float
    median_price: float
    get_in: float
    get_in_qty2plus: float

class EventStatsSnapshot(TypedDict):
    timestamp: str   # ISO-8601 with Z
    total_listings_all: int
    total_listings_active: int
    listing_fill_rate: float
    avg_price: float
    median_price: float
    get_in: float
    get_in_qty2plus: float
    zones: List[EventStatsZone]

class EventStatsPage(TypedDict):
    event_id: int
    data: List[EventStatsSnapshot]
    has_more: bool
    next_cursor: Optional[str]
    available_zones: NotRequired[List[str]]   # first page only
    total_count: NotRequired[int]              # first page only

class ErrorEnvelopeBody(TypedDict):
    type: str
    code: str
    message: str
    param: NotRequired[str]

class ErrorEnvelope(TypedDict):
    error: ErrorEnvelopeBody
```

### 6.2. Helpers

```python
from datetime import datetime

def parse_timestamp(ts: str) -> datetime:
    """Parse an ISO-8601 'Z'-suffixed UTC timestamp to a timezone-aware datetime."""
    # Implementation uses datetime.fromisoformat after stripping/normalizing Z
    # Python 3.11+ accepts Z natively; older versions need the replace('Z', '+00:00') shim.
```

The helper exists so users have one obvious way to parse server timestamps. Timestamps stay as strings in the TypedDicts so `json.dumps(response)` round-trips cleanly.

## 7. Exception Hierarchy (`seatdata/exceptions.py`)

```
SeatDataError                                (base; "Error" suffix is the new convention)
├── SeatDataAuthError                        # error.type == "authentication_error"
├── SeatDataRateLimitError                   # error.type == "rate_limit_error" (HTTP 429)
│       .retry_after: Optional[int]          # parsed from Retry-After header
├── SeatDataNotFoundError                    # error.type == "not_found"
├── SeatDataInvalidRequestError              # error.type == "invalid_request"
│       .param: Optional[str]                # field name when server provides it
│       .code: Optional[str]                 # machine-readable subtype
├── SeatDataSubscriptionError                # error.type == "subscription_required"
├── SeatDataServerError                      # error.type == "server_error" or 5xx without envelope
└── CursorExpiredError(SeatDataInvalidRequestError)
        .items_yielded: int                  # how many items the iterator emitted before the error
        .last_cursor: Optional[str]          # cursor used for the failed page
```

Every typed exception holds `.error_type: str`, `.error_code: Optional[str]`, `.message: str`, `.status_code: int`, and `.response_body: Optional[dict]` for debugging.

### Legacy aliases preserved

```python
SeatDataException = SeatDataError
AuthenticationError = SeatDataAuthError
RateLimitError = SeatDataRateLimitError
SubscriptionError = SeatDataSubscriptionError
NotFoundError = SeatDataNotFoundError
ServiceUnavailableError = SeatDataServerError
```

Existing user code catching these names continues to work.

### Mapping from server `error.type`

| Server `error.type` | HTTP | Exception |
|---|---|---|
| `authentication_error` | 401 | `SeatDataAuthError` |
| `subscription_required` | 401 / 402 | `SeatDataSubscriptionError` |
| `invalid_request` | 400 / 422 | `SeatDataInvalidRequestError` |
| `invalid_request` w/ `code == "invalid_cursor"` | 400 | `CursorExpiredError` (only when raised from inside iterator) |
| `not_found` | 404 | `SeatDataNotFoundError` |
| `rate_limit_error` | 429 | `SeatDataRateLimitError` |
| `server_error` | 5xx | `SeatDataServerError` |
| (no envelope, plain text) | 429 | `SeatDataRateLimitError` (covers v0.x plain-text response) |
| (no envelope, plain text) | 5xx | `SeatDataServerError` |

## 8. Transport Layer (`seatdata/_transport.py`)

### 8.1. Public-to-this-module surface

```python
class _Transport:
    def __init__(self, api_key: str, base_url: str, timeout: int, max_retries: int) -> None: ...

    # Sync
    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        retry_safe: bool = True,
    ) -> Any: ...

    def request_text(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        retry_safe: bool = True,
    ) -> str: ...

    # Async (mirror methods)
    async def arequest_json(self, ...) -> Any: ...
    async def arequest_text(self, ...) -> str: ...

    def close(self) -> None: ...
    async def aclose(self) -> None: ...
```

### 8.2. Behavior

- **Headers:** Always sets `Authorization: Bearer <api_key>`. Always sets `User-Agent: seatdata-python/<version> httpx/<httpx_version>`, with `<version>` resolved via `importlib.metadata.version("seatdata-sdk")` and a `_version.py` fallback if metadata lookup fails (e.g., editable installs without metadata).
- **URL building:** `base_url.rstrip("/") + path`. Path passed in already contains the API prefix (e.g., `/api/v1/account`).
- **`request_json` response handling:** On 2xx, return `response.json()` verbatim — the parsed body, whatever shape it has. Single-resource endpoints (`/v1/account`, `/v1/usage`) return their resource dict directly per the v1 spec, so no unwrapping is needed. List endpoints return the envelope dict (`{"data": [...], "has_more": ..., "next_cursor": ...}`) and the calling client method extracts `data` itself when it wants items only. On non-2xx, parse the body, map the error envelope to a typed exception, and raise.
- **Error parsing:** On non-2xx, try `response.json()`; if decode fails, fall back to `{"error": {"type": "server_error", "code": "non_json_response", "message": response.text}}`. If the parsed body lacks the expected `error` envelope, treat it as `server_error` with the raw body in `message`. This covers v0.x plain-text 429s and unexpected gateway HTML.
- **`request_text`:** Returns the response body as a string on 2xx. On non-2xx, parses the body defensively (try JSON, fall back to raw text) and raises the mapped exception. Used only by `download_daily_csv`.
- **Retry policy:**
  - Triggers: HTTP 429, 502, 503, 504, and `httpx.ConnectError` / `httpx.ReadTimeout` / `httpx.RemoteProtocolError`.
  - Skipped when `retry_safe=False` (used by `create_event_request` only).
  - Backoff: full jitter — `random.uniform(0, min(0.5 * 2 ** attempt, 30.0))` seconds.
  - Retry-After: when present and parseable as a non-negative integer, sleep for that many seconds (no jitter applied to server-directed waits).
  - Max attempts: `max_retries + 1` (default 4 total).
  - On exhaustion: raise the typed exception from the last attempt. For 429s, the raised `SeatDataRateLimitError` carries `retry_after` from the final response.
- **Lazy async client init:** `httpx.AsyncClient` is constructed on first call to `arequest_*`, not at `__init__`. Stored on `self._async_client`. Sync-only consumers never trigger its creation.

## 9. Pagination Layer (`seatdata/pagination.py`)

```python
from typing import Any, Callable, Dict, Generic, Iterator, List, Optional, TypeVar

T = TypeVar("T")
Envelope = Dict[str, Any]   # {"data": [...], "has_more": bool, "next_cursor": Optional[str], ...}

class PageIterator(Generic[T], Iterator[T]):
    def __init__(
        self,
        fetch_page: Callable[[Optional[str]], Envelope],
        item_key: str = "data",
    ) -> None:
        self._fetch_page = fetch_page
        self._item_key = item_key
        self._buffer: List[T] = []
        self._next_cursor: Optional[str] = None
        self._exhausted = False
        self._items_yielded = 0
        self._current_cursor: Optional[str] = None

    @property
    def current_cursor(self) -> Optional[str]:
        """Cursor of the most recently fetched page; None before the first fetch."""
        return self._current_cursor

    def __iter__(self) -> "PageIterator[T]":
        return self

    def __next__(self) -> T:
        if self._buffer:
            item = self._buffer.pop(0)
            self._items_yielded += 1
            return item
        if self._exhausted:
            raise StopIteration
        try:
            page = self._fetch_page(self._next_cursor)
        except CursorExpiredError as e:
            # Re-raise enriched with iteration progress
            e.items_yielded = self._items_yielded
            e.last_cursor = self._next_cursor
            raise
        self._current_cursor = self._next_cursor
        self._buffer = list(page.get(self._item_key, []))
        self._next_cursor = page.get("next_cursor")
        self._exhausted = not page.get("has_more", False)
        if not self._buffer:
            raise StopIteration
        item = self._buffer.pop(0)
        self._items_yielded += 1
        return item


class AsyncPageIterator(Generic[T]):
    """Same semantics, async."""
    # __aiter__ / __anext__; current_cursor property; same exception enrichment.
```

`fetch_page` is provided by the client method that constructs the iterator and binds the relevant filters/event_id/limit. Each call invokes `_transport.request_json(...)` and receives the full envelope dict (since list endpoints' raw response IS the envelope).

## 10. Versioning, Migration, and Deprecation

### 10.1. Version bump

`seatdata-sdk` jumps from `0.3.0` to `1.0.0`. CHANGELOG entry includes a "Breaking changes" section.

### 10.2. Breaking changes vs v0.3.0

1. `search_events()` now calls `GET /v1/events/search` (was `POST /v0.3.1/events/search`).
   - Returns `List[EventSearchItem]` (a single page, default limit 100). To get the cursor envelope, use `search_events_page()`. For all results across pages, use `iter_search_events()`.
   - `return_full_response=True` is removed (the new `*_page` variant supersedes it).
   - `**kwargs` passthrough is removed; new filters are explicit named parameters per the v1 surface (`event_name`, `event_date`, `venue_name`, `venue_city`, `venue_state`, `country_code`, `tm_event_id`, `std_event_id`, `std_venue_id`, `venue_slug`, `historical`, `limit`, `starting_after`).
2. The HTTP layer migrates from `requests` to `httpx`. SDK exceptions are unchanged; users who caught raw `requests.exceptions.*` will need to switch to `seatdata.SeatDataError` (which they should have been doing).
3. Auth header changes from `api-key: <key>` to `Authorization: Bearer <key>`. The server accepts both; this is invisible to users.

### 10.3. Deprecations (warnings emitted, removal in v1.1 or v2.0)

- `search_events_legacy(...)` — calls v0.3.1 POST. Emits `DeprecationWarning`.
- `event_request_add(...)` — alias for `create_event_request`. Emits `DeprecationWarning`.
- `event_request_status(...)` — alias for `get_event_request_status`. Emits `DeprecationWarning`.

Each warning message includes a one-line migration hint ("use `create_event_request` instead").

### 10.4. Migration guide (CHANGELOG / README)

Short worked example showing the most common case: pull all snapshots for an event.

```python
# Before (v0.3.0)
client = SeatDataClient(api_key)
results = client.search_events(event_name="Taylor Swift")
event_id = results[0]["event_id"]
# ...no v0.x stats endpoint existed

# After (v1.0.0)
client = SeatDataClient(api_key)
results = client.search_events(event_name="Taylor Swift")  # same shape (mostly), v1 GET
event_id = results[0]["event_id"]
for snapshot in client.iter_event_stats(event_id):
    print(snapshot["timestamp"], snapshot["get_in"])
```

## 11. Dependencies

`pyproject.toml` updates:

```toml
dependencies = [
    "httpx>=0.27",
    "typing_extensions>=4.0",
]
```

`requests` is removed. All Python versions 3.8–3.13 are supported (verified by `httpx>=0.27`'s own support matrix).

## 12. Testing Strategy

### 12.1. Unit tests (no network)

Use `respx` (httpx-native mock) or `httpx.MockTransport` to assert request/response behavior without sockets. Targeted suites:

- **Transport:** Bearer header injection. User-Agent string composition (dynamic version). URL building from `base_url` + path. Single-resource endpoints return the parsed resource dict; list endpoints return the parsed envelope dict. Error envelope → exception mapping for each `error.type`. Plain-text and non-JSON error bodies map to `SeatDataServerError` with the raw body in `message`. Retry/backoff: triggers on 429/5xx and connection errors, skips on other 4xx, honors `Retry-After`, exhaustion raises with `retry_after` populated. `retry_safe=False` skips retries (used by `create_event_request`).
- **Pagination:** `PageIterator` follows `next_cursor`. Stops on `has_more=False`. `current_cursor` updates correctly. Mid-iteration `CursorExpiredError` is enriched with `items_yielded` and `last_cursor`.
- **Exception hierarchy:** Legacy aliases (e.g., `AuthenticationError`) are the same class as new names (`SeatDataAuthError`). Plain-text 429 (v0.x) maps to `SeatDataRateLimitError`. `parse_timestamp` round-trips known fixtures.
- **v1 client methods:** Each method asserts the right path, params, and that the right TypedDict-shaped response comes back. `get_event_stats` (no cursor) returns first-page shape including `available_zones`/`total_count`; `get_event_stats(starting_after=...)` for continuation pages omits them.
- **Deprecations:** `search_events_legacy`, `event_request_add`, `event_request_status` each emit `DeprecationWarning`.
- **Async parity:** Same suite mirrored for `AsyncSeatDataClient` using `respx` async mocks. Verify `AsyncClient` is not constructed until first async call.

### 12.2. Integration tests (require `SEATDATA_API_KEY`)

Marked `pytest -m integration`. Hit the live API:

- `get_account()` returns expected fields, including non-empty `rate_limits`.
- `iter_search_events(event_name="...")` yields at least one item.
- `iter_event_stats(event_id=<known small event>)` paginates correctly.
- `get_sales_data` / `get_listings` / `download_daily_csv` continue to work (regression coverage for v0.x).
- A known-bad request raises `SeatDataInvalidRequestError` with `param` populated.

### 12.3. Backward-compatibility tests

A dedicated suite (`tests/test_backcompat.py`) imports from `seatdata` exactly as the v0.3.0 README showed and asserts every method still works against mocked v0.x responses. This guards against unintentional drift in v0.x behavior during the rewrite.

### 12.4. Type-check pass

`mypy seatdata/` runs clean under the existing configuration after the rewrite. New `tests/test_types.py` includes representative `reveal_type` assertions to catch TypedDict regressions.

## 13. Implementation Sequencing (Plan-Phase Hint)

A reasonable order for the implementation plan (detailed plan to be authored by the writing-plans skill):

1. Swap dependency: `requests` → `httpx`. Adapt the existing client minimally so all current tests pass on `httpx` before refactoring further. (Validates the dep swap in isolation.)
2. Build `_transport.py` (sync only first) — extract URL/header/error/retry concerns from `client.py`.
3. Add new exception hierarchy with legacy aliases. All existing tests should still pass.
4. Add `types.py` with TypedDicts and `parse_timestamp`.
5. Add `pagination.py` with `PageIterator`.
6. Implement v1 sync methods on `SeatDataClient`: `get_account`, `get_usage`, `search_events`/`search_events_page`/`iter_search_events`, `get_event_stats`/`iter_event_stats`.
7. Repoint `search_events()` to v1; add `search_events_legacy()` shim. Add deprecations.
8. Rename `event_request_add`/`event_request_status` → `create_event_request`/`get_event_request_status`; keep aliases.
9. Switch auth header to `Authorization: Bearer` for all requests.
10. Build `_transport.py` async surface + `AsyncSeatDataClient` mirroring sync, with lazy async client init.
11. Add `AsyncPageIterator` and async `iter_*` methods.
12. Update README and CHANGELOG with v1.0.0 migration guide.
13. Bump `__version__` and `pyproject.toml` to `1.0.0`.

Each step keeps the test suite green; this is intentional so we can verify "little to no breakage" continuously.

## 14. Open Questions / Risks

- **Server `error.code` for cursor expiry.** This spec assumes `error.code == "invalid_cursor"` (per the brief's documented errors for the stats endpoint). If the actual code differs, `CursorExpiredError` mapping needs adjustment. To be confirmed during integration testing.
- **First-page detection for `get_event_stats`.** The first page's distinguishing feature is the presence of `available_zones`/`total_count`. The SDK does not branch on call shape; the server is the source of truth for whether those fields appear (TypedDict marks them `NotRequired`). Callers use `"available_zones" in response` to detect first-page shape if they need to.
- **`event_id` typing on v0.x methods.** Currently `Optional[str]`. v1 uses `int` for `event_id` and the SeatData internal id; v0.x uses StubHub id (still str-shaped in current code). Not changing v0.x typing as part of this work (out of scope), but note the inconsistency for future cleanup.
- **`download_daily_csv` and Bearer auth.** Currently this method builds its own request inline rather than going through `_make_request`. After the rewrite it will go through `_transport.request_text` and pick up Bearer auth automatically.

## 15. Acceptance Criteria

- [ ] All four v1 endpoints implemented on both sync and async clients.
- [ ] `iter_*` methods auto-paginate; `*_page` methods return envelopes; `current_cursor` exposed.
- [ ] All listed exception classes exist; legacy aliases work; `retry_after` populated on 429.
- [ ] `CursorExpiredError` enriched with `items_yielded` and `last_cursor` when raised from an iterator.
- [ ] TypedDicts exist for all v1 responses; mypy passes.
- [ ] `parse_timestamp` parses `Z`-suffixed UTC strings on Python 3.8+.
- [ ] `requests` no longer in dependencies; `httpx` and `typing_extensions` are.
- [ ] All existing tests pass against the new transport (zero v0.x behavior regressions).
- [ ] New unit tests cover transport, pagination, exception mapping, deprecations.
- [ ] Integration suite passes against live staging key.
- [ ] User-Agent string includes dynamic SDK version.
- [ ] README and CHANGELOG updated with migration guide.
- [ ] `__version__` and `pyproject.toml` set to `1.0.0`.