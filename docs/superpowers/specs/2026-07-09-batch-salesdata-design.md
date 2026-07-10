# Batch Sales Data — Design

- **Date:** 2026-07-09
- **Status:** Approved (pending implementation)
- **Target release:** 1.1.0
- **Endpoint:** `POST /api/v0.3/salesdata/batch`

## Context

The SeatData API added a batch sales-data endpoint that fetches sales for up to
100 events in one request, as a sibling to the existing single-event
`GET /api/v0.3/salesdata/get`. Billing is identical (one pull per event that
returns sales; events with no sales are free), and it lives in a dedicated
`salesdata_batch` rate-limit bucket (500 requests / 60s, one count per call).

The SDK exposes the single-event endpoint as `get_sales_data()` on both the sync
`SeatDataClient` and async `AsyncSeatDataClient`. This design adds a parallel
`get_sales_data_batch()` to both, plus the supporting types, exception, and
transport wiring the endpoint requires.

## Goals

- Add `get_sales_data_batch()` to both clients with full sync/async parity.
- Return a shape consistent with the rest of the SDK (a `TypedDict`, not a new
  object type).
- Handle the endpoint's `402 Payment Required` correctly, SDK-wide.
- Validate input client-side the way the existing methods do, and fail fast on
  the endpoint's documented `400` conditions (no ids, > 100 ids) before spending
  a network round-trip or a rate-limit count.
- Ship additively as 1.1.0 without breaking any existing caller.

## Non-goals (out of scope)

- **Auto-chunking > 100 events.** One call maps to one API request and one
  rate-limit count. A caller with > 100 ids gets a `ValueError`. A convenience
  chunker can be added later without breaking this contract.
- **Typing individual sale rows (`SoldListing`).** The single-event
  `get_sales_data()` returns untyped `List[Dict[str, Any]]`; the batch method
  keeps rows untyped for row-for-row consistency. Introducing `SoldListing` for
  only one of the two endpoints would make them inconsistent with each other.
- **Fixing the stale `api-key` auth note in `CLAUDE.md`.** Pre-existing and
  unrelated to this work.

## Public API

Identical signature on `seatdata/client.py` (sync) and
`seatdata/async_client.py` (async, `async def`):

```python
def get_sales_data_batch(
    self,
    event_ids_sh: Optional[Sequence[Union[int, str]]] = None,
    event_ids: Optional[Sequence[Union[int, str]]] = None,
) -> BatchSalesResult:
    payload = prepare_batch_payload(event_ids_sh, event_ids)
    return cast(
        BatchSalesResult,
        self._transport.request_json(
            "POST", "/api/v0.3/salesdata/batch", json=payload
        ),
    )
```

- Method name `get_sales_data_batch` mirrors the operationId `getSalesDataBatch`
  and sits next to `get_sales_data`.
- `event_ids_sh` = StubHub Event IDs, `event_ids` = SeatData Event IDs — the exact
  field names from the endpoint's request body, and the plurals of the
  single-event method's `event_id_sh` / `event_id`.
- Both params accept `int` or `str` elements (callers may hold ids as either; the
  single-event method takes `str`, the endpoint wants `int`). The helper coerces
  to `int` on the wire.
- **Retries:** `retry_safe=True` (transport default), matching the identically
  billed `get_sales_data()` (the only `retry_safe=False` caller is the true write
  `create_event_request`). Retries occur only on transient failures
  (429/502/503/504 and connect/read-timeout/remote-protocol errors). Because a
  batch bills up to one pull per event, a retried read-timeout can re-bill the
  whole batch (worst case ~`(max_retries + 1) × N` pulls), and larger batch
  responses make a mid-body timeout likelier than on the single-event GET. The API
  exposes no idempotency key, so the SDK cannot eliminate this. The docstring and
  README **must** carry an explicit note that a retried timeout may re-bill the
  batch.

### Return value

```python
resp = client.get_sales_data_batch(
    event_ids_sh=[105294241, 105288127],
    event_ids=[225220],
)
# resp: BatchSalesResult
# {
#   "results": {
#       "105294241": [ {<sale row>}, ... ],
#       "225220":    [ {<sale row>}, ... ],
#   },
#   "errors": {
#       "105288127": "not_found",
#   },
# }

sales = resp["results"].get(str(225220), [])     # canonical str key
for event_id, reason in resp["errors"].items():  # errors always present (normalized)
    ...  # reason is "not_found" or "payment_required"
```

`results` and `errors` are keyed by the **canonical decimal string** of the ids:
JSON object keys are always strings, and the wire carries the coerced integers, so
a key is `str(int(id))` — e.g. a passed `" 225220"` or `"0225220"` comes back as
`"225220"`. Callers correlate with `str(int(event_id))` (or plain `str(event_id)`
when they already hold canonical ints). This str-key lookup is the one ergonomic
cost of returning a plain typed dict, documented in the README and docstring.

The method **normalizes** the response (see `normalize_batch_response` above) so
both keys are always present, guaranteeing the `BatchSalesResult` contract holds
even if the server omits an empty map — `resp["results"]` and `resp["errors"]`
never `KeyError`. A requested event that returns no sales (free, unbilled) may be
**absent** from `results` rather than present as an empty list, so callers should
use `resp["results"].get(str(int(id)), [])`. (Absent-vs-empty is not pinned by the
endpoint excerpt; confirm in integration testing.)

## New type — `seatdata/types.py`

```python
class BatchSalesResult(TypedDict):
    results: Dict[str, List[Dict[str, Any]]]
    errors: Dict[str, str]
```

- Requires adding `Any` to the `typing` import in `types.py`.
- Sale rows are untyped `Dict[str, Any]`, identical to `get_sales_data()`.
- `errors` values are `str`. Considered `Literal["not_found", "payment_required"]`
  but chose plain `str` to stay forgiving if the server adds a new per-event error
  string later (TypedDict is not runtime-enforced; a strict `Literal` would only
  mislead if the server diverges).
- Exposed only under `seatdata.types`, consistent with the other response
  TypedDicts (which are not top-level exports).

## New exception — `seatdata/exceptions.py`

```python
class SeatDataPaymentError(SeatDataError):
    pass
```

- Represents the top-level `402` ("no event in the batch could be served").
- Subclass of `SeatDataError`, so existing `except SeatDataError` handlers keep
  working.
- Top-level export from `seatdata/__init__.py` (import list + `__all__`).
- No legacy alias — it is brand new.

Note the two distinct "payment" surfaces, which must not be conflated:

| Surface | HTTP | Where it appears | SDK behavior |
|---|---|---|---|
| Per-event exhaustion | `200` | `errors: {"<id>": "payment_required"}` | Data, not an exception. Already handled by the `errors` map. |
| Whole-request failure | `402` | top-level response | Raises `SeatDataPaymentError`. |

## Transport wiring — `seatdata/_transport.py`

The transport is shared by both clients, so the 402 mapping applies SDK-wide.
This also fixes the single-event `get_sales_data()` / `get_listings()`, which can
return `402` under the same pay-as-you-go billing and today do not surface it as a
payment error.

The routing must be robust to two body shapes that reach `_raise_from_response`
by different paths:

- **Non-envelope bodies** (non-JSON, legacy string, or missing the `error` dict) —
  `_parse_error_body` synthesizes the envelope `type` from a status-keyed fallback
  map (currently `{401, 404, 429}`, else `server_error`).
- **Proper envelope bodies** — `_parse_error_body` returns them verbatim
  (`_transport.py:113`), so routing is driven solely by the server's own
  `error.type`. The exact `type` string the server sends on a 402 is not specified
  in the endpoint contract, so we must NOT assume it equals `"payment_required"`.
  A status-based backstop is required, not the fallback-map entry alone.

Changes:

1. Import `SeatDataPaymentError`.
2. Add to `_ERROR_TYPE_MAP`: `"payment_required": SeatDataPaymentError` (routes an
   explicit `payment_required` type, for any body shape).
3. Add `402: "payment_required"` to the fallback-type map in `_parse_error_body`
   (covers all non-envelope 402 bodies).
4. **Status-based backstop in `_raise_from_response`:** when `error.type` is not in
   `_ERROR_TYPE_MAP`, map `status_code == 402` to `SeatDataPaymentError` rather than
   defaulting to base `SeatDataError`. This guarantees every 402 raises
   `SeatDataPaymentError` regardless of the server's envelope `type`:

   ```python
   cls = _ERROR_TYPE_MAP.get(err_type)
   if cls is None:
       cls = SeatDataPaymentError if response.status_code == 402 else SeatDataError
   ```
5. Leave `402` out of `_RETRY_STATUS` — a billing failure must not be retried.

## Validation / payload helper — `seatdata/_batch.py` (new module)

Small pure functions shared by both clients — no HTTP, unit-testable in
isolation, and no import cycle (both clients already import sibling `_`-modules):

```python
def prepare_batch_payload(
    event_ids_sh: Optional[Sequence[Union[int, str]]],
    event_ids: Optional[Sequence[Union[int, str]]],
) -> Dict[str, List[int]]:
    ...
```

Rules:

- **Argument-type guard.** Each argument must be `None` or a non-`str`/non-`bytes`
  iterable. A bare `str`/`bytes` (satisfies `Sequence[Union[int, str]]`
  structurally but iterates into characters) or a non-iterable such as a bare
  `int` raises `ValueError` naming the argument — closing both the bare-string and
  bare-int footguns.
- **Per-element coercion to `int`, strict.** Accept only `int` (excluding `bool`)
  and `str` that parses as a base-10 integer. Reject `bool` (`int(True) == 1`
  silently), `float` (`int(105294241.9)` truncates to a *different* id), `None`,
  and nested containers. Note `int()` raises `TypeError` on `None`/containers and
  `ValueError` on bad strings; wrap both into a uniform `ValueError` naming the
  offending value, so the client-side contract is a single exception type.
- **Dedup within each list, order-preserving** via `dict.fromkeys`, after
  coercion. Not across lists — StubHub `225220` and SeatData `225220` are
  different events. Dedup precedes the count check because the endpoint's 100-cap
  applies "after deduplication"; counting raw length could falsely reject a valid
  batch. (Coerce-then-dedup also collapses a mixed `225220` / `"225220"` pair.)
- **Empty check.** If both lists are empty or `None` after processing, raise
  `ValueError` (mirrors the existing "Either … must be provided" guard on
  `get_sales_data()`).
- **Size check.** If the combined unique count > 100, raise `ValueError`.
- **Omit empties.** The returned dict includes a key only if its list is
  non-empty, so a one-sided call sends only the relevant field.

A companion one-liner in the same module normalizes the response so the
`BatchSalesResult` contract always holds:

```python
def normalize_batch_response(body: Any) -> BatchSalesResult:
    return {
        "results": (body or {}).get("results", {}),
        "errors": (body or {}).get("errors", {}),
    }
```

## Versioning & deprecation

- Bump to **1.1.0** in `pyproject.toml` and `seatdata/__init__.py`. Purely
  additive; nothing existing breaks.
- The `[1.0.0]` CHANGELOG entry and three `DeprecationWarning`s in `client.py`
  (`search_events_legacy`, `event_request_add`, `event_request_status`) say
  "removed in v1.1". Removing public API in a minor violates semver, so:
  - Update those three warnings in `client.py` to say **"removed in v2.0"**.
    (The async warnings do not name a version and need no change.)
  - Leave the historical `[1.0.0]` CHANGELOG entry intact; document the deferral
    in the new `[1.1.0]` entry rather than rewriting history.

## Files changed

| File | Change |
|---|---|
| `seatdata/_batch.py` | **New.** `prepare_batch_payload()` + `normalize_batch_response()`. |
| `seatdata/types.py` | Add `BatchSalesResult`; import `Any`. |
| `seatdata/exceptions.py` | Add `SeatDataPaymentError`. |
| `seatdata/_transport.py` | Map `402` / `payment_required` → `SeatDataPaymentError`. |
| `seatdata/client.py` | Add `get_sales_data_batch()`; deprecation notes → v2.0. |
| `seatdata/async_client.py` | Add `async get_sales_data_batch()`. |
| `seatdata/__init__.py` | Export `SeatDataPaymentError`; `__version__` → 1.1.0. |
| `pyproject.toml` | `version` → 1.1.0. |
| `CHANGELOG.md` | New `[1.1.0]` entry. |
| `README.md` | Batch usage snippet (sync + async). |
| `CLAUDE.md` | Add endpoint, error class, response-handling line. |
| `examples/batch_sales_data.py` | **New** example (distinct from `batch_event_requests.py`). |

## Implementation notes

- `client.py` and `async_client.py`: add `Sequence`, `Union` to the `typing`
  import and `BatchSalesResult` to the `.types` import; import
  `prepare_batch_payload` / `normalize_batch_response` from `._batch`. The async
  body must `await self._transport.arequest_json(...)` — the shared code sketch
  shows only the sync form.
- gzip and headers need no handling: httpx sends `Accept-Encoding: gzip, deflate`
  and auto-decompresses, and sets `Content-Type: application/json` for `json=`.
- `cast(BatchSalesResult, ...)` over `request_json`'s `Any` return type-checks
  cleanly; `Dict[str, List[int]]` satisfies the transport's
  `json: Optional[Dict[str, Any]]` parameter.

## Testing strategy

Test-driven; `respx` mocks httpx; must pass `mypy seatdata/` and `black` (line
length 100).

- **`tests/test_batch.py` (new)** — the pure helpers: order-preserving dedup,
  int/str coercion, mixed int+str duplicate collapses to one, bare-string/bytes
  guard → `ValueError`, bare-int (non-iterable) arg → `ValueError`, `None` element
  → `ValueError`, `bool` element → `ValueError`, `float` element → `ValueError`,
  non-numeric string → `ValueError`, both-empty → `ValueError`, > 100 unique →
  `ValueError`, cross-list separation preserved, one-sided call omits the empty
  field; `normalize_batch_response` fills missing `results`/`errors` with `{}`.
- **`tests/test_client.py` / `tests/test_async_client.py`** — success returns the
  normalized `{results, errors}` shape; a `200` whose `errors` map contains a
  per-event `payment_required` returns normally and does **not** raise (the
  two-surfaces invariant); a response missing `errors` is normalized to `{}`; the
  request body on the wire is deduped integers; `402` → `SeatDataPaymentError`;
  client-side `ValueError`s make no HTTP call (assert the respx route was not
  called).
- **`tests/test_transport.py`** — `402` → `SeatDataPaymentError` for a proper
  envelope whose `type` is an *unmapped* string (exercises the status backstop),
  for an explicit `payment_required` envelope, and for legacy-string and non-JSON
  bodies; confirm `402` is not retried; cover both `request_json` and
  `arequest_json` (separate retry loops).
- **`tests/test_exceptions.py`** — `SeatDataPaymentError` is a `SeatDataError`
  subclass and importable from the top-level package.

## Documentation & examples

- **README** — a batch snippet under Quick Start for both clients, showing the
  `str(int(event_id))` key lookup, iterating `errors`, catching
  `SeatDataPaymentError`, and the retry re-bill note.
- **CLAUDE.md** — add `POST /v0.3/salesdata/batch` to API Details (params, return,
  rate limit, billing), add `SeatDataPaymentError` to Error Handling, add a
  `get_sales_data_batch()` line to Response Handling.
- **CHANGELOG.md** — `[1.1.0]` dated on release: Added `get_sales_data_batch()`
  (sync + async), `SeatDataPaymentError`, `BatchSalesResult`; Fixed `402` handling
  to consistently raise `SeatDataPaymentError` (previously surfaced as
  `SeatDataServerError` or the base `SeatDataError` depending on response body);
  noted deprecation-removal deferral to v2.0.
- **examples/batch_sales_data.py** — build a mixed id list, call the batch method,
  read `results`, iterate `errors`, catch `SeatDataPaymentError`.

## Decisions log

1. **Return shape → typed dict (`BatchSalesResult`), not a rich object.** Every
   data-returning method in the SDK returns a plain dict/list; a result object
   would be the first data-container class and break the pattern.
2. **Payment → dedicated `SeatDataPaymentError`, wired SDK-wide.** A distinct,
   catchable billing exception; reusing `SeatDataSubscriptionError` would conflate
   402 balance exhaustion with 401 no-subscription. Fixes 402 handling everywhere,
   not just batch.
3. **> 100 events → raise `ValueError` (no auto-chunk).** One call = one request =
   one rate-limit count; predictable, matches the API's own 400.
4. **Version → 1.1.0, additive; defer deprecation removals to v2.0.** Keeps the
   release non-breaking and semver-correct.
