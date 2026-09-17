# v1 Sales Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the v1 sales endpoints to both SDK clients — `get_event_sales()`, `iter_event_sales()`, and `get_event_sales_batch()` — with SDK-wide `402 -> SeatDataPaymentError` handling, released additively as 1.1.0.

**Architecture:** Two new pure modules carry the shared logic. `seatdata/_sales.py` resolves the `event_id` / `event_id_sh` argument pair into a path id plus an optional `id_type`. `seatdata/_batch.py` (cherry-picked from the abandoned branch, unchanged) validates and normalizes batch payloads. Both clients add thin methods over the existing `_Transport`. `PageIterator` and `AsyncPageIterator` gain a `first_page` attribute so the server's first-page-only `total_count` and `sources` survive iteration. Rows are typed as a discriminated union on the `source` literal, because `sh` and `vs` rows have genuinely different key sets.

**Tech Stack:** Python 3.8+ (`typing` + `typing_extensions`), httpx, pytest + respx + pytest-asyncio, black (line length 100), mypy.

**Spec:** `docs/superpowers/specs/2026-09-16-v1-sales-adoption-design.md`

## Global Constraints

- Python 3.8+ compatibility. Annotations use `typing` (`Dict`, `List`, `Optional`, `Sequence`, `Tuple`, `Union`, `Any`) and `typing_extensions` (`TypedDict`, `NotRequired`, `Literal`) — match the existing files.
- **No comments in code files** (project preference). Implementation blocks below contain no comments. Docstrings are not comments; the mandated docstrings on the billed methods must not be removed.
- Black formatter, line length 100. `mypy seatdata/` must stay clean.
- Tests use `pytest` + `respx`. Base URL `https://seatdata.io`. Async tests follow `tests/test_async_client.py` (`@pytest.mark.asyncio` + `@respx.mock`; `pytest.ini` sets `asyncio_mode = auto`).
- Conventional commit prefixes (`feat:`, `test:`, `docs:`, `build:`, `fix:`). **No `Co-Authored-By` trailer** and no other attribution trailer in any commit message. Each task ends with its own commit.
- All commands run from `/home/chaz/Storage/CreativeStirLLC/SeatDataSDK-Python`.
- Full-suite runs use `pytest -m "not integration" -q`.
- Locate every edit by the exact code block shown, never by line number alone. Every "replace this exact block" anchor occurs exactly once in its file.
- **`CLAUDE.md` is untracked in git deliberately.** Edit it on disk when a task says to. Never `git add` it.
- **Keep every new test a `respx` unit test.** The v1 sales endpoints went live on 2026-09-17, but unit tests must not depend on a live service or spend metered calls.

## Execution model assignments

Planning runs on Opus at `max` effort. Implementation runs on Sonnet, except where a task is correctness-critical or subtle. The orchestrator and the between-task reviewer stay on Opus.

| Task | Model | Why |
|---|---|---|
| 0 | Sonnet | Preflight verification, no code |
| 1 | Sonnet | Mechanical cherry-pick, conflicts escalate to Opus |
| 2 | Sonnet | Mechanical cherry-pick |
| 3 | **Opus** | Discriminated union typing; mypy narrowing under 3.8 |
| 4 | **Opus** | Mutates a class shared by search and stats iterators |
| 5 | **Opus** | Cursor and parameter binding (D-01); an omission silently 400s on page two |
| 6 | Sonnet | Async mirror of task 5, code fully spelled out |
| 7 | **Opus** | Billing, retry policy, and two-shape 402 routing (D-04, D-05) |
| 8 | Sonnet | Async mirror of task 7, code fully spelled out |
| 9 | Sonnet | Single `warnings.warn` insertion |
| 10 | Sonnet | Version bump and docs |
| 11 | Sonnet | Example script and final gate |

## Settled decision: `listing_id` keeps its type split

`listing_id` stays an int on `sh` rows and a string on `vs` rows. A production query on
2026-09-16 found 275,913 Vivid Seats ids that are not digit-only, so no integer unification is
possible, and the alternative would break the deployed `/sales/live` endpoint. See D-02 in the
spec for the full reasoning.

**Task 3 ships exactly as written below. No line changes.**

---

## File Structure

| File | Responsibility |
|---|---|
| `seatdata/_sales.py` | **Create.** Pure resolution of the `event_id` / `event_id_sh` pair into `(path_id, id_type)`. |
| `seatdata/_batch.py` | **Cherry-pick.** Pure batch payload validation and response normalization. |
| `seatdata/types.py` | **Modify.** Row union, `SalesPage`, `SourceBlock`, `BatchSalesResult`. |
| `seatdata/pagination.py` | **Modify.** `first_page` capture on both iterators. |
| `seatdata/client.py` | **Modify.** Sync methods. |
| `seatdata/async_client.py` | **Modify.** Async methods. |
| `seatdata/exceptions.py` | **Cherry-pick.** `SeatDataPaymentError`. |
| `seatdata/_transport.py` | **Cherry-pick.** SDK-wide 402 routing. |

---

### Task 0: Preflight (no commit)

**Files:** none.

- [ ] **Step 1: Confirm a clean baseline**

Run:
```bash
git status --short
git rev-parse --abbrev-ref HEAD
pytest -m "not integration" -q
mypy seatdata/
black --check seatdata/ tests/ examples/
```
Expected: on `main`, tests green, mypy clean, black clean. `CLAUDE.md` and the two stray
`examples/*.py` files show as untracked; that is expected and must stay untracked.

- [ ] **Step 2: Confirm the source commits still exist**

Run:
```bash
git log --oneline main..feat/batch-salesdata
```
Expected: 11 commits, `748fa9f` through `f7d3cc7`.

- [ ] **Step 3: Record the baseline**

Write the test count, the mypy file count, and the current HEAD into the execution ledger.
No commit.

---

### Task 1: Stage 1 — 402 handling and the semver retarget (own PR)

**Files:**
- Modify: `seatdata/exceptions.py`, `seatdata/__init__.py`, `seatdata/_transport.py`, `seatdata/client.py`, `README.md`
- Test: `tests/test_exceptions.py`, `tests/test_transport.py`, `tests/test_client.py`

**Interfaces:**
- Produces: `SeatDataPaymentError`, exported from `seatdata`. Raised for every HTTP 402 regardless of body shape.

This task lands as **its own PR, merged before Task 2 starts**. It is additive and fixes 402
handling for `get_sales_data()` and `get_listings()` on `main` today.

- [ ] **Step 1: Branch off main**

```bash
git checkout main
git checkout -b fix/payment-error-402
```

- [ ] **Step 2: Cherry-pick the four commits**

```bash
git cherry-pick 748fa9f 7fbc572 3f18eb4 5aebcea
```
Expected: four commits applied with no conflict. If any conflict appears, stop and escalate to
Opus — do not resolve it mechanically.

- [ ] **Step 3: Verify**

```bash
pytest -m "not integration" -q
mypy seatdata/
black --check seatdata/ tests/
```
Expected: all green. Test count rises by the transport and exception tests those commits carry.

- [ ] **Step 4: Confirm the behaviour directly**

```bash
python -c "
import seatdata
print(seatdata.SeatDataPaymentError.__mro__[1].__name__)
"
```
Expected: `SeatDataError`.

- [ ] **Step 5: Open the PR and merge**

Merge to `main` before continuing. Every later task assumes `SeatDataPaymentError` exists.

---

### Task 2: Cherry-pick the batch foundations

**Files:**
- Create: `seatdata/_batch.py`
- Modify: `seatdata/types.py`
- Test: `tests/test_batch.py`, `tests/test_types.py`

**Interfaces:**
- Consumes: nothing from Task 1 beyond a merged `main`.
- Produces: `prepare_batch_payload(event_ids_sh, event_ids) -> Dict[str, List[int]]` and `normalize_batch_response(body) -> BatchSalesResult`, plus a `BatchSalesResult` TypedDict. Task 3 retypes `BatchSalesResult`; Task 7 calls both functions.

`prepare_batch_payload` needs no change for v1. Its dedupe, int and digit-string coercion, bool
rejection, and 100-id cap already match the v1 server's `_parse_batch_salesdata_body` exactly.

- [ ] **Step 1: Branch off the updated main**

```bash
git checkout main
git pull
git checkout -b feat/v1-sales
```

- [ ] **Step 2: Cherry-pick**

```bash
git cherry-pick 78e4b4e e03ff37
```
Expected: two commits applied cleanly. `78e4b4e` adds `BatchSalesResult`; `e03ff37` adds
`seatdata/_batch.py` and `tests/test_batch.py`.

- [ ] **Step 3: Verify**

```bash
pytest -m "not integration" -q
mypy seatdata/
```
Expected: green. `tests/test_batch.py` adds 107 lines of coverage for the payload helpers.

- [ ] **Step 4: Confirm the cap semantics match the server**

```bash
python -c "
from seatdata._batch import prepare_batch_payload
print(prepare_batch_payload([1, '1', 2], [3]))
try:
    prepare_batch_payload(list(range(60)), list(range(60)))
except ValueError as e:
    print('cap:', e)
"
```
Expected: `{'event_ids_sh': [1, 2], 'event_ids': [3]}` then a cap error naming 120. Per-list
dedup then sum is the server's rule, so an id present in both lists legitimately counts twice.

No commit of its own; the cherry-picks are the commits.

---

### Task 3: Row and page types

**Files:**
- Modify: `seatdata/types.py`
- Test: `tests/test_types.py`

**Interfaces:**
- Consumes: `BatchSalesResult` from Task 2.
- Produces: `SourceBlock`, `SHSalesRow`, `VSSalesRow`, `SalesRow`, `SalesPage`, and a retyped `BatchSalesResult`. Tasks 5 through 8 annotate against these.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_types.py`:

```python
def test_sales_row_union_narrows_on_source():
    from seatdata.types import SHSalesRow, VSSalesRow

    sh: SHSalesRow = {
        "source": "sh",
        "listing_id": 105294241,
        "all_in_price": None,
        "timestamp": 1757000000,
        "quantity": 2,
        "price": 145.0,
        "zone": "Lower Bowl",
        "section": "112",
        "row": "F",
    }
    vs: VSSalesRow = {
        "source": "vs",
        "listing_id": "vs-1",
        "all_in_price": 188.5,
        "timestamp": 1757000100,
        "quantity": 1,
        "price": 150.0,
        "zone": "",
        "section": "Lower Bowl 112",
        "row": "F",
        "norm_zone": "Lower Bowl",
        "norm_section": "112",
    }
    assert sh["source"] == "sh"
    assert vs["source"] == "vs"
    assert sh["all_in_price"] is None
    assert isinstance(vs["listing_id"], str)
    assert "norm_zone" not in sh


def test_sales_page_shape():
    from seatdata.types import SalesPage

    page: SalesPage = {
        "event_id": 225220,
        "data": [],
        "has_more": False,
        "next_cursor": None,
        "total_count": 0,
        "sources": [
            {
                "source": "sh",
                "collecting_since": "2024-03-01",
                "tracked_for_event": True,
                "status": "ok",
            },
            {
                "source": "vs",
                "collecting_since": None,
                "tracked_for_event": False,
                "status": "ok",
            },
        ],
    }
    assert page["sources"][1]["tracked_for_event"] is False


def test_batch_sales_result_carries_sources():
    from seatdata.types import BatchSalesResult

    result: BatchSalesResult = {"results": {}, "errors": {}, "sources": {}}
    assert result["sources"] == {}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_types.py -q`
Expected: FAIL with `ImportError: cannot import name 'SHSalesRow'`.

- [ ] **Step 3: Widen the imports**

Replace this exact block at the top of `seatdata/types.py`:

```python
from typing import Any, Dict, List, Optional
from typing_extensions import NotRequired, TypedDict
```

with:

```python
from typing import Any, Dict, List, Optional, Union
from typing_extensions import Literal, NotRequired, TypedDict
```

- [ ] **Step 4: Add the types**

Replace this exact block in `seatdata/types.py`:

```python
class BatchSalesResult(TypedDict):
    results: Dict[str, List[Dict[str, Any]]]
    errors: Dict[str, str]
```

with:

```python
class SourceBlock(TypedDict):
    source: str
    collecting_since: Optional[str]
    tracked_for_event: bool
    status: str


class SHSalesRow(TypedDict):
    source: Literal["sh"]
    listing_id: int
    all_in_price: None
    timestamp: int
    quantity: int
    price: float
    zone: str
    section: str
    row: str


class VSSalesRow(TypedDict):
    source: Literal["vs"]
    listing_id: str
    all_in_price: Optional[float]
    timestamp: int
    quantity: int
    price: float
    zone: str
    section: str
    row: str
    norm_zone: str
    norm_section: str


SalesRow = Union[SHSalesRow, VSSalesRow]


class SalesPage(TypedDict):
    event_id: int
    data: List[SalesRow]
    has_more: bool
    next_cursor: Optional[str]
    total_count: NotRequired[int]
    sources: NotRequired[List[SourceBlock]]


class BatchSalesResult(TypedDict):
    results: Dict[str, List[SalesRow]]
    errors: Dict[str, str]
    sources: Dict[str, List[SourceBlock]]
```

- [ ] **Step 5: Update `normalize_batch_response` for the third key**

Replace this exact block in `seatdata/_batch.py`:

```python
def normalize_batch_response(body: Any) -> BatchSalesResult:
    data = body or {}
    return {
        "results": data.get("results") or {},
        "errors": data.get("errors") or {},
    }
```

with:

```python
def normalize_batch_response(body: Any) -> BatchSalesResult:
    data = body or {}
    return {
        "results": data.get("results") or {},
        "errors": data.get("errors") or {},
        "sources": data.get("sources") or {},
    }
```

- [ ] **Step 6: Run the tests**

Run:
```bash
pytest tests/test_types.py tests/test_batch.py -q
mypy seatdata/
```
Expected: PASS, mypy clean. If `tests/test_batch.py` asserts a two-key dict from
`normalize_batch_response`, update those assertions to expect three keys.

- [ ] **Step 7: Commit**

```bash
git add seatdata/types.py seatdata/_batch.py tests/test_types.py tests/test_batch.py
git commit -m "feat: add v1 sales row union, SalesPage, and SourceBlock types"
```

---

### Task 4: `first_page` capture on both iterators

**Files:**
- Modify: `seatdata/pagination.py`
- Test: `tests/test_pagination.py`

**Interfaces:**
- Produces: `PageIterator.first_page` and `AsyncPageIterator.first_page`, both `Optional[Envelope]`, `None` until the first successful fetch.

This class is shared by the search and stats iterators. The change is additive: a new attribute,
no behaviour change to existing callers. Do not alter `__next__`'s control flow.

- [ ] **Step 1: Write the failing test**

Create or append to `tests/test_pagination.py`:

```python
import pytest

from seatdata.pagination import AsyncPageIterator, PageIterator


def test_first_page_is_none_before_fetch():
    it = PageIterator(lambda cursor: {"data": [1], "has_more": False, "next_cursor": None})
    assert it.first_page is None


def test_first_page_captured_and_not_overwritten():
    pages = [
        {"data": [1], "has_more": True, "next_cursor": "c1", "total_count": 2},
        {"data": [2], "has_more": False, "next_cursor": None},
    ]
    calls = {"n": 0}

    def fetch(cursor):
        page = pages[calls["n"]]
        calls["n"] += 1
        return page

    it = PageIterator(fetch)
    assert list(it) == [1, 2]
    assert it.first_page is not None
    assert it.first_page["total_count"] == 2


@pytest.mark.asyncio
async def test_async_first_page_captured():
    pages = [
        {"data": [1], "has_more": True, "next_cursor": "c1", "total_count": 5},
        {"data": [2], "has_more": False, "next_cursor": None},
    ]
    calls = {"n": 0}

    async def fetch(cursor):
        page = pages[calls["n"]]
        calls["n"] += 1
        return page

    it = AsyncPageIterator(fetch)
    got = [item async for item in it]
    assert got == [1, 2]
    assert it.first_page["total_count"] == 5
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_pagination.py -q`
Expected: FAIL with `AttributeError: 'PageIterator' object has no attribute 'first_page'`.

- [ ] **Step 3: Add the attribute to `PageIterator.__init__`**

Replace this exact block in `seatdata/pagination.py`:

```python
        self._exhausted = False
        self._items_yielded = 0
        self._current_cursor: Optional[str] = None

    @property
    def current_cursor(self) -> Optional[str]:
        return self._current_cursor

    def __iter__(self) -> "PageIterator[T]":
        return self
```

with:

```python
        self._exhausted = False
        self._items_yielded = 0
        self._current_cursor: Optional[str] = None
        self.first_page: Optional[Envelope] = None

    @property
    def current_cursor(self) -> Optional[str]:
        return self._current_cursor

    def __iter__(self) -> "PageIterator[T]":
        return self
```

- [ ] **Step 4: Capture it in `__next__`**

Replace this exact block in `seatdata/pagination.py`:

```python
        self._current_cursor = self._next_cursor
        self._buffer = list(page.get(self._item_key, []))
        self._next_cursor = page.get("next_cursor")
        self._exhausted = not page.get("has_more", False)
        if not self._buffer:
            raise StopIteration
```

with:

```python
        self._current_cursor = self._next_cursor
        if self.first_page is None:
            self.first_page = page
        self._buffer = list(page.get(self._item_key, []))
        self._next_cursor = page.get("next_cursor")
        self._exhausted = not page.get("has_more", False)
        if not self._buffer:
            raise StopIteration
```

- [ ] **Step 5: Add the attribute to `AsyncPageIterator.__init__`**

Replace this exact block in `seatdata/pagination.py`:

```python
        self._exhausted = False
        self._items_yielded = 0
        self._current_cursor: Optional[str] = None

    @property
    def current_cursor(self) -> Optional[str]:
        return self._current_cursor

    def __aiter__(self) -> "AsyncPageIterator[T]":
        return self
```

with:

```python
        self._exhausted = False
        self._items_yielded = 0
        self._current_cursor: Optional[str] = None
        self.first_page: Optional[Envelope] = None

    @property
    def current_cursor(self) -> Optional[str]:
        return self._current_cursor

    def __aiter__(self) -> "AsyncPageIterator[T]":
        return self
```

- [ ] **Step 6: Capture it in `__anext__`**

Replace this exact block in `seatdata/pagination.py`:

```python
        self._current_cursor = self._next_cursor
        self._buffer = list(page.get(self._item_key, []))
        self._next_cursor = page.get("next_cursor")
        self._exhausted = not page.get("has_more", False)
        if not self._buffer:
            raise StopAsyncIteration
```

with:

```python
        self._current_cursor = self._next_cursor
        if self.first_page is None:
            self.first_page = page
        self._buffer = list(page.get(self._item_key, []))
        self._next_cursor = page.get("next_cursor")
        self._exhausted = not page.get("has_more", False)
        if not self._buffer:
            raise StopAsyncIteration
```

- [ ] **Step 7: Run the tests**

Run:
```bash
pytest tests/test_pagination.py -q
pytest -m "not integration" -q
mypy seatdata/
```
Expected: PASS, and the existing search and stats iterator tests still green.

- [ ] **Step 8: Commit**

```bash
git add seatdata/pagination.py tests/test_pagination.py
git commit -m "feat: capture the first page envelope on both page iterators"
```

---

### Task 5: Sync `get_event_sales()` and `iter_event_sales()`

**Files:**
- Create: `seatdata/_sales.py`
- Modify: `seatdata/client.py`
- Test: `tests/test_sales.py`, `tests/test_client.py`

**Interfaces:**
- Consumes: `SalesPage`, `SalesRow`, `SourceBlock` from Task 3; `first_page` from Task 4.
- Produces: `resolve_sales_id(event_id, event_id_sh) -> Tuple[int, Optional[str]]` in `seatdata/_sales.py`; `SeatDataClient.get_event_sales(...) -> SalesPage`; `SeatDataClient.iter_event_sales(...) -> PageIterator[SalesRow]`. Task 6 mirrors both signatures exactly.

**This is the D-01 task.** Cursors are bound to the `source` they were issued under. A
continuation that drops `source` defaults to `sh` server-side and returns 400 `invalid_cursor`.
The iterator's closure must pin every non-cursor parameter.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sales.py`:

```python
import httpx
import pytest
import respx

from seatdata import SeatDataClient
from seatdata.exceptions import CursorExpiredError

API_KEY = "a" * 64
BASE = "https://seatdata.io"


def _page(data, has_more=False, next_cursor=None, first=True):
    body = {
        "event_id": 225220,
        "data": data,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }
    if first:
        body["total_count"] = 2
        body["sources"] = [
            {
                "source": "sh",
                "collecting_since": "2024-03-01",
                "tracked_for_event": True,
                "status": "ok",
            },
            {
                "source": "vs",
                "collecting_since": None,
                "tracked_for_event": False,
                "status": "ok",
            },
        ]
    return body


SH_ROW = {
    "source": "sh",
    "listing_id": 1,
    "all_in_price": None,
    "timestamp": 1757000000,
    "quantity": 2,
    "price": 145.0,
    "zone": "Lower Bowl",
    "section": "112",
    "row": "F",
}


@respx.mock
def test_get_event_sales_uses_internal_id_without_id_type():
    route = respx.get(f"{BASE}/api/v1/events/225220/sales").mock(
        return_value=httpx.Response(200, json=_page([SH_ROW]))
    )
    with SeatDataClient(api_key=API_KEY) as client:
        page = client.get_event_sales(event_id=225220)
    assert page["total_count"] == 2
    assert "id_type" not in route.calls[0].request.url.params


@respx.mock
def test_get_event_sales_maps_event_id_sh_to_marketplace():
    route = respx.get(f"{BASE}/api/v1/events/105294241/sales").mock(
        return_value=httpx.Response(200, json=_page([SH_ROW]))
    )
    with SeatDataClient(api_key=API_KEY) as client:
        client.get_event_sales(event_id_sh=105294241)
    assert route.calls[0].request.url.params["id_type"] == "marketplace"


@respx.mock
def test_source_is_omitted_when_not_supplied():
    route = respx.get(f"{BASE}/api/v1/events/225220/sales").mock(
        return_value=httpx.Response(200, json=_page([SH_ROW]))
    )
    with SeatDataClient(api_key=API_KEY) as client:
        client.get_event_sales(event_id=225220)
    assert "source" not in route.calls[0].request.url.params


@respx.mock
def test_iter_event_sales_resends_source_and_limit_on_every_page():
    pages = [
        _page([SH_ROW], has_more=True, next_cursor="c1"),
        _page([SH_ROW], has_more=False, next_cursor=None, first=False),
    ]
    route = respx.get(f"{BASE}/api/v1/events/225220/sales").mock(
        side_effect=[httpx.Response(200, json=p) for p in pages]
    )
    with SeatDataClient(api_key=API_KEY) as client:
        it = client.iter_event_sales(event_id=225220, source="all", limit=50)
        rows = list(it)
    assert len(rows) == 2
    assert len(route.calls) == 2
    for call in route.calls:
        assert call.request.url.params["source"] == "all"
        assert call.request.url.params["limit"] == "50"
    assert route.calls[1].request.url.params["starting_after"] == "c1"
    assert it.first_page["total_count"] == 2
    assert it.first_page["sources"][0]["source"] == "sh"


@respx.mock
def test_cursor_rejected_under_a_different_source_raises_cursor_expired():
    respx.get(f"{BASE}/api/v1/events/225220/sales").mock(
        return_value=httpx.Response(
            400,
            json={
                "error": {
                    "type": "invalid_request",
                    "code": "invalid_cursor",
                    "message": "Cursor was issued under a different source.",
                    "param": "starting_after",
                }
            },
        )
    )
    with SeatDataClient(api_key=API_KEY) as client:
        with pytest.raises(CursorExpiredError):
            client.get_event_sales(event_id=225220, starting_after="c1", source="vs")


def test_missing_and_conflicting_ids_raise_before_any_request():
    with SeatDataClient(api_key=API_KEY) as client:
        with pytest.raises(ValueError):
            client.get_event_sales()
        with pytest.raises(ValueError):
            client.get_event_sales(event_id=1, event_id_sh=2)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_sales.py -q`
Expected: FAIL with `AttributeError: 'SeatDataClient' object has no attribute 'get_event_sales'`.

- [ ] **Step 3: Create `seatdata/_sales.py`**

```python
from typing import Optional, Tuple, Union


def _coerce_event_id(name: str, value: Union[int, str]) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Invalid event id in {name}: {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid event id in {name}: {value!r}") from None
    raise ValueError(f"Invalid event id in {name}: {value!r}")


def resolve_sales_id(
    event_id: Optional[Union[int, str]],
    event_id_sh: Optional[Union[int, str]],
) -> Tuple[int, Optional[str]]:
    if event_id is None and event_id_sh is None:
        raise ValueError("Either event_id or event_id_sh must be provided")
    if event_id is not None and event_id_sh is not None:
        raise ValueError("Provide only one of event_id or event_id_sh")
    if event_id is not None:
        return _coerce_event_id("event_id", event_id), None
    return _coerce_event_id("event_id_sh", event_id_sh), "marketplace"
```

- [ ] **Step 4: Widen the imports in `seatdata/client.py`**

Replace this exact block:

```python
from ._batch import normalize_batch_response, prepare_batch_payload
from ._transport import _Transport
```

with:

```python
from ._batch import normalize_batch_response, prepare_batch_payload
from ._sales import resolve_sales_id
from ._transport import _Transport
```

Then replace this exact block in `seatdata/client.py`:

```python
from typing import Any, Dict, List, Optional, cast
```

with:

```python
from typing import Any, Dict, List, Optional, Sequence, Union, cast
```

`Sequence` is unused until Task 7; add it now so neither task has to touch this line twice.

Then add `SalesPage`, `SalesRow` to the `from .types import (...)` block, keeping it
alphabetically ordered alongside the existing names. `PageIterator` is already imported.

- [ ] **Step 5: Add both methods**

Insert immediately after `get_sales_data()` in `seatdata/client.py`, before `get_listings()`:

```python
    def _event_sales_params(
        self,
        *,
        limit: Optional[int] = None,
        starting_after: Optional[str] = None,
        source: Optional[str] = None,
        id_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if starting_after is not None:
            params["starting_after"] = starting_after
        if source is not None:
            params["source"] = source
        if id_type is not None:
            params["id_type"] = id_type
        return params

    def get_event_sales(
        self,
        event_id: Optional[Union[int, str]] = None,
        event_id_sh: Optional[Union[int, str]] = None,
        limit: Optional[int] = None,
        starting_after: Optional[str] = None,
        source: Optional[str] = None,
    ) -> SalesPage:
        """Fetch one page of sales for an event.

        The first page is billed one pull when it returns at least one row.
        Continuation pages are free, and an empty page is free. A retried
        first-page timeout may re-bill that pull, because the API has no
        idempotency key. Construct the client with max_retries=0 to opt out.

        total_count and sources appear on the first page only.
        """
        path_id, id_type = resolve_sales_id(event_id, event_id_sh)
        params = self._event_sales_params(
            limit=limit,
            starting_after=starting_after,
            source=source,
            id_type=id_type,
        )
        return cast(
            SalesPage,
            self._transport.request_json(
                "GET", f"/api/v1/events/{path_id}/sales", params=params
            ),
        )

    def iter_event_sales(
        self,
        event_id: Optional[Union[int, str]] = None,
        event_id_sh: Optional[Union[int, str]] = None,
        limit: Optional[int] = None,
        source: Optional[str] = None,
    ) -> PageIterator[SalesRow]:
        """Walk every page of sales for an event.

        source, limit, and the id pair are fixed for the life of the iterator.
        Cursors are bound to the source they were issued under, so changing
        source mid-walk is not supported. Read total_count and sources from
        the iterator's first_page attribute after the first item.
        """
        resolve_sales_id(event_id, event_id_sh)

        def fetch(cursor: Optional[str]) -> Dict[str, Any]:
            return cast(
                Dict[str, Any],
                self.get_event_sales(
                    event_id=event_id,
                    event_id_sh=event_id_sh,
                    limit=limit,
                    starting_after=cursor,
                    source=source,
                ),
            )

        return PageIterator(fetch)
```

- [ ] **Step 6: Run the tests**

Run:
```bash
pytest tests/test_sales.py -q
pytest -m "not integration" -q
mypy seatdata/
black seatdata/ tests/
```
Expected: PASS, mypy clean.

- [ ] **Step 7: Commit**

```bash
git add seatdata/_sales.py seatdata/client.py tests/test_sales.py
git commit -m "feat: add get_event_sales() and iter_event_sales() to SeatDataClient"
```

---

### Task 6: Async `get_event_sales()` and `iter_event_sales()`

**Files:**
- Modify: `seatdata/async_client.py`
- Test: `tests/test_async_sales.py`

**Interfaces:**
- Consumes: `resolve_sales_id` from Task 5; `SalesPage`, `SalesRow` from Task 3.
- Produces: `AsyncSeatDataClient.get_event_sales(...)` and `.iter_event_sales(...)` with signatures identical to Task 5's.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_async_sales.py` as an async mirror of `tests/test_sales.py`. Copy every test
from Task 5, converting each to `async def`, adding `@pytest.mark.asyncio`, replacing
`with SeatDataClient(...)` with `async with AsyncSeatDataClient(...)`, awaiting each
`get_event_sales` call, and collecting the iterator with
`[row async for row in client.iter_event_sales(...)]`. Keep the `_page` helper and `SH_ROW`
fixture verbatim.

The async iterator test must still assert all four things: two calls made, `source` present on
both, `starting_after` on the second, and `it.first_page["total_count"] == 2`.

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_async_sales.py -q`
Expected: FAIL with `AttributeError: 'AsyncSeatDataClient' object has no attribute 'get_event_sales'`.

- [ ] **Step 3: Widen the imports in `seatdata/async_client.py`**

Replace this exact block:

```python
from ._batch import normalize_batch_response, prepare_batch_payload
from ._transport import _Transport
```

with:

```python
from ._batch import normalize_batch_response, prepare_batch_payload
from ._sales import resolve_sales_id
from ._transport import _Transport
```

Then replace this exact block in `seatdata/async_client.py`:

```python
from typing import Any, Dict, List, Optional, cast
```

with:

```python
from typing import Any, Dict, List, Optional, Sequence, Union, cast
```

`Sequence` is unused until Task 8; add it now so neither task has to touch this line twice.

Then add `SalesPage`, `SalesRow` to the `from .types import (...)` block. `AsyncPageIterator`
is already imported.

- [ ] **Step 4: Add both methods**

Insert immediately after `get_sales_data()` in `seatdata/async_client.py`, before
`get_listings()`:

```python
    def _event_sales_params(
        self,
        *,
        limit: Optional[int] = None,
        starting_after: Optional[str] = None,
        source: Optional[str] = None,
        id_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if starting_after is not None:
            params["starting_after"] = starting_after
        if source is not None:
            params["source"] = source
        if id_type is not None:
            params["id_type"] = id_type
        return params

    async def get_event_sales(
        self,
        event_id: Optional[Union[int, str]] = None,
        event_id_sh: Optional[Union[int, str]] = None,
        limit: Optional[int] = None,
        starting_after: Optional[str] = None,
        source: Optional[str] = None,
    ) -> SalesPage:
        """Fetch one page of sales for an event.

        The first page is billed one pull when it returns at least one row.
        Continuation pages are free, and an empty page is free. A retried
        first-page timeout may re-bill that pull, because the API has no
        idempotency key. Construct the client with max_retries=0 to opt out.

        total_count and sources appear on the first page only.
        """
        path_id, id_type = resolve_sales_id(event_id, event_id_sh)
        params = self._event_sales_params(
            limit=limit,
            starting_after=starting_after,
            source=source,
            id_type=id_type,
        )
        return cast(
            SalesPage,
            await self._transport.arequest_json(
                "GET", f"/api/v1/events/{path_id}/sales", params=params
            ),
        )

    def iter_event_sales(
        self,
        event_id: Optional[Union[int, str]] = None,
        event_id_sh: Optional[Union[int, str]] = None,
        limit: Optional[int] = None,
        source: Optional[str] = None,
    ) -> AsyncPageIterator[SalesRow]:
        """Walk every page of sales for an event.

        source, limit, and the id pair are fixed for the life of the iterator.
        Cursors are bound to the source they were issued under, so changing
        source mid-walk is not supported. Read total_count and sources from
        the iterator's first_page attribute after the first item.
        """
        resolve_sales_id(event_id, event_id_sh)

        async def fetch(cursor: Optional[str]) -> Dict[str, Any]:
            return cast(
                Dict[str, Any],
                await self.get_event_sales(
                    event_id=event_id,
                    event_id_sh=event_id_sh,
                    limit=limit,
                    starting_after=cursor,
                    source=source,
                ),
            )

        return AsyncPageIterator(fetch)
```

- [ ] **Step 5: Run the tests**

Run:
```bash
pytest tests/test_async_sales.py -q
pytest -m "not integration" -q
mypy seatdata/
black seatdata/ tests/
```
Expected: PASS, mypy clean.

- [ ] **Step 6: Commit**

```bash
git add seatdata/async_client.py tests/test_async_sales.py
git commit -m "feat: add get_event_sales() and iter_event_sales() to AsyncSeatDataClient"
```

---

### Task 7: Sync `get_event_sales_batch()`

**Files:**
- Modify: `seatdata/client.py`
- Test: `tests/test_sales_batch.py`

**Interfaces:**
- Consumes: `prepare_batch_payload`, `normalize_batch_response` from Task 2; `BatchSalesResult` from Task 3.
- Produces: `SeatDataClient.get_event_sales_batch(event_ids_sh=None, event_ids=None, source=None) -> BatchSalesResult`. Task 8 mirrors it.

**This is the D-04 and D-05 task.** The call is billed per event and has no idempotency key, so
it must not auto-retry. A 402 arrives in two different shapes and only one is an exception.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sales_batch.py`:

```python
import httpx
import pytest
import respx

from seatdata import SeatDataClient, SeatDataPaymentError, SeatDataRateLimitError

API_KEY = "a" * 64
BASE = "https://seatdata.io"
PATH = f"{BASE}/api/v1/events/sales/batch"

SH_ROW = {
    "source": "sh",
    "listing_id": 1,
    "all_in_price": None,
    "timestamp": 1757000000,
    "quantity": 2,
    "price": 145.0,
    "zone": "Lower Bowl",
    "section": "112",
    "row": "F",
}


@respx.mock
def test_batch_posts_payload_and_returns_three_keys():
    route = respx.post(PATH).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": {"105294241": [SH_ROW]},
                "errors": {"225220": "not_found"},
                "sources": {"105294241": []},
            },
        )
    )
    with SeatDataClient(api_key=API_KEY) as client:
        result = client.get_event_sales_batch(event_ids_sh=[105294241], event_ids=[225220])
    assert set(result) == {"results", "errors", "sources"}
    assert result["errors"]["225220"] == "not_found"
    import json as _json

    body = _json.loads(route.calls[0].request.content)
    assert body == {"event_ids_sh": [105294241], "event_ids": [225220]}


@respx.mock
def test_digit_string_ids_look_up_by_decimal_string():
    respx.post(PATH).mock(
        return_value=httpx.Response(
            200, json={"results": {"105294241": [SH_ROW]}, "errors": {}, "sources": {}}
        )
    )
    with SeatDataClient(api_key=API_KEY) as client:
        result = client.get_event_sales_batch(event_ids_sh=["105294241"])
    assert result["results"]["105294241"] == [SH_ROW]


@respx.mock
def test_same_numeric_id_in_both_lists_is_sent_twice():
    route = respx.post(PATH).mock(
        return_value=httpx.Response(200, json={"results": {}, "errors": {}, "sources": {}})
    )
    with SeatDataClient(api_key=API_KEY) as client:
        client.get_event_sales_batch(event_ids_sh=[7], event_ids=[7])
    import json as _json

    body = _json.loads(route.calls[0].request.content)
    assert body == {"event_ids_sh": [7], "event_ids": [7]}


@respx.mock
def test_source_goes_on_the_query_string_not_the_body():
    route = respx.post(PATH).mock(
        return_value=httpx.Response(200, json={"results": {}, "errors": {}, "sources": {}})
    )
    with SeatDataClient(api_key=API_KEY) as client:
        client.get_event_sales_batch(event_ids_sh=[1], source="all")
    import json as _json

    assert route.calls[0].request.url.params["source"] == "all"
    assert "source" not in _json.loads(route.calls[0].request.content)


@respx.mock
def test_per_event_payment_required_is_data_not_an_exception():
    respx.post(PATH).mock(
        return_value=httpx.Response(
            200, json={"results": {}, "errors": {"7": "payment_required"}, "sources": {}}
        )
    )
    with SeatDataClient(api_key=API_KEY) as client:
        result = client.get_event_sales_batch(event_ids_sh=[7])
    assert result["errors"]["7"] == "payment_required"


@respx.mock
def test_raw_402_raises_payment_error():
    respx.post(PATH).mock(return_value=httpx.Response(402, json={"error": {"type": "payment_required", "code": "balance_exhausted", "message": "no funds"}}))
    with SeatDataClient(api_key=API_KEY) as client:
        with pytest.raises(SeatDataPaymentError):
            client.get_event_sales_batch(event_ids_sh=[7])


@respx.mock
def test_batch_is_not_retried_on_429():
    route = respx.post(PATH).mock(
        return_value=httpx.Response(
            429,
            json={
                "error": {
                    "type": "rate_limit_error",
                    "code": "rate_limited",
                    "message": "slow down",
                }
            },
        )
    )
    with SeatDataClient(api_key=API_KEY, max_retries=3) as client:
        with pytest.raises(SeatDataRateLimitError):
            client.get_event_sales_batch(event_ids_sh=[7])
    assert len(route.calls) == 1


def test_cap_and_empty_payload_raise_before_any_request():
    with SeatDataClient(api_key=API_KEY) as client:
        with pytest.raises(ValueError):
            client.get_event_sales_batch()
        with pytest.raises(ValueError):
            client.get_event_sales_batch(event_ids_sh=list(range(101)))
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_sales_batch.py -q`
Expected: FAIL with `AttributeError: 'SeatDataClient' object has no attribute 'get_event_sales_batch'`.

- [ ] **Step 3: Add the method**

Insert immediately after `iter_event_sales()` in `seatdata/client.py`:

```python
    def get_event_sales_batch(
        self,
        event_ids_sh: Optional[Sequence[Union[int, str]]] = None,
        event_ids: Optional[Sequence[Union[int, str]]] = None,
        source: Optional[str] = None,
    ) -> BatchSalesResult:
        """Fetch sales for up to 100 events in one request.

        This call is billed one pull per event that returns rows, and the API
        has no idempotency key, so it is never retried automatically. A caller
        who accepts the re-bill risk can retry in their own code.

        A deny-all billing failure raises SeatDataPaymentError. A per-event
        payment failure is data, and arrives as "payment_required" in errors.

        results, errors, and sources are all keyed by the decimal string of
        each id sent.
        """
        payload = prepare_batch_payload(event_ids_sh, event_ids)
        params: Dict[str, Any] = {}
        if source is not None:
            params["source"] = source
        response = self._transport.request_json(
            "POST",
            "/api/v1/events/sales/batch",
            params=params,
            json=payload,
            retry_safe=False,
        )
        return normalize_batch_response(response)
```

Task 5 already added `Sequence` and `Union` to the typing import. Add `BatchSalesResult` to
the `from .types import (...)` block if it is not there yet.

- [ ] **Step 4: Run the tests**

Run:
```bash
pytest tests/test_sales_batch.py -q
pytest -m "not integration" -q
mypy seatdata/
black seatdata/ tests/
```
Expected: PASS. The 429 test must show exactly one call — that assertion is the whole point of
`retry_safe=False`.

- [ ] **Step 5: Commit**

```bash
git add seatdata/client.py tests/test_sales_batch.py
git commit -m "feat: add get_event_sales_batch() to SeatDataClient"
```

---

### Task 8: Async `get_event_sales_batch()`

**Files:**
- Modify: `seatdata/async_client.py`
- Test: `tests/test_async_sales_batch.py`

**Interfaces:**
- Produces: `AsyncSeatDataClient.get_event_sales_batch(...)` with a signature identical to Task 7's.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_async_sales_batch.py` as an async mirror of `tests/test_sales_batch.py`.
Convert every test to `async def` with `@pytest.mark.asyncio`, use
`async with AsyncSeatDataClient(...)`, and await each call. Keep the `SH_ROW` fixture verbatim.
The no-retry test must still assert `len(route.calls) == 1`.

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_async_sales_batch.py -q`
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Add the method**

Insert immediately after `iter_event_sales()` in `seatdata/async_client.py`:

```python
    async def get_event_sales_batch(
        self,
        event_ids_sh: Optional[Sequence[Union[int, str]]] = None,
        event_ids: Optional[Sequence[Union[int, str]]] = None,
        source: Optional[str] = None,
    ) -> BatchSalesResult:
        """Fetch sales for up to 100 events in one request.

        This call is billed one pull per event that returns rows, and the API
        has no idempotency key, so it is never retried automatically. A caller
        who accepts the re-bill risk can retry in their own code.

        A deny-all billing failure raises SeatDataPaymentError. A per-event
        payment failure is data, and arrives as "payment_required" in errors.

        results, errors, and sources are all keyed by the decimal string of
        each id sent.
        """
        payload = prepare_batch_payload(event_ids_sh, event_ids)
        params: Dict[str, Any] = {}
        if source is not None:
            params["source"] = source
        response = await self._transport.arequest_json(
            "POST",
            "/api/v1/events/sales/batch",
            params=params,
            json=payload,
            retry_safe=False,
        )
        return normalize_batch_response(response)
```

- [ ] **Step 4: Run the tests**

Run:
```bash
pytest tests/test_async_sales_batch.py -q
pytest -m "not integration" -q
mypy seatdata/
black seatdata/ tests/
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add seatdata/async_client.py tests/test_async_sales_batch.py
git commit -m "feat: add get_event_sales_batch() to AsyncSeatDataClient"
```

---

### Task 9: Deprecate `get_sales_data()`

**Files:**
- Modify: `seatdata/client.py`, `seatdata/async_client.py`
- Test: `tests/test_client.py`, `tests/test_async_client.py`

`get_sales_data()` stays on `/api/v0.3/salesdata/get` and keeps returning a flat list. Only the
warning is added. Removal is a 2.0 item.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_client.py`:

```python
@respx.mock
def test_get_sales_data_warns_and_names_the_replacement():
    respx.get("https://seatdata.io/api/v0.3/salesdata/get").mock(
        return_value=httpx.Response(200, json=[])
    )
    with SeatDataClient(api_key="a" * 64) as client:
        with pytest.warns(DeprecationWarning, match="get_event_sales"):
            client.get_sales_data(event_id="225220")
```

Append the async equivalent to `tests/test_async_client.py`, using `@pytest.mark.asyncio`,
`async with AsyncSeatDataClient(...)`, and `await client.get_sales_data(event_id="225220")`
inside the same `pytest.warns` block.

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_client.py -k deprecat -q`
Expected: FAIL with `DID NOT WARN`.

- [ ] **Step 3: Add the warning in `seatdata/client.py`**

Replace this exact block:

```python
    def get_sales_data(
        self, event_id: Optional[str] = None, event_id_sh: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not event_id and not event_id_sh:
            raise ValueError("Either event_id or event_id_sh must be provided")
```

with:

```python
    def get_sales_data(
        self, event_id: Optional[str] = None, event_id_sh: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        warnings.warn(
            "get_sales_data() calls the v0.3 endpoint and returns sh rows only. "
            "Use get_event_sales() for v1 sales, the source filter, and pagination. "
            "This method will be removed in v2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not event_id and not event_id_sh:
            raise ValueError("Either event_id or event_id_sh must be provided")
```

- [ ] **Step 4: Add the same warning in `seatdata/async_client.py`**

Replace this exact block:

```python
    async def get_sales_data(
        self, event_id: Optional[str] = None, event_id_sh: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not event_id and not event_id_sh:
            raise ValueError("Either event_id or event_id_sh must be provided")
```

with:

```python
    async def get_sales_data(
        self, event_id: Optional[str] = None, event_id_sh: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        warnings.warn(
            "get_sales_data() calls the v0.3 endpoint and returns sh rows only. "
            "Use get_event_sales() for v1 sales, the source filter, and pagination. "
            "This method will be removed in v2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not event_id and not event_id_sh:
            raise ValueError("Either event_id or event_id_sh must be provided")
```

Both files already import `warnings` at the top. Confirm before adding an import.

- [ ] **Step 5: Run the full suite**

Run: `pytest -m "not integration" -q`
Expected: PASS. If any existing test calls `get_sales_data()` and now fails on an unexpected
warning, wrap that call in `pytest.warns(DeprecationWarning)` rather than silencing the warning
globally.

- [ ] **Step 6: Commit**

```bash
git add seatdata/client.py seatdata/async_client.py tests/test_client.py tests/test_async_client.py
git commit -m "feat: deprecate get_sales_data() in favor of get_event_sales()"
```

---

### Task 10: Version bump and documentation

**Files:**
- Modify: `pyproject.toml`, `seatdata/__init__.py`, `CHANGELOG.md`, `README.md`, `CLAUDE.md`

- [ ] **Step 1: Bump the version**

In `pyproject.toml`, change `version = "1.0.0"` to `version = "1.1.0"`.
In `seatdata/__init__.py`, change `__version__ = "1.0.0"` to `__version__ = "1.1.0"`.

- [ ] **Step 2: Export the new names**

Add `SeatDataPaymentError` to both the `from .exceptions import (...)` block and `__all__` in
`seatdata/__init__.py`, if Task 1's cherry-pick did not already. Verify with:

```bash
python -c "import seatdata; print(seatdata.__version__, seatdata.SeatDataPaymentError)"
```

- [ ] **Step 3: Add the CHANGELOG entry**

Insert directly above the `## [1.0.0] - 2026-04-30` heading in `CHANGELOG.md`:

```markdown
## [1.1.0] - UNRELEASED

### Added
- `get_event_sales()` and `iter_event_sales()` on both clients - one page or a full cursor walk of `GET /api/v1/events/{event_id}/sales`. Accepts `event_id` or `event_id_sh`, plus `limit`, `starting_after`, and `source`.
- `get_event_sales_batch()` on both clients - sales for up to 100 events in one `POST /api/v1/events/sales/batch` request.
- An optional `source` filter (`sh`, `vs`, `all`) on all three methods. Omitting it reproduces the previous sh-only behavior and charges.
- `first_page` on `PageIterator` and `AsyncPageIterator`, so the server's first-page-only `total_count` and `sources` survive iteration.
- New types: `SalesPage`, `SalesRow` (a discriminated union of `SHSalesRow` and `VSSalesRow`), `SourceBlock`, and a `sources` key on `BatchSalesResult`.
- `SeatDataPaymentError` for HTTP `402 Payment Required`, exported from the top-level package.

### Fixed
- `402` responses now raise `SeatDataPaymentError` SDK-wide. They previously surfaced as `SeatDataServerError` or the base `SeatDataError` depending on the response body. This also covers `get_sales_data()` and `get_listings()`.

### Deprecated
- `get_sales_data()` now emits a `DeprecationWarning` naming `get_event_sales()`. It stays on the v0.3 endpoint and will be removed in v2.0.
- Removal of `search_events_legacy()`, `event_request_add()`, and `event_request_status()` is deferred from v1.1 to v2.0.
```

Set the real date at tag time. Leave it `UNRELEASED` until then.

- [ ] **Step 4: Add the README section**

Add a "v1 sales" section to `README.md` with three runnable snippets: a single page, a full
cursor walk reading `first_page`, and a batch call. Make the async snippet a complete
`asyncio.run(main())` script, not a bare `await` fragment. Add the migration table from the
spec's "Migration table" section verbatim.

- [ ] **Step 5: Update `CLAUDE.md` on disk**

Move `GET /api/v1/events/{event_id}/sales` and `POST /api/v1/events/sales/batch` from the
"Endpoints the SDK does NOT call" list into the numbered "Endpoints the SDK calls today" list,
naming the new methods. Update the Response Handling and Pagination sections for
`get_event_sales`, `iter_event_sales`, and `first_page`. Add `SeatDataPaymentError` to the error
table and delete the "There is no 402 handling today" paragraph.

**Do not `git add CLAUDE.md`.** It is untracked deliberately.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml seatdata/__init__.py CHANGELOG.md README.md
git commit -m "docs: add 1.1.0 changelog, README v1 sales section, and version bump"
```

---

### Task 11: Example script and final gate

**Files:**
- Create: `examples/v1_sales.py`

- [ ] **Step 1: Write the example**

```python
import os

from seatdata import SeatDataClient, SeatDataPaymentError


def main():
    api_key = os.environ.get("SEATDATA_API_KEY")
    if not api_key:
        print("Please set SEATDATA_API_KEY environment variable")
        return

    base_url = os.environ.get("SEATDATA_BASE_URL", "https://seatdata.io").rstrip("/")

    with SeatDataClient(api_key=api_key, base_url=base_url) as client:
        print("=== First page ===")
        page = client.get_event_sales(event_id_sh=105294241, limit=5, source="all")
        print(f"total_count: {page.get('total_count')}")
        for block in page.get("sources", []):
            print(
                f"  {block['source']}: tracked={block['tracked_for_event']} status={block['status']}"
            )
        for sale in page["data"]:
            print(f"  {sale['source']} {sale['section']} row {sale['row']} ${sale['price']}")

        print("=== Full walk ===")
        rows = client.iter_event_sales(event_id_sh=105294241, source="all")
        count = 0
        for _ in rows:
            count += 1
            if count >= 25:
                break
        print(f"walked {count} rows; total_count was {rows.first_page.get('total_count')}")

        print("=== Batch ===")
        try:
            batch = client.get_event_sales_batch(event_ids_sh=[105294241, 105288127])
        except SeatDataPaymentError as e:
            print(f"Payment required - no event could be served: {e.message}")
            return
        for event_id, sales in batch["results"].items():
            print(f"  event {event_id}: {len(sales)} sales")
        for event_id, reason in batch["errors"].items():
            print(f"  event {event_id}: {reason}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Byte-compile it**

Run: `python -m py_compile examples/v1_sales.py`
Expected: no output. Do not run it against the live API — neither endpoint is deployed.

- [ ] **Step 3: Final gate**

Run:
```bash
pytest -m "not integration" -q
mypy seatdata/
black --check seatdata/ tests/ examples/
git status --short
```
Expected: all green. `git status` shows only `CLAUDE.md` and the two pre-existing stray
`examples/*.py` files as untracked.

- [ ] **Step 4: Commit**

```bash
git add examples/v1_sales.py
git commit -m "docs: add v1 sales example script"
```

---

## Spec coverage

| Spec item | Task |
|---|---|
| D-01 iterators pin and resend every non-cursor parameter | 5, 6 |
| D-02 `SalesRow` discriminated union | 3 |
| D-03 `PageIterator` captures the first page | 4 |
| D-04 the batch POST does not auto-retry | 7, 8 |
| D-05 402 has two shapes, one is an exception | 7, 8 |
| D-06 `invalid_cursor` stays mapped to `CursorExpiredError` | 5 (test), already wired in `_transport.py` |
| D-07 batch result lookup is by decimal string | 7 (tests) |
| D-08 `source` is omitted when not supplied | 5, 7 (tests) |
| D-09 `sources[].status` is surfaced, not raised | 3 (type), 11 (example) |
| Stage 1 402 and semver | 1 |
| Stage 2 items 1 through 8 | 2 through 11 |
| Migration table | 10 |
| Test plan | 3 through 9 |

## Risks and notes

- **Neither endpoint is deployed.** Every test here is a `respx` unit test. No integration test can pass until the server branch ships. Do not add one.
- **Task 4 touches a shared class.** Run the full suite, not just the new tests, before committing it. The search and stats iterators must be unaffected.
- **Task 7's no-retry assertion is load-bearing.** If `len(route.calls) == 1` ever becomes `> 1`, the SDK is re-billing customers on transient failures. Treat a change there as a release blocker.
- **The `listing_id` type split is settled, not open.** It stays int on `sh` and str on `vs`. See "Settled decision" above before anyone proposes unifying it again.
- **`CLAUDE.md` stays untracked.** Task 10 edits it on disk and must not stage it.
