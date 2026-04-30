# SeatData Python SDK v1.0.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SeatData v1 REST API support (`account`, `usage`, `events/search`, `events/{id}/stats`) to the official Python SDK with sync + async clients, typed responses, cursor pagination, typed exceptions, and retry/backoff — while keeping all existing v0.x endpoints functional. Ship as v1.0.0.

**Architecture:** Flat client API (sync + async) sharing one `_transport.py` core built on `httpx`. v1 responses are TypedDicts; v0.x stays untyped. Pagination via `PageIterator` / `AsyncPageIterator`. Typed exception hierarchy mapped from the v1 `error.type` field, with legacy aliases preserved.

**Tech Stack:** Python 3.8+, `httpx>=0.27` (replacing `requests`), `typing_extensions>=4.0`, `respx` (test-only) for httpx mocking, `pytest`, `mypy`, `black`.

**Reference spec:** `docs/superpowers/specs/2026-04-30-v1-api-support-design.md`

---

## Conventions

- **TDD strictly.** Test first, watch it fail, implement, watch it pass, commit.
- **Commits.** Per task. Short imperative. NO `Co-Authored-By` trailer (user preference).
- **No comments in code files** (per `CLAUDE.md`). The plan shows comments for clarity only — strip them when writing the actual code.
- **Black formatter, 100 char line length.** Applied per task before committing where applicable.
- **API key in tests:** use `"a" * 64` (64-char hex).
- **Mock transport:** new tests use `respx` (`pip install respx`) — gives httpx-native mocking instead of `unittest.mock.patch`.
- **Test command shorthand:** `pytest tests/` runs unit tests only (no integration). Use `pytest tests/path::testname -v` for one test.

---

## Phase A — Foundation: Dependencies, Transport, Exceptions, Types, Pagination

### Task 1: Update dependencies (httpx, typing_extensions, respx)

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`

- [ ] **Step 1: Update `pyproject.toml` dependencies**

Replace the `dependencies` and `[project.optional-dependencies] dev` blocks:

```toml
dependencies = [
    "httpx>=0.27",
    "typing_extensions>=4.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.23.0",
    "respx>=0.21.0",
    "black>=23.0.0",
    "mypy>=1.5.0",
]
```

(`types-requests` is gone since we're off `requests`.)

- [ ] **Step 2: Update `requirements.txt`**

Replace contents:

```
httpx>=0.27
typing_extensions>=4.0
```

- [ ] **Step 3: Reinstall in editable mode**

Run: `pip install -e ".[dev]"`
Expected: success; `httpx` and `respx` install cleanly.

- [ ] **Step 4: Confirm existing tests still discoverable**

Run: `pytest --collect-only tests/ -q 2>&1 | tail -20`
Expected: Tests collect (will fail at runtime since they patch `requests.Session`, fixed in next task).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml requirements.txt
git commit -m "build: swap requests for httpx, add respx and pytest-asyncio for tests"
```

---

### Task 2: Migrate existing `client.py` from requests to httpx (behavior-preserving)

The current client uses `requests.Session`. Swap it to `httpx.Client` keeping all current method behavior identical so the existing test suite (after a small mock update in Task 3) still passes.

**Files:**
- Modify: `seatdata/client.py`

- [ ] **Step 1: Replace `requests` import and Session creation**

In `seatdata/client.py`, change line 2:

```python
import httpx
```

(remove `import requests`)

Change `__init__` (lines 17-24):

```python
def __init__(self, api_key: str, timeout: int = 30):
    if not api_key or len(api_key) != 64:
        raise ValueError("API key must be a 64-character hexadecimal string")

    self._api_key = api_key
    self.timeout = timeout
    self.session = httpx.Client(
        timeout=timeout,
        headers={"api-key": api_key, "User-Agent": "SeatData-Python-SDK/0.3.0"},
    )
```

(`User-Agent` and header changes come later. Bearer auth is Task 18.)

- [ ] **Step 2: Replace `_make_request` body to use httpx**

Replace lines 26-55 of `seatdata/client.py`:

```python
def _make_request(
    self,
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
) -> Any:
    url = self.BASE_URL + endpoint

    try:
        response = self.session.request(
            method=method, url=url, params=params, json=json_data
        )

        if response.status_code == 401:
            raise AuthenticationError("Invalid API key")
        elif response.status_code == 429:
            raise RateLimitError("Rate limit exceeded")
        elif response.status_code == 400:
            raise SeatDataException(f"Bad request: {response.text}")
        elif response.status_code == 404:
            raise SeatDataException(f"Not found: {response.text}")

        if response.status_code not in [200, 202]:
            response.raise_for_status()

        return response.json()

    except httpx.HTTPError as e:
        raise SeatDataException(f"Request failed: {str(e)}")
```

- [ ] **Step 3: Replace `download_daily_csv`'s exception handler**

In the `download_daily_csv` method (around line 201–202), replace `requests.exceptions.RequestException` with `httpx.HTTPError`:

```python
except httpx.HTTPError as e:
    raise SeatDataException(f"Request failed: {str(e)}")
```

- [ ] **Step 4: Run black**

Run: `black seatdata/client.py`
Expected: file reformatted (or already conformant).

- [ ] **Step 5: Verify imports compile**

Run: `python -c "from seatdata.client import SeatDataClient; print('ok')"`
Expected: `ok` printed.

- [ ] **Step 6: Commit**

```bash
git add seatdata/client.py
git commit -m "refactor: migrate transport from requests to httpx (behavior preserved)"
```

(Existing tests will still fail because they patch `requests.Session` — fixed in Task 3.)

---

### Task 3: Update existing test mocks from requests to httpx via respx

Tests in `tests/test_client.py` currently use `unittest.mock.patch("seatdata.client.requests.Session")`. Convert each to use `respx` for httpx-native mocking. This both fixes the broken tests and gives us the mocking pattern we'll use for new v1 tests.

**Files:**
- Modify: `tests/test_client.py`

- [ ] **Step 1: Replace top-level mock import**

In `tests/test_client.py`, replace line 2:

```python
import respx
import httpx
```

(Remove the `unittest.mock` import; we no longer need it.)

- [ ] **Step 2: Convert `test_authentication_error`**

Replace the method (lines 31–40):

```python
@respx.mock
def test_authentication_error(self):
    respx.get("https://seatdata.io/api/v0.3/salesdata/get").mock(
        return_value=httpx.Response(401)
    )
    client = SeatDataClient(api_key="a" * 64)
    with pytest.raises(AuthenticationError, match="Invalid API key"):
        client.get_sales_data(event_id="test_event")
```

- [ ] **Step 3: Convert `test_rate_limit_error`**

```python
@respx.mock
def test_rate_limit_error(self):
    respx.post("https://seatdata.io/api/v0.3.1/events/search").mock(
        return_value=httpx.Response(429)
    )
    client = SeatDataClient(api_key="a" * 64)
    with pytest.raises(RateLimitError, match="Rate limit exceeded"):
        client.search_events(event_name="test")
```

- [ ] **Step 4: Convert `test_bad_request_error`**

```python
@respx.mock
def test_bad_request_error(self):
    respx.get("https://seatdata.io/api/v0.1/listings/get").mock(
        return_value=httpx.Response(400, text="Missing required parameter")
    )
    client = SeatDataClient(api_key="a" * 64)
    with pytest.raises(SeatDataException, match="Bad request: Missing required parameter"):
        client.get_listings(event_id="test")
```

- [ ] **Step 5: Convert `test_get_sales_data_success`**

```python
@respx.mock
def test_get_sales_data_success(self):
    test_data = {"sales": [{"price": 100, "quantity": 2}]}
    route = respx.get("https://seatdata.io/api/v0.3/salesdata/get").mock(
        return_value=httpx.Response(200, json=test_data)
    )
    client = SeatDataClient(api_key="a" * 64)
    result = client.get_sales_data(event_id="test_event")
    assert result == test_data
    assert route.called
```

- [ ] **Step 6: Convert remaining `@patch`-using tests**

Apply the same pattern to:
- `test_get_listings_success` → `respx.get("https://seatdata.io/api/v0.1/listings/get")`
- `test_search_events_success` → `respx.post("https://seatdata.io/api/v0.3.1/events/search")`. Use `route.calls.last.request.content` to inspect the JSON body, e.g.:
  ```python
  import json
  body = json.loads(route.calls.last.request.content)
  assert body == {"event_name": "Concert", "venue_name": "Stadium"}
  ```
- `test_context_manager` — drop the mock; just construct the client in a `with` block and assert `client._api_key`. The `httpx.Client.close()` is called by httpx itself on exit; no mock needed.
- `test_event_request_add_success` → `respx.post("https://seatdata.io/api/v0.4/events/event-request-add")`. Use `httpx.Response(202, json=test_data)`.
- `test_event_request_status_success` → `respx.get("https://seatdata.io/api/v0.4/events/event-request-status/test-job-123/")`.
- `test_event_request_status_not_found` → mock 404 with `httpx.Response(404, text="Job not found")`.
- All `test_download_daily_csv_*` tests → `respx.get("https://seatdata.io/api/v0.5/daily-csv/download")` with appropriate response.

For each: drop `@patch("seatdata.client.requests.Session")` decorator and `mock_session` arg; add `@respx.mock` decorator. Replace `mock_response = Mock(); mock_response.status_code = ...; mock_response.json.return_value = ...` with `httpx.Response(status, json=...)` or `httpx.Response(status, text=...)` as appropriate.

- [ ] **Step 7: Run the full test suite**

Run: `pytest tests/test_client.py -v 2>&1 | tail -30`
Expected: ALL tests pass. If any fail, the conversion missed a case — read the error and fix it.

- [ ] **Step 8: Commit**

```bash
git add tests/test_client.py
git commit -m "test: convert client tests from unittest.mock to respx"
```

---

### Task 4: Create new exception hierarchy (with legacy aliases)

**Files:**
- Modify: `seatdata/exceptions.py`
- Create: `tests/test_exceptions.py`

- [ ] **Step 1: Write failing test for new exception hierarchy**

Create `tests/test_exceptions.py`:

```python
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
        err = SeatDataInvalidRequestError(
            "bad", param="event_id", error_code="missing_parameter"
        )
        assert err.param == "event_id"
        assert err.error_code == "missing_parameter"

    def test_cursor_expired_carries_iteration_state(self):
        err = CursorExpiredError(
            "cursor expired", items_yielded=42, last_cursor="abc123"
        )
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
```

- [ ] **Step 2: Run test, expect failure**

Run: `pytest tests/test_exceptions.py -v`
Expected: ImportError or AttributeError — the new classes don't exist yet.

- [ ] **Step 3: Rewrite `seatdata/exceptions.py`**

Replace contents with:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_exceptions.py tests/test_client.py -v`
Expected: ALL pass (legacy aliases ensure existing client.py code still works).

- [ ] **Step 5: Run black**

Run: `black seatdata/exceptions.py tests/test_exceptions.py`

- [ ] **Step 6: Commit**

```bash
git add seatdata/exceptions.py tests/test_exceptions.py
git commit -m "feat: add v1 exception hierarchy with legacy aliases"
```

---

### Task 5: Create `seatdata/types.py` with TypedDicts

**Files:**
- Create: `seatdata/types.py`
- Create: `tests/test_types.py`

- [ ] **Step 1: Write failing test for TypedDict shapes**

Create `tests/test_types.py`:

```python
from seatdata.types import (
    AccountResponse,
    Plan,
    RateLimitInfo,
    UsageResponse,
    UsageTotals,
    UsageByEndpoint,
    EventSearchItem,
    EventSearchPage,
    EventStatsZone,
    EventStatsSnapshot,
    EventStatsPage,
    ErrorEnvelope,
    ErrorEnvelopeBody,
)


def test_account_response_is_dict_compatible():
    plan: Plan = {
        "id": "professional",
        "name": "Professional",
        "status": "active",
        "billing_period_start": "2026-04-01T00:00:00Z",
        "billing_period_end": "2026-05-01T00:00:00Z",
        "renews_at": "2026-05-01T00:00:00Z",
    }
    rate_limit: RateLimitInfo = {"limit": 60, "window_seconds": 60}
    account: AccountResponse = {
        "user_id": 4823,
        "email": "client@example.com",
        "plans": [plan],
        "rate_limits": {"account": rate_limit},
    }
    assert account["user_id"] == 4823
    assert account["plans"][0]["status"] == "active"


def test_usage_response_shape():
    totals: UsageTotals = {
        "api_calls": 4287,
        "events_searched": 3886,
        "salesdata_pulls": 312,
        "listings_pulls": 89,
        "stats_pulls": 0,
        "daily_csv_downloads": 0,
    }
    by_endpoint: UsageByEndpoint = {"endpoint": "events.search", "count": 3886}
    usage: UsageResponse = {
        "period_start": "2026-03-31T00:00:00Z",
        "period_end": "2026-04-30T00:00:00Z",
        "totals": totals,
        "by_endpoint": [by_endpoint],
    }
    assert usage["totals"]["api_calls"] == 4287


def test_event_search_item_minimal():
    item: EventSearchItem = {
        "event_id": 12345,
        "event_name": "Test",
        "event_date": "2026-06-15",
        "days_on_seatdata": 47,
        "first_seen_date": "2026-03-11",
        "venue_name": "MetLife",
        "venue_city": "East Rutherford",
        "venue_state": "NJ",
    }
    assert item["event_id"] == 12345


def test_event_stats_snapshot_with_zones():
    zone: EventStatsZone = {
        "zone_name": "Lower Bowl",
        "avg_price": 412.75,
        "median_price": 395.0,
        "get_in": 285.0,
        "get_in_qty2plus": 320.0,
    }
    snapshot: EventStatsSnapshot = {
        "timestamp": "2026-04-26T14:30:00Z",
        "total_listings_all": 487,
        "total_listings_active": 312,
        "listing_fill_rate": 0.64,
        "avg_price": 245.5,
        "median_price": 198.0,
        "get_in": 89.0,
        "get_in_qty2plus": 145.0,
        "zones": [zone],
    }
    assert snapshot["zones"][0]["zone_name"] == "Lower Bowl"


def test_event_stats_page_first_page_has_extra_fields():
    page: EventStatsPage = {
        "event_id": 12345,
        "data": [],
        "has_more": False,
        "next_cursor": None,
        "available_zones": ["Lower Bowl"],
        "total_count": 487,
    }
    assert page["available_zones"] == ["Lower Bowl"]


def test_error_envelope_shape():
    body: ErrorEnvelopeBody = {
        "type": "invalid_request",
        "code": "missing_parameter",
        "message": "event_id is required",
        "param": "event_id",
    }
    env: ErrorEnvelope = {"error": body}
    assert env["error"]["type"] == "invalid_request"
```

- [ ] **Step 2: Run test, expect ImportError**

Run: `pytest tests/test_types.py -v`
Expected: ImportError — `seatdata.types` doesn't exist.

- [ ] **Step 3: Create `seatdata/types.py`**

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
    billing_period_start: Optional[str]
    billing_period_end: Optional[str]
    renews_at: Optional[str]


class AccountResponse(TypedDict):
    user_id: int
    email: str
    company: NotRequired[str]
    plans: List[Plan]
    rate_limits: Dict[str, RateLimitInfo]


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
    period_start: str
    period_end: str
    totals: UsageTotals
    by_endpoint: List[UsageByEndpoint]


class EventSearchItem(TypedDict):
    event_id: int
    event_name: str
    event_date: str
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
    timestamp: str
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
    available_zones: NotRequired[List[str]]
    total_count: NotRequired[int]


class ErrorEnvelopeBody(TypedDict):
    type: str
    code: str
    message: str
    param: NotRequired[str]


class ErrorEnvelope(TypedDict):
    error: ErrorEnvelopeBody
```

- [ ] **Step 4: Run tests, mypy**

Run: `pytest tests/test_types.py -v && mypy seatdata/types.py tests/test_types.py`
Expected: tests pass; mypy clean.

- [ ] **Step 5: Black format**

Run: `black seatdata/types.py tests/test_types.py`

- [ ] **Step 6: Commit**

```bash
git add seatdata/types.py tests/test_types.py
git commit -m "feat: add TypedDicts for v1 API responses"
```

---

### Task 6: Add `parse_timestamp` helper to `types.py`

**Files:**
- Modify: `seatdata/types.py`
- Modify: `tests/test_types.py`

- [ ] **Step 1: Write failing tests for parse_timestamp**

Append to `tests/test_types.py`:

```python
from datetime import datetime, timezone
from seatdata.types import parse_timestamp


def test_parse_timestamp_z_suffix():
    result = parse_timestamp("2026-04-26T14:30:00Z")
    assert result == datetime(2026, 4, 26, 14, 30, 0, tzinfo=timezone.utc)


def test_parse_timestamp_with_microseconds():
    result = parse_timestamp("2026-04-26T14:30:00.123456Z")
    assert result.microsecond == 123456
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_explicit_offset_passes_through():
    result = parse_timestamp("2026-04-26T14:30:00+00:00")
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_invalid_raises():
    import pytest

    with pytest.raises(ValueError):
        parse_timestamp("not a timestamp")
```

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/test_types.py::test_parse_timestamp_z_suffix -v`
Expected: ImportError — `parse_timestamp` doesn't exist.

- [ ] **Step 3: Add `parse_timestamp` to `seatdata/types.py`**

Append to the file (after the TypedDict definitions):

```python
from datetime import datetime


def parse_timestamp(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)
```

(`datetime.fromisoformat` accepts `+00:00` on all supported Python versions; the `Z` suffix is normalized first.)

- [ ] **Step 4: Run all type tests**

Run: `pytest tests/test_types.py -v`
Expected: ALL pass including the new parse_timestamp tests.

- [ ] **Step 5: Commit**

```bash
git add seatdata/types.py tests/test_types.py
git commit -m "feat: add parse_timestamp helper for ISO-8601 UTC strings"
```

---

### Task 7: Create `seatdata/pagination.py` with `PageIterator`

**Files:**
- Create: `seatdata/pagination.py`
- Create: `tests/test_pagination.py`

- [ ] **Step 1: Write failing tests for PageIterator**

Create `tests/test_pagination.py`:

```python
import pytest

from seatdata.exceptions import CursorExpiredError, SeatDataInvalidRequestError
from seatdata.pagination import PageIterator


def make_pages(*pages):
    pages_iter = iter(pages)

    def fetch(cursor):
        return next(pages_iter)

    return fetch


class TestPageIteratorSync:
    def test_yields_items_from_single_page(self):
        fetch = make_pages({"data": [1, 2, 3], "has_more": False, "next_cursor": None})
        items = list(PageIterator(fetch))
        assert items == [1, 2, 3]

    def test_follows_cursor_through_multiple_pages(self):
        fetch = make_pages(
            {"data": [1, 2], "has_more": True, "next_cursor": "c1"},
            {"data": [3, 4], "has_more": True, "next_cursor": "c2"},
            {"data": [5], "has_more": False, "next_cursor": None},
        )
        items = list(PageIterator(fetch))
        assert items == [1, 2, 3, 4, 5]

    def test_passes_cursor_to_next_fetch(self):
        cursors_seen = []

        def fetch(cursor):
            cursors_seen.append(cursor)
            if cursor is None:
                return {"data": [1], "has_more": True, "next_cursor": "c1"}
            return {"data": [2], "has_more": False, "next_cursor": None}

        list(PageIterator(fetch))
        assert cursors_seen == [None, "c1"]

    def test_current_cursor_property(self):
        fetch = make_pages(
            {"data": [1], "has_more": True, "next_cursor": "c1"},
            {"data": [2], "has_more": False, "next_cursor": None},
        )
        it = PageIterator(fetch)
        assert it.current_cursor is None
        next(it)
        assert it.current_cursor is None
        next(it)
        assert it.current_cursor == "c1"

    def test_stops_on_empty_page_without_more(self):
        fetch = make_pages({"data": [], "has_more": False, "next_cursor": None})
        items = list(PageIterator(fetch))
        assert items == []

    def test_does_not_implement_len(self):
        fetch = make_pages({"data": [1], "has_more": False, "next_cursor": None})
        it = PageIterator(fetch)
        with pytest.raises(TypeError):
            len(it)

    def test_cursor_expired_enriched_with_iteration_state(self):
        def fetch(cursor):
            if cursor is None:
                return {"data": [1, 2], "has_more": True, "next_cursor": "c1"}
            raise CursorExpiredError("cursor expired", error_code="invalid_cursor")

        it = PageIterator(fetch)
        assert next(it) == 1
        assert next(it) == 2
        with pytest.raises(CursorExpiredError) as exc_info:
            next(it)
        assert exc_info.value.items_yielded == 2
        assert exc_info.value.last_cursor == "c1"
```

- [ ] **Step 2: Run, expect ImportError**

Run: `pytest tests/test_pagination.py -v`
Expected: ImportError — `seatdata.pagination` doesn't exist.

- [ ] **Step 3: Create `seatdata/pagination.py`**

```python
from typing import Any, Callable, Dict, Generic, Iterator, List, Optional, TypeVar

from .exceptions import CursorExpiredError

T = TypeVar("T")
Envelope = Dict[str, Any]


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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_pagination.py -v`
Expected: ALL pass.

- [ ] **Step 5: Black**

Run: `black seatdata/pagination.py tests/test_pagination.py`

- [ ] **Step 6: Commit**

```bash
git add seatdata/pagination.py tests/test_pagination.py
git commit -m "feat: add PageIterator for cursor-based auto-pagination"
```

---

### Task 8: Create `seatdata/_transport.py` (sync) — `request_json` core

This task creates the transport core but does NOT yet wire it into `client.py`. We test it in isolation, then integrate in Task 11.

**Files:**
- Create: `seatdata/_transport.py`
- Create: `tests/test_transport.py`

- [ ] **Step 1: Write failing tests for `request_json` happy paths**

Create `tests/test_transport.py`:

```python
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
    transport.request_json(
        "POST", "/api/v0.4/events/event-request-add", json={"search_query": "X"}
    )
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
```

- [ ] **Step 2: Run, expect ImportError**

Run: `pytest tests/test_transport.py -v`
Expected: ImportError — `seatdata._transport` doesn't exist.

- [ ] **Step 3: Create `seatdata/_transport.py` with sync `request_json`**

```python
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
```

(Retry logic comes in Task 10. `request_text` comes in Task 9. Async client field is reserved for Task 14.)

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_transport.py -v`
Expected: ALL pass.

- [ ] **Step 5: Black**

Run: `black seatdata/_transport.py tests/test_transport.py`

- [ ] **Step 6: Commit**

```bash
git add seatdata/_transport.py tests/test_transport.py
git commit -m "feat: add _Transport with request_json and typed error mapping"
```

---

### Task 9: Add `request_text` to `_Transport` for CSV downloads

**Files:**
- Modify: `seatdata/_transport.py`
- Modify: `tests/test_transport.py`

- [ ] **Step 1: Write failing tests for `request_text`**

Append to `tests/test_transport.py`:

```python
@respx.mock
def test_request_text_returns_body_on_2xx(transport):
    csv = "a,b,c\n1,2,3"
    respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
        return_value=httpx.Response(200, text=csv)
    )
    result = transport.request_text("GET", "/api/v0.5/daily-csv/download")
    assert result == csv


@respx.mock
def test_request_text_raises_typed_error_on_non_2xx(transport):
    respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
        return_value=httpx.Response(
            401,
            json={
                "error": {
                    "type": "subscription_required",
                    "code": "no_csv_plan",
                    "message": "Daily Event CSV subscription required",
                }
            },
        )
    )
    with pytest.raises(SeatDataSubscriptionError, match="Daily Event CSV subscription required"):
        transport.request_text("GET", "/api/v0.5/daily-csv/download")


@respx.mock
def test_request_text_handles_plain_text_error(transport):
    respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
        return_value=httpx.Response(400, text="Invalid date format")
    )
    with pytest.raises(SeatDataServerError) as exc_info:
        transport.request_text("GET", "/api/v0.5/daily-csv/download")
    assert "Invalid date format" in exc_info.value.message
```

(Note: 400 with no envelope falls through to `server_error` per `_parse_error_body`. If we wanted 400-without-envelope → `SeatDataInvalidRequestError`, that would be a separate refinement; the v0.x server returns plain-text 400s and the server_error mapping is acceptable since the user already gets the message. Keep this behavior; revisit if it bites us.)

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/test_transport.py::test_request_text_returns_body_on_2xx -v`
Expected: AttributeError — `request_text` doesn't exist.

- [ ] **Step 3: Add `request_text` to `_Transport`**

Append to `class _Transport` in `seatdata/_transport.py`:

```python
def request_text(
    self,
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    retry_safe: bool = True,
) -> str:
    url = self._base_url + path
    response = self._client.request(method, url, params=params)
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.text
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_transport.py -v`
Expected: ALL pass.

- [ ] **Step 5: Commit**

```bash
git add seatdata/_transport.py tests/test_transport.py
git commit -m "feat: add request_text to _Transport for CSV downloads"
```

---

### Task 10: Add retry/backoff to `_Transport`

**Files:**
- Modify: `seatdata/_transport.py`
- Modify: `tests/test_transport.py`

- [ ] **Step 1: Write failing retry tests**

Append to `tests/test_transport.py`:

```python
class TestRetryBehavior:
    @respx.mock
    def test_retries_on_429_then_succeeds(self):
        t = _Transport(api_key="a" * 64, max_retries=2)
        try:
            route = respx.get("https://seatdata.io/api/v1/x").mock(
                side_effect=[
                    httpx.Response(429, headers={"Retry-After": "0"}, json={
                        "error": {"type": "rate_limit_error", "code": "x", "message": "x"}
                    }),
                    httpx.Response(200, json={"ok": True}),
                ]
            )
            result = t.request_json("GET", "/api/v1/x")
            assert result == {"ok": True}
            assert route.call_count == 2
        finally:
            t.close()

    @respx.mock
    def test_retries_on_503_then_succeeds(self):
        t = _Transport(api_key="a" * 64, max_retries=2)
        try:
            route = respx.get("https://seatdata.io/api/v1/x").mock(
                side_effect=[
                    httpx.Response(503, json={
                        "error": {"type": "server_error", "code": "x", "message": "x"}
                    }),
                    httpx.Response(200, json={"ok": True}),
                ]
            )
            result = t.request_json("GET", "/api/v1/x")
            assert result == {"ok": True}
            assert route.call_count == 2
        finally:
            t.close()

    @respx.mock
    def test_does_not_retry_on_400(self):
        t = _Transport(api_key="a" * 64, max_retries=3)
        try:
            route = respx.get("https://seatdata.io/api/v1/x").mock(
                return_value=httpx.Response(400, json={
                    "error": {"type": "invalid_request", "code": "x", "message": "x"}
                })
            )
            with pytest.raises(SeatDataInvalidRequestError):
                t.request_json("GET", "/api/v1/x")
            assert route.call_count == 1
        finally:
            t.close()

    @respx.mock
    def test_exhaustion_raises_with_retry_after(self):
        t = _Transport(api_key="a" * 64, max_retries=1)
        try:
            respx.get("https://seatdata.io/api/v1/x").mock(
                return_value=httpx.Response(429, headers={"Retry-After": "0"}, json={
                    "error": {"type": "rate_limit_error", "code": "x", "message": "x"}
                })
            )
            with pytest.raises(SeatDataRateLimitError) as exc_info:
                t.request_json("GET", "/api/v1/x")
            assert exc_info.value.retry_after == 0
        finally:
            t.close()

    @respx.mock
    def test_retry_safe_false_skips_retries(self):
        t = _Transport(api_key="a" * 64, max_retries=3)
        try:
            route = respx.get("https://seatdata.io/api/v1/x").mock(
                return_value=httpx.Response(503, json={
                    "error": {"type": "server_error", "code": "x", "message": "x"}
                })
            )
            with pytest.raises(SeatDataServerError):
                t.request_json("GET", "/api/v1/x", retry_safe=False)
            assert route.call_count == 1
        finally:
            t.close()

    @respx.mock
    def test_retries_on_connection_error(self):
        t = _Transport(api_key="a" * 64, max_retries=2)
        try:
            route = respx.get("https://seatdata.io/api/v1/x").mock(
                side_effect=[
                    httpx.ConnectError("boom"),
                    httpx.Response(200, json={"ok": True}),
                ]
            )
            result = t.request_json("GET", "/api/v1/x")
            assert result == {"ok": True}
            assert route.call_count == 2
        finally:
            t.close()
```

- [ ] **Step 2: Run, expect failures (no retry yet)**

Run: `pytest tests/test_transport.py::TestRetryBehavior -v`
Expected: FAILURES — retries don't happen yet.

- [ ] **Step 3: Implement retry loop**

Add at the top of `seatdata/_transport.py` (after imports):

```python
import random
import time

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
    return random.uniform(0, min(_BACKOFF_BASE_SECONDS * (2 ** attempt), _BACKOFF_CAP_SECONDS))
```

Replace the `_Transport.request_json` method body with retry-aware version:

```python
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
```

Apply the same retry pattern to `request_text`:

```python
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
```

- [ ] **Step 4: Run all transport tests**

Run: `pytest tests/test_transport.py -v`
Expected: ALL pass.

- [ ] **Step 5: Black**

Run: `black seatdata/_transport.py tests/test_transport.py`

- [ ] **Step 6: Commit**

```bash
git add seatdata/_transport.py tests/test_transport.py
git commit -m "feat: add retry with full-jitter backoff and Retry-After honoring"
```

---

### Task 11: Refactor `seatdata/client.py` to use `_Transport`

This task replaces the inline httpx logic in `client.py` with calls into `_Transport`. The existing public methods (search_events, get_sales_data, etc.) keep their current signatures and v0.x endpoints; behavior preserved. Bearer auth becomes the new default (already set in `_Transport`); v0.x server accepts both per spec.

**Files:**
- Modify: `seatdata/client.py`

- [ ] **Step 1: Replace the client implementation**

Rewrite `seatdata/client.py` (full replacement; signatures preserved):

```python
from typing import Any, Dict, List, Optional, cast

from ._transport import _Transport
from .exceptions import SeatDataError


class SeatDataClient:
    BASE_URL = "https://seatdata.io"

    def __init__(
        self,
        api_key: str,
        timeout: int = 30,
        max_retries: int = 3,
        base_url: Optional[str] = None,
    ) -> None:
        if not api_key or len(api_key) != 64:
            raise ValueError("API key must be a 64-character hexadecimal string")
        self._api_key = api_key
        self.timeout = timeout
        self._transport = _Transport(
            api_key=api_key,
            base_url=base_url or self.BASE_URL,
            timeout=timeout,
            max_retries=max_retries,
        )

    def get_sales_data(
        self, event_id: Optional[str] = None, event_id_sh: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not event_id and not event_id_sh:
            raise ValueError("Either event_id or event_id_sh must be provided")
        params: Dict[str, Any] = {}
        if event_id:
            params["event_id"] = event_id
        if event_id_sh:
            params["event_id_sh"] = event_id_sh
        return cast(
            List[Dict[str, Any]],
            self._transport.request_json("GET", "/api/v0.3/salesdata/get", params=params),
        )

    def get_listings(
        self, event_id: Optional[str] = None, event_id_sh: Optional[str] = None
    ) -> Dict[str, Any]:
        if not event_id and not event_id_sh:
            raise ValueError("Either event_id or event_id_sh must be provided")
        params: Dict[str, Any] = {}
        if event_id:
            params["event_id"] = event_id
        if event_id_sh:
            params["event_id_sh"] = event_id_sh
        return cast(
            Dict[str, Any],
            self._transport.request_json("GET", "/api/v0.1/listings/get", params=params),
        )

    def search_events(
        self,
        event_name: Optional[str] = None,
        event_date: Optional[str] = None,
        venue_name: Optional[str] = None,
        venue_city: Optional[str] = None,
        venue_state: Optional[str] = None,
        return_full_response: bool = False,
        **kwargs: Any,
    ) -> Any:
        search_params: Dict[str, Any] = {}
        if event_name:
            search_params["event_name"] = event_name
        if event_date:
            search_params["event_date"] = event_date
        if venue_name:
            search_params["venue_name"] = venue_name
        if venue_city:
            search_params["venue_city"] = venue_city
        if venue_state:
            search_params["venue_state"] = venue_state
        search_params.update(kwargs)
        response = self._transport.request_json(
            "POST", "/api/v0.3.1/events/search", json=search_params
        )
        if return_full_response:
            return response
        if isinstance(response, dict) and "items" in response:
            return response["items"]
        return response

    def event_request_add(self, search_query: str) -> Dict[str, Any]:
        if not search_query:
            raise ValueError("search_query must be provided")
        response = self._transport.request_json(
            "POST",
            "/api/v0.4/events/event-request-add",
            json={"search_query": search_query},
            retry_safe=False,
        )
        if response is None:
            raise SeatDataError("Empty response from API")
        return cast(Dict[str, Any], response)

    def event_request_status(self, job_id: str) -> Dict[str, Any]:
        if not job_id:
            raise ValueError("job_id must be provided")
        response = self._transport.request_json(
            "GET", f"/api/v0.4/events/event-request-status/{job_id}/"
        )
        if response is None:
            raise SeatDataError("Empty response from API")
        return cast(Dict[str, Any], response)

    def download_daily_csv(self, date: Optional[str] = None) -> str:
        params: Dict[str, Any] = {}
        if date:
            params["date"] = date
        return self._transport.request_text(
            "GET", "/api/v0.5/daily-csv/download", params=params
        )

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "SeatDataClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
```

(This is the v0.3.0-compatible version still using v0.3.1 POST search and old endpoint paths. v1 search comes in Task 12. `**kwargs` and `return_full_response` will be removed in Task 13. Bearer header is already used because `_Transport` sets it.)

- [ ] **Step 2: Update tests for changed BASE_URL semantics**

The new `BASE_URL` is `"https://seatdata.io"` (no `/api` suffix); endpoints now include `/api/...` in their paths. Update `tests/test_client.py` mocks accordingly. Check each `respx.<method>("https://seatdata.io/api/...")` URL — the path should already include `/api/...`. Confirm the mocks match by reading them.

(If the existing tests already use `https://seatdata.io/api/v0.3/...` etc., no change needed. They do — see Task 3 conversions above.)

- [ ] **Step 3: Run full unit test suite**

Run: `pytest tests/ -v 2>&1 | tail -40`
Expected: ALL pass. The download_daily_csv subscription/not-found tests still pass because the typed exception mapping in `_Transport` handles 401 with `subscription_required` envelope and 404 with `not_found` envelope correctly. The 401-with-non-JSON body falls through to `SeatDataAuthError` ("Invalid API key" message lost but the exception type is right).

- [ ] **Step 4: Update `download_daily_csv` 401-without-envelope test if needed**

The existing test `test_download_daily_csv_authentication_error` mocked a 401 response with no JSON body and expected `AuthenticationError(match="Invalid API key")`. With the new transport, `_parse_error_body` falls back to `server_error` for 401-without-envelope. Update the test to expect `SeatDataAuthError` (which is `AuthenticationError`) without matching the message:

```python
@respx.mock
def test_download_daily_csv_authentication_error(self):
    respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    client = SeatDataClient(api_key="a" * 64)
    with pytest.raises(SeatDataException):
        client.download_daily_csv()
```

(Bare-401 maps to `SeatDataServerError` per `_parse_error_body`'s fallback. That's a behavior change worth fixing: bare-401 should map to auth, not server_error. Adjust `_parse_error_body` so 401-without-envelope maps to `authentication_error`:)

```python
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
    if not isinstance(body, dict) or "error" not in body or not isinstance(body["error"], dict):
        return {
            "error": {
                "type": fallback_type,
                "code": "non_envelope_response",
                "message": response.text or "",
            }
        }
    return body
```

Re-run transport tests: `pytest tests/test_transport.py -v`. The `test_5xx_non_json_body` test still expects `SeatDataServerError` — passes (502 is not in the fallback map → server_error). Re-run client tests: `pytest tests/test_client.py -v`.

- [ ] **Step 5: Black**

Run: `black seatdata/client.py seatdata/_transport.py tests/`

- [ ] **Step 6: Commit**

```bash
git add seatdata/client.py seatdata/_transport.py tests/
git commit -m "refactor: route SeatDataClient through _Transport (Bearer auth, retries)"
```

---

## Phase B — v1 Endpoints (Sync)

### Task 12: Add `get_account` and `get_usage`

**Files:**
- Modify: `seatdata/client.py`
- Create: `tests/test_v1_account_usage.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_v1_account_usage.py`:

```python
import httpx
import pytest
import respx

from seatdata import SeatDataClient


@respx.mock
def test_get_account_returns_typed_response():
    payload = {
        "user_id": 4823,
        "email": "client@example.com",
        "company": "Acme Trading",
        "plans": [
            {
                "id": "professional",
                "name": "Professional",
                "status": "active",
                "billing_period_start": "2026-04-01T00:00:00Z",
                "billing_period_end": "2026-05-01T00:00:00Z",
                "renews_at": "2026-05-01T00:00:00Z",
            }
        ],
        "rate_limits": {
            "account": {"limit": 60, "window_seconds": 60},
            "events_search": {"limit": 6, "window_seconds": 60},
        },
    }
    route = respx.get("https://seatdata.io/api/v1/account").mock(
        return_value=httpx.Response(200, json=payload)
    )
    client = SeatDataClient(api_key="a" * 64)
    result = client.get_account()
    assert result["user_id"] == 4823
    assert result["plans"][0]["status"] == "active"
    assert result["rate_limits"]["events_search"]["limit"] == 6
    assert route.called


@respx.mock
def test_get_usage_returns_typed_response():
    payload = {
        "period_start": "2026-03-31T00:00:00Z",
        "period_end": "2026-04-30T00:00:00Z",
        "totals": {
            "api_calls": 4287,
            "events_searched": 3886,
            "salesdata_pulls": 312,
            "listings_pulls": 89,
            "stats_pulls": 0,
            "daily_csv_downloads": 0,
        },
        "by_endpoint": [{"endpoint": "events.search", "count": 3886}],
    }
    respx.get("https://seatdata.io/api/v1/usage").mock(
        return_value=httpx.Response(200, json=payload)
    )
    client = SeatDataClient(api_key="a" * 64)
    result = client.get_usage()
    assert result["totals"]["api_calls"] == 4287
```

- [ ] **Step 2: Run, expect AttributeError**

Run: `pytest tests/test_v1_account_usage.py -v`
Expected: AttributeError — `get_account` doesn't exist.

- [ ] **Step 3: Add methods to `SeatDataClient`**

Add to `seatdata/client.py` (alongside other methods). Add the import at top:

```python
from .types import AccountResponse, UsageResponse
```

Add methods inside `class SeatDataClient`:

```python
def get_account(self) -> AccountResponse:
    return cast(AccountResponse, self._transport.request_json("GET", "/api/v1/account"))

def get_usage(self) -> UsageResponse:
    return cast(UsageResponse, self._transport.request_json("GET", "/api/v1/usage"))
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_v1_account_usage.py -v`
Expected: ALL pass.

- [ ] **Step 5: Black**

Run: `black seatdata/client.py tests/test_v1_account_usage.py`

- [ ] **Step 6: Commit**

```bash
git add seatdata/client.py tests/test_v1_account_usage.py
git commit -m "feat: add get_account and get_usage v1 methods"
```

---

### Task 13: Repoint `search_events` to v1 GET (BREAKING) and add `search_events_page` / `iter_search_events`

**Files:**
- Modify: `seatdata/client.py`
- Modify: `tests/test_client.py` (update existing `test_search_events_success`)
- Create: `tests/test_v1_search.py`

- [ ] **Step 1: Write failing tests for new search surface**

Create `tests/test_v1_search.py`:

```python
import httpx
import pytest
import respx

from seatdata import SeatDataClient


SEARCH_URL = "https://seatdata.io/api/v1/events/search"


def make_item(event_id, name="Test"):
    return {
        "event_id": event_id,
        "event_name": name,
        "event_date": "2026-06-15",
        "days_on_seatdata": 47,
        "first_seen_date": "2026-03-11",
        "venue_name": "MetLife",
        "venue_city": "East Rutherford",
        "venue_state": "NJ",
    }


@respx.mock
def test_search_events_returns_items_list():
    route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={"data": [make_item(1), make_item(2)], "has_more": False, "next_cursor": None},
        )
    )
    client = SeatDataClient(api_key="a" * 64)
    items = client.search_events(event_name="Taylor")
    assert isinstance(items, list)
    assert items[0]["event_id"] == 1
    assert route.calls.last.request.url.params["event_name"] == "Taylor"


@respx.mock
def test_search_events_page_returns_envelope():
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={"data": [make_item(1)], "has_more": True, "next_cursor": "c1"},
        )
    )
    client = SeatDataClient(api_key="a" * 64)
    page = client.search_events_page(event_name="Taylor")
    assert page["data"][0]["event_id"] == 1
    assert page["has_more"] is True
    assert page["next_cursor"] == "c1"


@respx.mock
def test_search_events_page_passes_starting_after():
    route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200, json={"data": [], "has_more": False, "next_cursor": None}
        )
    )
    client = SeatDataClient(api_key="a" * 64)
    client.search_events_page(starting_after="cursor1", limit=50)
    params = route.calls.last.request.url.params
    assert params["starting_after"] == "cursor1"
    assert params["limit"] == "50"


@respx.mock
def test_iter_search_events_walks_pages():
    respx.get(SEARCH_URL).mock(
        side_effect=[
            httpx.Response(200, json={
                "data": [make_item(1), make_item(2)], "has_more": True, "next_cursor": "c1"
            }),
            httpx.Response(200, json={
                "data": [make_item(3)], "has_more": False, "next_cursor": None
            }),
        ]
    )
    client = SeatDataClient(api_key="a" * 64)
    ids = [item["event_id"] for item in client.iter_search_events(event_name="X")]
    assert ids == [1, 2, 3]


@respx.mock
def test_iter_search_events_exposes_current_cursor():
    respx.get(SEARCH_URL).mock(
        side_effect=[
            httpx.Response(200, json={"data": [make_item(1)], "has_more": True, "next_cursor": "c1"}),
            httpx.Response(200, json={"data": [make_item(2)], "has_more": False, "next_cursor": None}),
        ]
    )
    client = SeatDataClient(api_key="a" * 64)
    it = client.iter_search_events()
    next(it)
    next(it)
    assert it.current_cursor == "c1"


@respx.mock
def test_search_events_supports_all_documented_filters():
    route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"data": [], "has_more": False, "next_cursor": None})
    )
    client = SeatDataClient(api_key="a" * 64)
    client.search_events(
        event_name="X",
        event_date="2026-06",
        venue_name="MetLife",
        venue_city="East Rutherford",
        venue_state="NJ",
        country_code="US",
        tm_event_id="abc",
        std_event_id=42,
        std_venue_id=7,
        venue_slug="metlife-stadium",
        historical=True,
        limit=100,
    )
    params = route.calls.last.request.url.params
    assert params["country_code"] == "US"
    assert params["std_event_id"] == "42"
    assert params["historical"] == "true"


@respx.mock
def test_search_events_omits_none_filters():
    route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"data": [], "has_more": False, "next_cursor": None})
    )
    client = SeatDataClient(api_key="a" * 64)
    client.search_events(event_name="X")
    params = route.calls.last.request.url.params
    assert "venue_name" not in params
    assert "country_code" not in params
```

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/test_v1_search.py -v`
Expected: failures (`search_events` returns wrong shape, others don't exist).

- [ ] **Step 3: Replace `search_events` implementation in `client.py`**

Add imports at top of `seatdata/client.py`:

```python
from .pagination import PageIterator
from .types import EventSearchItem, EventSearchPage
```

Replace the existing `search_events` method:

```python
def _search_events_params(
    self,
    *,
    event_name: Optional[str] = None,
    event_date: Optional[str] = None,
    venue_name: Optional[str] = None,
    venue_city: Optional[str] = None,
    venue_state: Optional[str] = None,
    country_code: Optional[str] = None,
    tm_event_id: Optional[str] = None,
    std_event_id: Optional[int] = None,
    std_venue_id: Optional[int] = None,
    venue_slug: Optional[str] = None,
    historical: Optional[bool] = None,
    limit: Optional[int] = None,
    starting_after: Optional[str] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    if event_name is not None:
        params["event_name"] = event_name
    if event_date is not None:
        params["event_date"] = event_date
    if venue_name is not None:
        params["venue_name"] = venue_name
    if venue_city is not None:
        params["venue_city"] = venue_city
    if venue_state is not None:
        params["venue_state"] = venue_state
    if country_code is not None:
        params["country_code"] = country_code
    if tm_event_id is not None:
        params["tm_event_id"] = tm_event_id
    if std_event_id is not None:
        params["std_event_id"] = std_event_id
    if std_venue_id is not None:
        params["std_venue_id"] = std_venue_id
    if venue_slug is not None:
        params["venue_slug"] = venue_slug
    if historical is not None:
        params["historical"] = "true" if historical else "false"
    if limit is not None:
        params["limit"] = limit
    if starting_after is not None:
        params["starting_after"] = starting_after
    return params

def search_events(
    self,
    event_name: Optional[str] = None,
    event_date: Optional[str] = None,
    venue_name: Optional[str] = None,
    venue_city: Optional[str] = None,
    venue_state: Optional[str] = None,
    country_code: Optional[str] = None,
    tm_event_id: Optional[str] = None,
    std_event_id: Optional[int] = None,
    std_venue_id: Optional[int] = None,
    venue_slug: Optional[str] = None,
    historical: Optional[bool] = None,
    limit: Optional[int] = None,
) -> List[EventSearchItem]:
    page = self.search_events_page(
        event_name=event_name,
        event_date=event_date,
        venue_name=venue_name,
        venue_city=venue_city,
        venue_state=venue_state,
        country_code=country_code,
        tm_event_id=tm_event_id,
        std_event_id=std_event_id,
        std_venue_id=std_venue_id,
        venue_slug=venue_slug,
        historical=historical,
        limit=limit,
    )
    return cast(List[EventSearchItem], page["data"])

def search_events_page(
    self,
    event_name: Optional[str] = None,
    event_date: Optional[str] = None,
    venue_name: Optional[str] = None,
    venue_city: Optional[str] = None,
    venue_state: Optional[str] = None,
    country_code: Optional[str] = None,
    tm_event_id: Optional[str] = None,
    std_event_id: Optional[int] = None,
    std_venue_id: Optional[int] = None,
    venue_slug: Optional[str] = None,
    historical: Optional[bool] = None,
    limit: Optional[int] = None,
    starting_after: Optional[str] = None,
) -> EventSearchPage:
    params = self._search_events_params(
        event_name=event_name,
        event_date=event_date,
        venue_name=venue_name,
        venue_city=venue_city,
        venue_state=venue_state,
        country_code=country_code,
        tm_event_id=tm_event_id,
        std_event_id=std_event_id,
        std_venue_id=std_venue_id,
        venue_slug=venue_slug,
        historical=historical,
        limit=limit,
        starting_after=starting_after,
    )
    return cast(
        EventSearchPage,
        self._transport.request_json("GET", "/api/v1/events/search", params=params),
    )

def iter_search_events(
    self,
    event_name: Optional[str] = None,
    event_date: Optional[str] = None,
    venue_name: Optional[str] = None,
    venue_city: Optional[str] = None,
    venue_state: Optional[str] = None,
    country_code: Optional[str] = None,
    tm_event_id: Optional[str] = None,
    std_event_id: Optional[int] = None,
    std_venue_id: Optional[int] = None,
    venue_slug: Optional[str] = None,
    historical: Optional[bool] = None,
    limit: Optional[int] = None,
) -> PageIterator[EventSearchItem]:
    def fetch(cursor: Optional[str]) -> Dict[str, Any]:
        return self.search_events_page(
            event_name=event_name,
            event_date=event_date,
            venue_name=venue_name,
            venue_city=venue_city,
            venue_state=venue_state,
            country_code=country_code,
            tm_event_id=tm_event_id,
            std_event_id=std_event_id,
            std_venue_id=std_venue_id,
            venue_slug=venue_slug,
            historical=historical,
            limit=limit,
            starting_after=cursor,
        )
    return PageIterator(fetch)
```

- [ ] **Step 4: Update existing `test_search_events_success` in `tests/test_client.py`**

The old test mocked `POST /api/v0.3.1/events/search`. Delete that test (the legacy method test will be added in Task 14). Replace with: nothing for now.

In `tests/test_client.py`, find and DELETE the `test_search_events_success` method entirely (lines around 107–123 in the original file, post-Task-3 conversion).

Also delete the `test_rate_limit_error` test that uses `search_events` (the existing one mocks the v0.3.1 POST URL — it's stale). Either delete or update to mock the new GET URL:

```python
@respx.mock
def test_rate_limit_error(self):
    respx.get("https://seatdata.io/api/v1/events/search").mock(
        return_value=httpx.Response(429, json={
            "error": {"type": "rate_limit_error", "code": "x", "message": "Rate limit exceeded"}
        })
    )
    client = SeatDataClient(api_key="a" * 64, max_retries=0)
    with pytest.raises(RateLimitError):
        client.search_events(event_name="test")
```

(Note `max_retries=0` so the test doesn't loop on the 429.)

- [ ] **Step 5: Run all tests**

Run: `pytest tests/ -v 2>&1 | tail -30`
Expected: ALL pass (search_events now uses v1 GET; new tests pass; old tests updated).

- [ ] **Step 6: Black**

Run: `black seatdata/client.py tests/`

- [ ] **Step 7: Commit**

```bash
git add seatdata/client.py tests/
git commit -m "feat!: search_events now uses v1 GET; add search_events_page and iter_search_events

BREAKING CHANGE: search_events returns v1 envelope items (no result_total),
removes return_full_response and **kwargs. Use search_events_page for the
envelope, iter_search_events for auto-paginated iteration."
```

---

### Task 14: Add `search_events_legacy` shim with deprecation warning

**Files:**
- Modify: `seatdata/client.py`
- Create: `tests/test_legacy_search.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_legacy_search.py`:

```python
import json
import warnings

import httpx
import pytest
import respx

from seatdata import SeatDataClient


@respx.mock
def test_search_events_legacy_calls_v031_post():
    route = respx.post("https://seatdata.io/api/v0.3.1/events/search").mock(
        return_value=httpx.Response(200, json={"items": [{"event_id": 1}]})
    )
    client = SeatDataClient(api_key="a" * 64)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = client.search_events_legacy(event_name="Taylor")
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body == {"event_name": "Taylor"}
    assert any(
        issubclass(w.category, DeprecationWarning) and "search_events" in str(w.message)
        for w in caught
    )
    assert result == [{"event_id": 1}]


@respx.mock
def test_search_events_legacy_return_full_response():
    payload = {"result_total": 1, "items": [{"event_id": 1}]}
    respx.post("https://seatdata.io/api/v0.3.1/events/search").mock(
        return_value=httpx.Response(200, json=payload)
    )
    client = SeatDataClient(api_key="a" * 64)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = client.search_events_legacy(event_name="X", return_full_response=True)
    assert result == payload
```

- [ ] **Step 2: Run, expect AttributeError**

Run: `pytest tests/test_legacy_search.py -v`
Expected: AttributeError — `search_events_legacy` doesn't exist.

- [ ] **Step 3: Add `search_events_legacy` to `client.py`**

Add `import warnings` at top of `seatdata/client.py`.

Add method to `class SeatDataClient`:

```python
def search_events_legacy(
    self,
    event_name: Optional[str] = None,
    event_date: Optional[str] = None,
    venue_name: Optional[str] = None,
    venue_city: Optional[str] = None,
    venue_state: Optional[str] = None,
    return_full_response: bool = False,
    **kwargs: Any,
) -> Any:
    warnings.warn(
        "search_events_legacy() calls the deprecated v0.3.1 POST endpoint. "
        "Use search_events() (v1 GET) instead. This method will be removed in v1.1.",
        DeprecationWarning,
        stacklevel=2,
    )
    search_params: Dict[str, Any] = {}
    if event_name:
        search_params["event_name"] = event_name
    if event_date:
        search_params["event_date"] = event_date
    if venue_name:
        search_params["venue_name"] = venue_name
    if venue_city:
        search_params["venue_city"] = venue_city
    if venue_state:
        search_params["venue_state"] = venue_state
    search_params.update(kwargs)
    response = self._transport.request_json(
        "POST", "/api/v0.3.1/events/search", json=search_params
    )
    if return_full_response:
        return response
    if isinstance(response, dict) and "items" in response:
        return response["items"]
    return response
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_legacy_search.py -v`
Expected: ALL pass.

- [ ] **Step 5: Commit**

```bash
git add seatdata/client.py tests/test_legacy_search.py
git commit -m "feat: add search_events_legacy shim for v0.3.1 POST with DeprecationWarning"
```

---

### Task 15: Add `get_event_stats` and `iter_event_stats`

**Files:**
- Modify: `seatdata/client.py`
- Create: `tests/test_v1_stats.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_v1_stats.py`:

```python
import httpx
import pytest
import respx

from seatdata import SeatDataClient
from seatdata.exceptions import CursorExpiredError


def stats_url(event_id):
    return f"https://seatdata.io/api/v1/events/{event_id}/stats"


def make_snapshot(timestamp="2026-04-26T14:30:00Z"):
    return {
        "timestamp": timestamp,
        "total_listings_all": 487,
        "total_listings_active": 312,
        "listing_fill_rate": 0.64,
        "avg_price": 245.5,
        "median_price": 198.0,
        "get_in": 89.0,
        "get_in_qty2plus": 145.0,
        "zones": [],
    }


@respx.mock
def test_get_event_stats_first_page_includes_zones_and_total():
    payload = {
        "event_id": 12345,
        "data": [make_snapshot()],
        "has_more": False,
        "next_cursor": None,
        "available_zones": ["Lower Bowl", "Upper Deck"],
        "total_count": 1,
    }
    respx.get(stats_url(12345)).mock(return_value=httpx.Response(200, json=payload))
    client = SeatDataClient(api_key="a" * 64)
    result = client.get_event_stats(12345)
    assert result["available_zones"] == ["Lower Bowl", "Upper Deck"]
    assert result["total_count"] == 1
    assert result["data"][0]["timestamp"] == "2026-04-26T14:30:00Z"


@respx.mock
def test_get_event_stats_with_cursor_continuation():
    payload = {
        "event_id": 12345,
        "data": [make_snapshot()],
        "has_more": False,
        "next_cursor": None,
    }
    route = respx.get(stats_url(12345)).mock(return_value=httpx.Response(200, json=payload))
    client = SeatDataClient(api_key="a" * 64)
    client.get_event_stats(12345, starting_after="cursor1", limit=50)
    params = route.calls.last.request.url.params
    assert params["starting_after"] == "cursor1"
    assert params["limit"] == "50"


@respx.mock
def test_get_event_stats_with_date_filters():
    payload = {"event_id": 12345, "data": [], "has_more": False, "next_cursor": None}
    route = respx.get(stats_url(12345)).mock(return_value=httpx.Response(200, json=payload))
    client = SeatDataClient(api_key="a" * 64)
    client.get_event_stats(12345, start_date="2026-04-01", end_date="2026-04-30")
    params = route.calls.last.request.url.params
    assert params["start_date"] == "2026-04-01"
    assert params["end_date"] == "2026-04-30"


@respx.mock
def test_iter_event_stats_walks_pages():
    respx.get(stats_url(12345)).mock(
        side_effect=[
            httpx.Response(200, json={
                "event_id": 12345,
                "data": [make_snapshot("2026-04-26T14:30:00Z")],
                "has_more": True,
                "next_cursor": "c1",
                "available_zones": [],
                "total_count": 2,
            }),
            httpx.Response(200, json={
                "event_id": 12345,
                "data": [make_snapshot("2026-04-26T15:00:00Z")],
                "has_more": False,
                "next_cursor": None,
            }),
        ]
    )
    client = SeatDataClient(api_key="a" * 64)
    timestamps = [s["timestamp"] for s in client.iter_event_stats(12345)]
    assert timestamps == ["2026-04-26T14:30:00Z", "2026-04-26T15:00:00Z"]


@respx.mock
def test_iter_event_stats_raises_cursor_expired_with_progress():
    respx.get(stats_url(12345)).mock(
        side_effect=[
            httpx.Response(200, json={
                "event_id": 12345,
                "data": [make_snapshot()],
                "has_more": True,
                "next_cursor": "expired_cursor",
            }),
            httpx.Response(400, json={
                "error": {
                    "type": "invalid_request",
                    "code": "invalid_cursor",
                    "message": "cursor expired",
                }
            }),
        ]
    )
    client = SeatDataClient(api_key="a" * 64, max_retries=0)
    it = client.iter_event_stats(12345)
    next(it)
    with pytest.raises(CursorExpiredError) as exc_info:
        next(it)
    assert exc_info.value.items_yielded == 1
    assert exc_info.value.last_cursor == "expired_cursor"
```

- [ ] **Step 2: Run, expect AttributeError**

Run: `pytest tests/test_v1_stats.py -v`
Expected: failures.

- [ ] **Step 3: Add stats methods to `client.py`**

Add imports at top:

```python
from .types import EventStatsPage, EventStatsSnapshot
```

Add methods to `class SeatDataClient`:

```python
def _event_stats_params(
    self,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
    starting_after: Optional[str] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    if limit is not None:
        params["limit"] = limit
    if starting_after is not None:
        params["starting_after"] = starting_after
    return params

def get_event_stats(
    self,
    event_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
    starting_after: Optional[str] = None,
) -> EventStatsPage:
    params = self._event_stats_params(
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        starting_after=starting_after,
    )
    return cast(
        EventStatsPage,
        self._transport.request_json(
            "GET", f"/api/v1/events/{event_id}/stats", params=params
        ),
    )

def iter_event_stats(
    self,
    event_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
) -> PageIterator[EventStatsSnapshot]:
    def fetch(cursor: Optional[str]) -> Dict[str, Any]:
        return cast(
            Dict[str, Any],
            self.get_event_stats(
                event_id,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                starting_after=cursor,
            ),
        )
    return PageIterator(fetch)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_v1_stats.py -v`
Expected: ALL pass.

- [ ] **Step 5: Black + commit**

Run: `black seatdata/client.py tests/test_v1_stats.py`

```bash
git add seatdata/client.py tests/test_v1_stats.py
git commit -m "feat: add get_event_stats and iter_event_stats with cursor-expiry handling"
```

---

## Phase C — v0.x Method Renames and Public API Shape

### Task 16: Rename `event_request_add` → `create_event_request`

**Files:**
- Modify: `seatdata/client.py`
- Modify: `tests/test_client.py`

- [ ] **Step 1: Write failing tests for new name + deprecation alias**

Append to `tests/test_client.py`:

```python
@respx.mock
def test_create_event_request_success():
    test_data = {"job_id": "test-job-123", "status": "pending"}
    respx.post("https://seatdata.io/api/v0.4/events/event-request-add").mock(
        return_value=httpx.Response(202, json=test_data)
    )
    client = SeatDataClient(api_key="a" * 64)
    result = client.create_event_request(search_query="Taylor Swift")
    assert result == test_data


@respx.mock
def test_event_request_add_emits_deprecation_warning():
    import warnings
    respx.post("https://seatdata.io/api/v0.4/events/event-request-add").mock(
        return_value=httpx.Response(202, json={"job_id": "x"})
    )
    client = SeatDataClient(api_key="a" * 64)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client.event_request_add(search_query="X")
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


def test_create_event_request_empty_query_raises():
    client = SeatDataClient(api_key="a" * 64)
    with pytest.raises(ValueError, match="search_query must be provided"):
        client.create_event_request(search_query="")
```

- [ ] **Step 2: Run, expect AttributeError**

Run: `pytest tests/test_client.py::TestSeatDataClient::test_create_event_request_success -v`
Expected: AttributeError.

- [ ] **Step 3: Rename in `client.py`**

In `seatdata/client.py`, rename the method `event_request_add` → `create_event_request`. Then add a deprecated alias method:

```python
def event_request_add(self, search_query: str) -> Dict[str, Any]:
    warnings.warn(
        "event_request_add() is deprecated. Use create_event_request() instead. "
        "This alias will be removed in v1.1.",
        DeprecationWarning,
        stacklevel=2,
    )
    return self.create_event_request(search_query)
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/ -v`
Expected: ALL pass — new tests + the existing `test_event_request_add_success` test still works (because the alias delegates to the new method).

- [ ] **Step 5: Commit**

```bash
git add seatdata/client.py tests/test_client.py
git commit -m "feat: rename event_request_add to create_event_request (alias kept, deprecated)"
```

---

### Task 17: Rename `event_request_status` → `get_event_request_status`

**Files:**
- Modify: `seatdata/client.py`
- Modify: `tests/test_client.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_client.py`:

```python
@respx.mock
def test_get_event_request_status_success():
    test_data = {"job_id": "test-job-123", "status": "completed"}
    respx.get("https://seatdata.io/api/v0.4/events/event-request-status/test-job-123/").mock(
        return_value=httpx.Response(200, json=test_data)
    )
    client = SeatDataClient(api_key="a" * 64)
    result = client.get_event_request_status(job_id="test-job-123")
    assert result == test_data


@respx.mock
def test_event_request_status_alias_emits_deprecation():
    import warnings
    respx.get("https://seatdata.io/api/v0.4/events/event-request-status/x/").mock(
        return_value=httpx.Response(200, json={"job_id": "x"})
    )
    client = SeatDataClient(api_key="a" * 64)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client.event_request_status(job_id="x")
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
```

- [ ] **Step 2: Run, expect AttributeError**

Run: `pytest tests/test_client.py::TestSeatDataClient::test_get_event_request_status_success -v`
Expected: AttributeError.

- [ ] **Step 3: Rename and add alias**

In `seatdata/client.py`, rename `event_request_status` → `get_event_request_status`. Add deprecated alias:

```python
def event_request_status(self, job_id: str) -> Dict[str, Any]:
    warnings.warn(
        "event_request_status() is deprecated. Use get_event_request_status() instead. "
        "This alias will be removed in v1.1.",
        DeprecationWarning,
        stacklevel=2,
    )
    return self.get_event_request_status(job_id)
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/ -v`
Expected: ALL pass.

- [ ] **Step 5: Commit**

```bash
git add seatdata/client.py tests/test_client.py
git commit -m "feat: rename event_request_status to get_event_request_status (alias kept, deprecated)"
```

---

### Task 18: Update `seatdata/__init__.py` exports

**Files:**
- Modify: `seatdata/__init__.py`

- [ ] **Step 1: Replace `__init__.py` contents**

```python
from .client import SeatDataClient
from .exceptions import (
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
from . import types

__version__ = "1.0.0"
__all__ = [
    "SeatDataClient",
    "SeatDataError",
    "SeatDataAuthError",
    "SeatDataRateLimitError",
    "SeatDataNotFoundError",
    "SeatDataInvalidRequestError",
    "SeatDataSubscriptionError",
    "SeatDataServerError",
    "CursorExpiredError",
    "SeatDataException",
    "AuthenticationError",
    "RateLimitError",
    "SubscriptionError",
    "NotFoundError",
    "ServiceUnavailableError",
    "types",
    "__version__",
]
```

(The `AsyncSeatDataClient` export is added in Task 21 once it exists.)

- [ ] **Step 2: Verify imports work**

Run: `python -c "from seatdata import SeatDataClient, SeatDataError, types; print(types.AccountResponse)"`
Expected: a TypedDict class is printed.

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v 2>&1 | tail -10`
Expected: ALL pass.

- [ ] **Step 4: Commit**

```bash
git add seatdata/__init__.py
git commit -m "feat: update __init__ exports for v1.0.0 (new exception names, types submodule)"
```

---

## Phase D — Async Client

### Task 19: Add `AsyncPageIterator` to `seatdata/pagination.py`

**Files:**
- Modify: `seatdata/pagination.py`
- Modify: `tests/test_pagination.py`

- [ ] **Step 1: Write failing async iterator tests**

Append to `tests/test_pagination.py`:

```python
import pytest


class TestAsyncPageIterator:
    @pytest.mark.asyncio
    async def test_yields_items_from_pages(self):
        from seatdata.pagination import AsyncPageIterator

        pages_iter = iter([
            {"data": [1, 2], "has_more": True, "next_cursor": "c1"},
            {"data": [3], "has_more": False, "next_cursor": None},
        ])

        async def fetch(cursor):
            return next(pages_iter)

        items = []
        async for item in AsyncPageIterator(fetch):
            items.append(item)
        assert items == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_current_cursor_async(self):
        from seatdata.pagination import AsyncPageIterator

        pages_iter = iter([
            {"data": [1], "has_more": True, "next_cursor": "c1"},
            {"data": [2], "has_more": False, "next_cursor": None},
        ])

        async def fetch(cursor):
            return next(pages_iter)

        it = AsyncPageIterator(fetch)
        await it.__anext__()
        await it.__anext__()
        assert it.current_cursor == "c1"

    @pytest.mark.asyncio
    async def test_async_cursor_expired_enriched(self):
        from seatdata.exceptions import CursorExpiredError
        from seatdata.pagination import AsyncPageIterator

        async def fetch(cursor):
            if cursor is None:
                return {"data": [1, 2], "has_more": True, "next_cursor": "c1"}
            raise CursorExpiredError("expired", error_code="invalid_cursor")

        it = AsyncPageIterator(fetch)
        await it.__anext__()
        await it.__anext__()
        with pytest.raises(CursorExpiredError) as exc_info:
            await it.__anext__()
        assert exc_info.value.items_yielded == 2
        assert exc_info.value.last_cursor == "c1"
```

Add `asyncio_mode = auto` to pytest config — modify `pytest.ini`:

```
[pytest]
markers =
    integration: marks tests as integration tests (deselect with '-m "not integration"')

asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 2: Run, expect ImportError**

Run: `pytest tests/test_pagination.py::TestAsyncPageIterator -v`
Expected: ImportError.

- [ ] **Step 3: Add `AsyncPageIterator` to `pagination.py`**

Append to `seatdata/pagination.py`:

```python
from typing import AsyncIterator as _AsyncIterator, Awaitable


class AsyncPageIterator(Generic[T]):
    def __init__(
        self,
        fetch_page: Callable[[Optional[str]], Awaitable[Envelope]],
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
        return self._current_cursor

    def __aiter__(self) -> "AsyncPageIterator[T]":
        return self

    async def __anext__(self) -> T:
        if self._buffer:
            item = self._buffer.pop(0)
            self._items_yielded += 1
            return item
        if self._exhausted:
            raise StopAsyncIteration
        try:
            page = await self._fetch_page(self._next_cursor)
        except CursorExpiredError as e:
            e.items_yielded = self._items_yielded
            e.last_cursor = self._next_cursor
            raise
        self._current_cursor = self._next_cursor
        self._buffer = list(page.get(self._item_key, []))
        self._next_cursor = page.get("next_cursor")
        self._exhausted = not page.get("has_more", False)
        if not self._buffer:
            raise StopAsyncIteration
        item = self._buffer.pop(0)
        self._items_yielded += 1
        return item
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_pagination.py -v`
Expected: ALL pass (sync + async).

- [ ] **Step 5: Commit**

```bash
git add seatdata/pagination.py tests/test_pagination.py pytest.ini
git commit -m "feat: add AsyncPageIterator for async cursor pagination"
```

---

### Task 20: Add async methods to `_Transport` (lazy `httpx.AsyncClient`)

**Files:**
- Modify: `seatdata/_transport.py`
- Modify: `tests/test_transport.py`

- [ ] **Step 1: Write failing async tests**

Append to `tests/test_transport.py`:

```python
class TestAsyncTransport:
    @pytest.mark.asyncio
    @respx.mock
    async def test_arequest_json_returns_parsed_body(self):
        t = _Transport(api_key="a" * 64, max_retries=0)
        try:
            respx.get("https://seatdata.io/api/v1/account").mock(
                return_value=httpx.Response(200, json={"user_id": 1})
            )
            result = await t.arequest_json("GET", "/api/v1/account")
            assert result == {"user_id": 1}
        finally:
            await t.aclose()

    @pytest.mark.asyncio
    @respx.mock
    async def test_arequest_json_retries_on_429(self):
        t = _Transport(api_key="a" * 64, max_retries=1)
        try:
            respx.get("https://seatdata.io/api/v1/x").mock(
                side_effect=[
                    httpx.Response(429, headers={"Retry-After": "0"}, json={
                        "error": {"type": "rate_limit_error", "code": "x", "message": "x"}
                    }),
                    httpx.Response(200, json={"ok": True}),
                ]
            )
            result = await t.arequest_json("GET", "/api/v1/x")
            assert result == {"ok": True}
        finally:
            await t.aclose()

    @pytest.mark.asyncio
    @respx.mock
    async def test_arequest_text_returns_body(self):
        t = _Transport(api_key="a" * 64, max_retries=0)
        try:
            respx.get("https://seatdata.io/api/v0.5/daily-csv/download").mock(
                return_value=httpx.Response(200, text="a,b\n1,2")
            )
            result = await t.arequest_text("GET", "/api/v0.5/daily-csv/download")
            assert result == "a,b\n1,2"
        finally:
            await t.aclose()

    def test_async_client_is_not_created_until_first_async_call(self):
        t = _Transport(api_key="a" * 64)
        try:
            assert t._async_client is None
        finally:
            t.close()
```

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/test_transport.py::TestAsyncTransport -v`
Expected: AttributeError — `arequest_json` doesn't exist.

- [ ] **Step 3: Add async methods to `_Transport`**

Add to `seatdata/_transport.py`:

```python
import asyncio


def _ensure_async_client(self: "_Transport") -> httpx.AsyncClient:
    if self._async_client is None:
        self._async_client = httpx.AsyncClient(
            timeout=self._timeout,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "User-Agent": _user_agent(),
            },
        )
    return self._async_client
```

(Make this a method on `_Transport` instead of a free function — reorganize:)

Inside `class _Transport`:

```python
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
```

(Also replace the existing `close()` to NOT call aclose — they are separate.)

```python
def close(self) -> None:
    self._client.close()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_transport.py -v`
Expected: ALL pass (sync + async).

- [ ] **Step 5: Commit**

```bash
git add seatdata/_transport.py tests/test_transport.py
git commit -m "feat: add async request methods to _Transport (lazy AsyncClient init)"
```

---

### Task 21: Create `AsyncSeatDataClient`

**Files:**
- Create: `seatdata/async_client.py`
- Modify: `seatdata/__init__.py`
- Create: `tests/test_async_client.py`

- [ ] **Step 1: Write failing tests for async client**

Create `tests/test_async_client.py`:

```python
import httpx
import pytest
import respx

from seatdata import AsyncSeatDataClient


class TestAsyncSeatDataClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_account(self):
        respx.get("https://seatdata.io/api/v1/account").mock(
            return_value=httpx.Response(200, json={"user_id": 1, "email": "x", "plans": [], "rate_limits": {}})
        )
        async with AsyncSeatDataClient(api_key="a" * 64) as client:
            result = await client.get_account()
            assert result["user_id"] == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_events(self):
        respx.get("https://seatdata.io/api/v1/events/search").mock(
            return_value=httpx.Response(200, json={
                "data": [{
                    "event_id": 1, "event_name": "X", "event_date": "2026-06-15",
                    "days_on_seatdata": 1, "first_seen_date": "2026-06-14",
                    "venue_name": "V", "venue_city": "C", "venue_state": "NJ",
                }],
                "has_more": False, "next_cursor": None,
            })
        )
        async with AsyncSeatDataClient(api_key="a" * 64) as client:
            items = await client.search_events(event_name="X")
            assert items[0]["event_id"] == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_iter_search_events(self):
        respx.get("https://seatdata.io/api/v1/events/search").mock(
            side_effect=[
                httpx.Response(200, json={
                    "data": [{
                        "event_id": 1, "event_name": "X", "event_date": "2026-06-15",
                        "days_on_seatdata": 1, "first_seen_date": "2026-06-14",
                        "venue_name": "V", "venue_city": "C", "venue_state": "NJ",
                    }],
                    "has_more": True, "next_cursor": "c1",
                }),
                httpx.Response(200, json={
                    "data": [{
                        "event_id": 2, "event_name": "Y", "event_date": "2026-06-16",
                        "days_on_seatdata": 1, "first_seen_date": "2026-06-15",
                        "venue_name": "V", "venue_city": "C", "venue_state": "NJ",
                    }],
                    "has_more": False, "next_cursor": None,
                }),
            ]
        )
        async with AsyncSeatDataClient(api_key="a" * 64) as client:
            ids = []
            async for item in client.iter_search_events():
                ids.append(item["event_id"])
        assert ids == [1, 2]

    @pytest.mark.asyncio
    @respx.mock
    async def test_iter_event_stats(self):
        url = "https://seatdata.io/api/v1/events/12345/stats"
        respx.get(url).mock(
            side_effect=[
                httpx.Response(200, json={
                    "event_id": 12345,
                    "data": [{"timestamp": "2026-04-26T14:30:00Z",
                              "total_listings_all": 1, "total_listings_active": 1,
                              "listing_fill_rate": 1.0, "avg_price": 1, "median_price": 1,
                              "get_in": 1, "get_in_qty2plus": 1, "zones": []}],
                    "has_more": True, "next_cursor": "c1",
                    "available_zones": [], "total_count": 2,
                }),
                httpx.Response(200, json={
                    "event_id": 12345,
                    "data": [{"timestamp": "2026-04-26T15:00:00Z",
                              "total_listings_all": 1, "total_listings_active": 1,
                              "listing_fill_rate": 1.0, "avg_price": 1, "median_price": 1,
                              "get_in": 1, "get_in_qty2plus": 1, "zones": []}],
                    "has_more": False, "next_cursor": None,
                }),
            ]
        )
        async with AsyncSeatDataClient(api_key="a" * 64) as client:
            timestamps = [s["timestamp"] async for s in client.iter_event_stats(12345)]
        assert timestamps == ["2026-04-26T14:30:00Z", "2026-04-26T15:00:00Z"]

    @pytest.mark.asyncio
    async def test_invalid_api_key_raises(self):
        with pytest.raises(ValueError, match="API key must be a 64-character hexadecimal string"):
            AsyncSeatDataClient(api_key="short")
```

- [ ] **Step 2: Run, expect ImportError**

Run: `pytest tests/test_async_client.py -v`
Expected: ImportError.

- [ ] **Step 3: Create `seatdata/async_client.py`**

```python
import warnings
from typing import Any, Dict, List, Optional, cast

from ._transport import _Transport
from .exceptions import SeatDataError
from .pagination import AsyncPageIterator
from .types import (
    AccountResponse,
    EventSearchItem,
    EventSearchPage,
    EventStatsPage,
    EventStatsSnapshot,
    UsageResponse,
)


class AsyncSeatDataClient:
    BASE_URL = "https://seatdata.io"

    def __init__(
        self,
        api_key: str,
        timeout: int = 30,
        max_retries: int = 3,
        base_url: Optional[str] = None,
    ) -> None:
        if not api_key or len(api_key) != 64:
            raise ValueError("API key must be a 64-character hexadecimal string")
        self._api_key = api_key
        self.timeout = timeout
        self._transport = _Transport(
            api_key=api_key,
            base_url=base_url or self.BASE_URL,
            timeout=timeout,
            max_retries=max_retries,
        )

    async def get_account(self) -> AccountResponse:
        return cast(AccountResponse, await self._transport.arequest_json("GET", "/api/v1/account"))

    async def get_usage(self) -> UsageResponse:
        return cast(UsageResponse, await self._transport.arequest_json("GET", "/api/v1/usage"))

    async def search_events(
        self,
        event_name: Optional[str] = None,
        event_date: Optional[str] = None,
        venue_name: Optional[str] = None,
        venue_city: Optional[str] = None,
        venue_state: Optional[str] = None,
        country_code: Optional[str] = None,
        tm_event_id: Optional[str] = None,
        std_event_id: Optional[int] = None,
        std_venue_id: Optional[int] = None,
        venue_slug: Optional[str] = None,
        historical: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> List[EventSearchItem]:
        page = await self.search_events_page(
            event_name=event_name, event_date=event_date, venue_name=venue_name,
            venue_city=venue_city, venue_state=venue_state, country_code=country_code,
            tm_event_id=tm_event_id, std_event_id=std_event_id, std_venue_id=std_venue_id,
            venue_slug=venue_slug, historical=historical, limit=limit,
        )
        return cast(List[EventSearchItem], page["data"])

    async def search_events_page(
        self,
        event_name: Optional[str] = None,
        event_date: Optional[str] = None,
        venue_name: Optional[str] = None,
        venue_city: Optional[str] = None,
        venue_state: Optional[str] = None,
        country_code: Optional[str] = None,
        tm_event_id: Optional[str] = None,
        std_event_id: Optional[int] = None,
        std_venue_id: Optional[int] = None,
        venue_slug: Optional[str] = None,
        historical: Optional[bool] = None,
        limit: Optional[int] = None,
        starting_after: Optional[str] = None,
    ) -> EventSearchPage:
        params: Dict[str, Any] = {}
        if event_name is not None:
            params["event_name"] = event_name
        if event_date is not None:
            params["event_date"] = event_date
        if venue_name is not None:
            params["venue_name"] = venue_name
        if venue_city is not None:
            params["venue_city"] = venue_city
        if venue_state is not None:
            params["venue_state"] = venue_state
        if country_code is not None:
            params["country_code"] = country_code
        if tm_event_id is not None:
            params["tm_event_id"] = tm_event_id
        if std_event_id is not None:
            params["std_event_id"] = std_event_id
        if std_venue_id is not None:
            params["std_venue_id"] = std_venue_id
        if venue_slug is not None:
            params["venue_slug"] = venue_slug
        if historical is not None:
            params["historical"] = "true" if historical else "false"
        if limit is not None:
            params["limit"] = limit
        if starting_after is not None:
            params["starting_after"] = starting_after
        return cast(
            EventSearchPage,
            await self._transport.arequest_json("GET", "/api/v1/events/search", params=params),
        )

    def iter_search_events(
        self,
        event_name: Optional[str] = None,
        event_date: Optional[str] = None,
        venue_name: Optional[str] = None,
        venue_city: Optional[str] = None,
        venue_state: Optional[str] = None,
        country_code: Optional[str] = None,
        tm_event_id: Optional[str] = None,
        std_event_id: Optional[int] = None,
        std_venue_id: Optional[int] = None,
        venue_slug: Optional[str] = None,
        historical: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> AsyncPageIterator[EventSearchItem]:
        async def fetch(cursor: Optional[str]) -> Dict[str, Any]:
            return cast(
                Dict[str, Any],
                await self.search_events_page(
                    event_name=event_name, event_date=event_date, venue_name=venue_name,
                    venue_city=venue_city, venue_state=venue_state, country_code=country_code,
                    tm_event_id=tm_event_id, std_event_id=std_event_id, std_venue_id=std_venue_id,
                    venue_slug=venue_slug, historical=historical, limit=limit,
                    starting_after=cursor,
                ),
            )
        return AsyncPageIterator(fetch)

    async def get_event_stats(
        self,
        event_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        starting_after: Optional[str] = None,
    ) -> EventStatsPage:
        params: Dict[str, Any] = {}
        if start_date is not None:
            params["start_date"] = start_date
        if end_date is not None:
            params["end_date"] = end_date
        if limit is not None:
            params["limit"] = limit
        if starting_after is not None:
            params["starting_after"] = starting_after
        return cast(
            EventStatsPage,
            await self._transport.arequest_json(
                "GET", f"/api/v1/events/{event_id}/stats", params=params
            ),
        )

    def iter_event_stats(
        self,
        event_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> AsyncPageIterator[EventStatsSnapshot]:
        async def fetch(cursor: Optional[str]) -> Dict[str, Any]:
            return cast(
                Dict[str, Any],
                await self.get_event_stats(
                    event_id, start_date=start_date, end_date=end_date,
                    limit=limit, starting_after=cursor,
                ),
            )
        return AsyncPageIterator(fetch)

    async def get_sales_data(
        self, event_id: Optional[str] = None, event_id_sh: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not event_id and not event_id_sh:
            raise ValueError("Either event_id or event_id_sh must be provided")
        params: Dict[str, Any] = {}
        if event_id:
            params["event_id"] = event_id
        if event_id_sh:
            params["event_id_sh"] = event_id_sh
        return cast(
            List[Dict[str, Any]],
            await self._transport.arequest_json("GET", "/api/v0.3/salesdata/get", params=params),
        )

    async def get_listings(
        self, event_id: Optional[str] = None, event_id_sh: Optional[str] = None
    ) -> Dict[str, Any]:
        if not event_id and not event_id_sh:
            raise ValueError("Either event_id or event_id_sh must be provided")
        params: Dict[str, Any] = {}
        if event_id:
            params["event_id"] = event_id
        if event_id_sh:
            params["event_id_sh"] = event_id_sh
        return cast(
            Dict[str, Any],
            await self._transport.arequest_json("GET", "/api/v0.1/listings/get", params=params),
        )

    async def download_daily_csv(self, date: Optional[str] = None) -> str:
        params: Dict[str, Any] = {}
        if date:
            params["date"] = date
        return await self._transport.arequest_text(
            "GET", "/api/v0.5/daily-csv/download", params=params
        )

    async def create_event_request(self, search_query: str) -> Dict[str, Any]:
        if not search_query:
            raise ValueError("search_query must be provided")
        response = await self._transport.arequest_json(
            "POST",
            "/api/v0.4/events/event-request-add",
            json={"search_query": search_query},
            retry_safe=False,
        )
        if response is None:
            raise SeatDataError("Empty response from API")
        return cast(Dict[str, Any], response)

    async def get_event_request_status(self, job_id: str) -> Dict[str, Any]:
        if not job_id:
            raise ValueError("job_id must be provided")
        response = await self._transport.arequest_json(
            "GET", f"/api/v0.4/events/event-request-status/{job_id}/"
        )
        if response is None:
            raise SeatDataError("Empty response from API")
        return cast(Dict[str, Any], response)

    async def event_request_add(self, search_query: str) -> Dict[str, Any]:
        warnings.warn(
            "event_request_add() is deprecated. Use create_event_request() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self.create_event_request(search_query)

    async def event_request_status(self, job_id: str) -> Dict[str, Any]:
        warnings.warn(
            "event_request_status() is deprecated. Use get_event_request_status() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self.get_event_request_status(job_id)

    async def search_events_legacy(
        self,
        event_name: Optional[str] = None,
        event_date: Optional[str] = None,
        venue_name: Optional[str] = None,
        venue_city: Optional[str] = None,
        venue_state: Optional[str] = None,
        return_full_response: bool = False,
        **kwargs: Any,
    ) -> Any:
        warnings.warn(
            "search_events_legacy() is deprecated. Use search_events() (v1 GET) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        params: Dict[str, Any] = {}
        if event_name:
            params["event_name"] = event_name
        if event_date:
            params["event_date"] = event_date
        if venue_name:
            params["venue_name"] = venue_name
        if venue_city:
            params["venue_city"] = venue_city
        if venue_state:
            params["venue_state"] = venue_state
        params.update(kwargs)
        response = await self._transport.arequest_json(
            "POST", "/api/v0.3.1/events/search", json=params
        )
        if return_full_response:
            return response
        if isinstance(response, dict) and "items" in response:
            return response["items"]
        return response

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def __aenter__(self) -> "AsyncSeatDataClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()
```

- [ ] **Step 4: Update `seatdata/__init__.py` to export `AsyncSeatDataClient`**

```python
from .async_client import AsyncSeatDataClient
```

(Add to imports and `__all__`.)

- [ ] **Step 5: Run all async tests**

Run: `pytest tests/test_async_client.py tests/test_pagination.py tests/test_transport.py -v`
Expected: ALL pass.

- [ ] **Step 6: Run full test suite**

Run: `pytest tests/ -v 2>&1 | tail -10`
Expected: ALL pass.

- [ ] **Step 7: Black + commit**

Run: `black seatdata/ tests/`

```bash
git add seatdata/async_client.py seatdata/__init__.py tests/test_async_client.py
git commit -m "feat: add AsyncSeatDataClient with v1 + v0.x methods and deprecated aliases"
```

---

## Phase E — Release Prep

### Task 22: Update README with v1 examples

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the Quick Start section**

Replace the `## Quick Start` section in `README.md`:

```markdown
## Quick Start

### Sync

```python
from seatdata import SeatDataClient

client = SeatDataClient(api_key="your_64_char_api_key")

# Verify auth + see your plans and rate limits
account = client.get_account()
print(account["plans"])

# Search events (v1) — returns list of items from one page
events = client.search_events(venue_name="Madison Square Garden", venue_city="New York")

# Or iterate all matching events across pages
for event in client.iter_search_events(performer="Taylor Swift"):
    print(event["event_id"], event["event_name"])

# Get event-level price/listing time series
for snapshot in client.iter_event_stats(event_id=12345):
    print(snapshot["timestamp"], snapshot["get_in"], snapshot["avg_price"])

# v0.x endpoints continue to work
sales = client.get_sales_data(event_id="1234567")
listings = client.get_listings(event_id="1234567")
csv = client.download_daily_csv()  # latest day
```

### Async

```python
import asyncio
from seatdata import AsyncSeatDataClient


async def main():
    async with AsyncSeatDataClient(api_key="your_64_char_api_key") as client:
        events = await client.search_events(performer="Taylor Swift")
        async for snapshot in client.iter_event_stats(events[0]["event_id"]):
            print(snapshot["timestamp"], snapshot["get_in"])


asyncio.run(main())
```

## Migrating from v0.3.x

- `search_events()` now calls `GET /v1/events/search` and returns the v1 envelope's `data`. The legacy `POST /v0.3.1/events/search` is available as `search_events_legacy()` (deprecated, removed in v1.1).
- `event_request_add` → `create_event_request`. `event_request_status` → `get_event_request_status`. Old names remain as deprecated aliases.
- Exceptions gained richer attributes: `SeatDataRateLimitError.retry_after`, `SeatDataInvalidRequestError.param`, `CursorExpiredError.items_yielded` / `.last_cursor`. Legacy exception names (`AuthenticationError`, `RateLimitError`, etc.) are preserved as aliases.
- The HTTP layer is now `httpx`. If you caught `requests.exceptions.*` directly, switch to `seatdata.SeatDataError`.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README quick start covers v1 sync and async usage plus migration notes"
```

---

### Task 23: Update CHANGELOG.md with v1.0.0 entry

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add v1.0.0 section at top of CHANGELOG.md**

Insert after the `# Changelog` header and intro:

```markdown
## [1.0.0] - 2026-04-30

### Added
- Support for SeatData v1 REST API endpoints: `get_account()`, `get_usage()`, `search_events_page()`, `iter_search_events()`, `get_event_stats()`, `iter_event_stats()`.
- New `AsyncSeatDataClient` for async/await usage.
- Cursor-based auto-pagination via `PageIterator` / `AsyncPageIterator`.
- Typed response shapes (`seatdata.types.*`) for all v1 responses.
- Typed exception hierarchy: `SeatDataError`, `SeatDataAuthError`, `SeatDataRateLimitError`, `SeatDataNotFoundError`, `SeatDataInvalidRequestError`, `SeatDataSubscriptionError`, `SeatDataServerError`, `CursorExpiredError`.
- `SeatDataRateLimitError.retry_after` attribute (parsed from `Retry-After` header).
- `CursorExpiredError.items_yielded` and `.last_cursor` for resumable iteration.
- `parse_timestamp(ts)` helper for ISO-8601 UTC strings.
- Configurable retry/backoff with full jitter, honoring `Retry-After`. `max_retries` constructor argument (default 3).

### Changed
- **BREAKING:** `search_events()` now calls `GET /v1/events/search`. Removed `return_full_response=True` and `**kwargs`. Returns `List[EventSearchItem]` from one page; use `search_events_page()` for the envelope or `iter_search_events()` for auto-paginated iteration.
- HTTP layer migrated from `requests` to `httpx`. Public method signatures preserved; if you caught `requests.exceptions.*` directly, switch to catching `SeatDataError`.
- Auth header sent as `Authorization: Bearer <key>` for all requests (server still accepts the legacy `api-key` header).
- `event_request_add` → `create_event_request` (alias kept, deprecated).
- `event_request_status` → `get_event_request_status` (alias kept, deprecated).

### Deprecated
- `search_events_legacy()` — calls v0.3.1 POST search; will be removed in v1.1.
- `event_request_add()`, `event_request_status()` — use the renamed methods; aliases removed in v1.1.

### Dependencies
- Removed: `requests`.
- Added: `httpx>=0.27`, `typing_extensions>=4.0`.
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "chore: 1.0.0 changelog entry"
```

(`chore:` prefix per the user's preference: doc and chore commits stay out of user-facing release notes; the release notes will be drafted from the CHANGELOG content above.)

---

### Task 24: Bump version to 1.0.0

**Files:**
- Modify: `pyproject.toml`
- Modify: `seatdata/__init__.py` (already done in Task 18, verify)

- [ ] **Step 1: Update version in `pyproject.toml`**

Change `version = "0.3.0"` to `version = "1.0.0"`.

Also update the `Development Status` classifier — change:

```toml
"Development Status :: 3 - Alpha",
```

to:

```toml
"Development Status :: 5 - Production/Stable",
```

- [ ] **Step 2: Verify `__init__.py` has `__version__ = "1.0.0"`**

Run: `grep __version__ seatdata/__init__.py`
Expected: `__version__ = "1.0.0"`. (Already set in Task 18.)

- [ ] **Step 3: Reinstall to refresh metadata**

Run: `pip install -e ".[dev]" --quiet`

- [ ] **Step 4: Confirm User-Agent reads correct version**

```bash
python -c "from seatdata._transport import _user_agent; print(_user_agent())"
```

Expected output: `seatdata-python/1.0.0 httpx/X.Y.Z`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "chore: bump version to 1.0.0"
```

---

### Task 25: Final test pass + manual smoke check

**Files:** none modified.

- [ ] **Step 1: Run full unit test suite**

Run: `pytest tests/ -v 2>&1 | tail -30`
Expected: ALL pass; deprecation warnings present where expected; no regressions.

- [ ] **Step 2: Run mypy**

Run: `mypy seatdata/ 2>&1 | tail -20`
Expected: zero errors. If errors appear, fix them inline (most likely missed `cast` calls or wrong type annotations).

- [ ] **Step 3: Run black in check mode**

Run: `black --check seatdata/ tests/`
Expected: "would reformat 0 files".

- [ ] **Step 4: Smoke-test imports**

```bash
python -c "
from seatdata import (
    SeatDataClient, AsyncSeatDataClient,
    SeatDataError, SeatDataAuthError, SeatDataRateLimitError,
    SeatDataNotFoundError, SeatDataInvalidRequestError,
    SeatDataSubscriptionError, SeatDataServerError, CursorExpiredError,
    SeatDataException, AuthenticationError, RateLimitError,
    SubscriptionError, NotFoundError, ServiceUnavailableError,
    types, __version__,
)
from seatdata.types import (
    AccountResponse, UsageResponse, EventSearchItem, EventSearchPage,
    EventStatsSnapshot, EventStatsPage, EventStatsZone, ErrorEnvelope,
    parse_timestamp,
)
print('imports ok, version:', __version__)
"
```

Expected: `imports ok, version: 1.0.0`

- [ ] **Step 5: Optional integration test (if SEATDATA_API_KEY available)**

Run: `pytest -m integration tests/ -v` (skips if env var unset).
Expected: PASS or SKIP — never FAIL.

- [ ] **Step 6: Verify branch state**

Run: `git status && git log --oneline main..HEAD`
Expected: clean working tree; ~25 commits on `feat/v1-api-support` ahead of `main`.

- [ ] **Step 7: Final tag commit (no code change)**

If everything is green, the branch is ready for PR. No commit needed; just merge or open a PR.

---

## Coverage Verification (Self-Review)

| Spec section | Implementing tasks |
|---|---|
| §4 Module layout (client/async_client/_transport/exceptions/pagination/types) | Tasks 4, 5, 7, 8, 11, 21 |
| §5.1 Constructors with `base_url`, `timeout`, `max_retries` | Tasks 11, 21 |
| §5.2 Sync method surface | Tasks 11, 12, 13, 14, 15, 16, 17 |
| §5.3 Async method surface | Task 21 |
| §5.4 Iterator semantics (current_cursor, no __len__, CursorExpiredError) | Tasks 7, 15, 19 |
| §5.5 Public exports | Task 18 (sync), Task 21 (async) |
| §6.1 TypedDicts | Task 5 |
| §6.2 parse_timestamp | Task 6 |
| §7 Exception hierarchy + legacy aliases | Task 4 |
| §7 Mapping table for error.type | Tasks 8 (and Task 11 fallback for non-envelope responses) |
| §8.1 Transport surface | Tasks 8, 9, 10, 20 |
| §8.2 Behavior (Bearer, User-Agent, JSON/text, error parsing, retry, lazy async) | Tasks 8, 9, 10, 20 |
| §9 Pagination | Tasks 7, 19 |
| §10.1 Version bump | Task 24 |
| §10.2 Breaking changes | Tasks 13 (search_events), 11 (httpx swap), all (Bearer auth) |
| §10.3 Deprecations | Tasks 14, 16, 17 |
| §10.4 Migration guide | Task 22 (README), Task 23 (CHANGELOG) |
| §11 Dependencies | Task 1 |
| §12 Test strategy | Every task includes tests; respx is set up in Task 1 |
| §15 Acceptance criteria | Validated in Task 25 |

**Open question from spec §14 — `error.code` for cursor expiry.** The plan (Task 8) maps `error.code == "invalid_cursor"` → `CursorExpiredError`. If the live API uses a different code, adjust the mapping in `seatdata/_transport.py:_raise_from_response` after integration testing. This is the only place the assumption appears.

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-30-v1-api-support.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
