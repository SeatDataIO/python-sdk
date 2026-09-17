# v1 Sales Adoption — Design

- **Date:** 2026-09-16
- **Status:** Draft (revised after a six-reviewer panel)
- **Target release:** 1.1.0
- **Endpoints:** `GET /api/v1/events/{event_id}/sales`, `POST /api/v1/events/sales/batch`
- **Supersedes:** `2026-07-09-batch-salesdata-design.md`, which targeted `POST /api/v0.3/salesdata/batch`
- **Contract verified against:** `SoldListingsTrackerDjango-vividseats-api-endpoint` at `4b81fe87`, confirmed by the API team

> **Both v1 sales endpoints went live on 2026-09-17.** This spec was written while they were
> still unreleased, which is why several decisions below weigh whether the wire format was
> still free to change. It no longer is: `/sales` and `/sales/batch` are a shipped contract.

## Context

The SDK is already a v1 client for account, usage, event search, and event stats.
Sales is the one endpoint family still on v0.x. The server now exposes both a v1
single-event sales endpoint and a v1 batch endpoint, and a `source` filter that
returns sales observed on a second marketplace.

An abandoned branch, `feat/batch-salesdata`, implemented the v0.3 batch endpoint
across 11 commits. It is complete, reviewed, and merges clean. This design reuses
most of it and repoints the rest.

## Server contract

### `GET /api/v1/events/{event_id}/sales`

- Query parameters: `limit` (default 100, max 200), `starting_after`, `id_type`, `source`
- `id_type` omitted means `event_id` is the internal SeatData id. `id_type=marketplace` means it is the `sh` id.
- Response: `{event_id, data, has_more, next_cursor}`, plus `total_count` and `sources` on the first page only
- A rejected cursor returns 400 with `error.code` of `invalid_cursor` and `error.param` of `starting_after`

### `POST /api/v1/events/sales/batch`

- Body: `{"event_ids": [...], "event_ids_sh": [...]}`. The server reuses the v0.3 body parser unmodified.
- Validation: ints and ASCII digit-strings; bools and floats rejected; 100-event cap on the combined per-list-deduplicated count
- `source` goes on the query string, not in the body
- Response: `{results, errors, sources}`, each keyed by the client-sent id
- `errors` values: `not_found` or `payment_required`
- Rate limit: 500/m, bucket `paid:salesdata_batch`
- A deny-all billing failure returns a raw HTTP 402
- No `limit` parameter and no pagination

### `source` filter

- Exactly three values: `sh` (the default), `vs`, `all`. Any other value returns 400 with `error.code` of `invalid_param` and `error.param` of `source`, free of charge.
- Longer marketplace-name values are **not** deprecated aliases. They never shipped. Do not accept or translate them.
- An omitted `source` returns `sh` only and charges what a pre-Phase-4 caller paid.
- Cursors are bound to the `source` they were issued under. Replaying under a different `source` returns `invalid_cursor`.

### Row shapes

| Field | `sh` rows | `vs` rows |
|---|---|---|
| `source` | `"sh"` | `"vs"` |
| `listing_id` | int | str |
| `all_in_price` | always null | number or null |
| `zone` | populated | always `""` |
| `section` | section only | may combine zone and section |
| `norm_zone`, `norm_section` | absent | present, all-or-nothing |

On a `vs` row the normalized pair is all-or-nothing: either both are meaningful or both are `""`.
Neither ever carries a cleaned copy of the marketplace's own text.

Neither endpoint returns an `enriched` field. Vivid Seats rows whose seat details could not be
determined are excluded from `data` and from `total_count`.

### `sources` metadata

Two entries, `sh` then `vs`, whatever `source` was sent. Each has `source`,
`collecting_since`, `tracked_for_event`, and `status` (`ok` or `unavailable`).
The single endpoint returns an array. The batch endpoint returns a map of
client-sent id to that array. The live endpoint returns something different again; see the
non-goal below.

### Billing

One pull per first page that returns at least one row, whichever source produced it.
Continuation pages are free. An empty page is free. Batch charges one pull per event
that returns rows.

## Goals

- Add v1 sales to both clients, single and batch, with full sync and async parity.
- Ship additively as 1.1.0. Break no existing caller.
- Handle 402 correctly, SDK-wide.
- Type the heterogeneous row shapes honestly.

## Non-goals

- **`GET /api/v1/listings/live/get`.** Not a public endpoint. Out of scope.
- **`GET /api/v1/events/{event_id}/sales/live`.** Deployed, but not public. Out of scope. It is a
  different contract, not a variant of `/sales`: its rows are a homogeneous 11-key shape always
  carrying `source: "sh"`, its `?source=` accepts only `sh` or nothing and 400s `all` and `vs`,
  its `sources` is live-feed health (`{recent, transactions}`) rather than marketplace metadata,
  and it has its own `enriched` field meaning the live row was paired with a mobile sale. That
  `enriched` is unrelated to the field removed from the other two endpoints, and it is staying.
  **Do not share one row model across the three endpoints.**
- **Repointing `get_sales_data()`.** Breaking. Reserved for 2.0.
- **Auto-chunking past 100 events.** One call maps to one request and one rate-limit count.
- **Client-side `source` validation.** The server rejection is free. Pass through.

## Design decisions

### D-01 — Iterators pin and resend every non-cursor parameter

`iter_event_sales()` captures `source`, `id_type`, and `limit` at construction and
resends them on every continuation request. Cursors are bound to `source`, so a
continuation that omits it defaults to `sh` and fails with `invalid_cursor`.

The `iter_event_stats()` template already threads `start_date`, `end_date`, and
`limit` through its `fetch` closure. Follow that pattern exactly and add `source`
and `id_type` to the closure.

Changing `source` mid-iteration is not supported. The iterator holds one value for
its lifetime.

### D-02 — `SalesRow` is a discriminated union

A single flat TypedDict would either lie about required fields or force `Optional`
on everything. Define two shapes and a union, discriminated on the `source` literal:

```python
class SHSalesRow(TypedDict):
    source: Literal["sh"]
    listing_id: int
    all_in_price: None
    zone: str
    section: str
    row: str
    price: float
    quantity: int
    timestamp: int

class VSSalesRow(TypedDict):
    source: Literal["vs"]
    listing_id: str
    all_in_price: Optional[float]
    zone: str
    section: str
    row: str
    price: float
    quantity: int
    timestamp: int
    norm_zone: str
    norm_section: str

SalesRow = Union[SHSalesRow, VSSalesRow]
```

`Literal` comes from `typing_extensions`, already a dependency. mypy must pass on
the union under Python 3.8.

The union is correct regardless, because the key sets genuinely differ by source. `norm_zone` and
`norm_section` exist only on `vs` rows, so no `listing_id` decision removes the union.

**Settled 2026-09-16: keep the split.** `listing_id` stays an int on `sh` rows and a string on
`vs` rows. The union handles it.

Chaz ran the deciding query against production:

```sql
SELECT count() FROM vs.sales WHERE NOT match(listing_id, '^[0-9]+$')
-- 275913
```

275,913 production Vivid Seats listing ids are not digit-only. That is a structural property of
the upstream data, not a handful of bad rows, and it retires every alternative:

- **Int on both is impossible.** The edge cast in `vs_sale_to_row`
  (`services/vividseats_sales.py:452`) would raise on every one of those rows. The tracker's
  defensive `str(...)` coercion in the core repo was correct, not merely cautious.
- **String on both is not worth it.** `_sale_to_json_row_v1` is shared:
  `views_sales_live.py:47` calls it for recorded rows, and `/sales/live` ships an integer
  `listing_id` today. Changing it breaks a deployed contract to tidy a draft one. Special-casing
  the live endpoint would keep the heterogeneity and move it from inside one array to across
  sibling endpoints, which is harder to document, not easier.
- **Keeping the split costs nothing.** It is the status quo, and it is now the only option that
  does not break something or crash on real data.

Two related facts, recorded so nobody re-opens this. The ClickHouse column type is not forced by
the cursor design — the keyset filter and the `ORDER BY` compare the same column, so the walk is
self-consistent either way. And the 2^53 JavaScript concern is not a factor: `sh` ids measured
about 1.3e10 against a 9.0e15 limit, four orders of magnitude of headroom, and that integer
already ships on `/sales/live` and the v0.x endpoints.

**Task 3 of the plan ships exactly as written.** No line changes.

### D-03 — `PageIterator` captures the first page envelope

`total_count` and `sources` appear on the first page only. A bare iterator drops them.

Add `self.first_page: Optional[Envelope]` to `PageIterator` and `AsyncPageIterator`,
set on the first successful fetch. This is additive and harmless to the search and
stats iterators.

`first_page` is the route to first-page metadata. A caller reads `total_count` and
`sources` off `iter_event_sales(...).first_page`. It is `None` before the first fetch,
and a fetch that raises leaves it `None`. An empty first page still sets it, so a
zero-row query still exposes `total_count` and `sources`.

Document that `get_event_sales()` is the direct way to read first-page metadata.

**Amended 2026-09-16, at final whole-branch review.** This decision originally required
`iter_event_sales()` to expose `total_count` and `sources` as convenience properties
reading from `first_page`. The plan dropped that requirement, so no task built the
properties and they did not ship. The capability is not lost: `first_page` carries both
values, and the docstrings, README, CHANGELOG and CLAUDE.md all document that route
consistently. The properties were considered and deferred, not forgotten. Adding them
later is purely additive and non-breaking. They were not added during the final review,
because new public API with no TDD cycle and no task review is the worse trade on a
green release branch.

### D-04 — The batch POST does not auto-retry

The endpoint is billed per event and has no idempotency key. A retried timeout can
re-bill for events already charged on the dropped response.

`get_event_sales_batch()` calls the transport with `retry_safe=False`. The transport
already supports this. A caller who accepts the re-bill risk can retry in their own
code. The docstring states the risk explicitly.

`get_event_sales()` keeps the client's `max_retries`, matching `get_sales_data()`
today. Its docstring notes that a retried first-page timeout may re-bill one pull.

### D-05 — 402 has two shapes, and only one is an exception

- A raw HTTP 402 deny-all raises `SeatDataPaymentError`.
- A per-event `payment_required` inside `errors` is data, not an exception.

State this in the docstring. Test both paths.

### D-06 — `invalid_cursor` stays mapped to `CursorExpiredError`

The server returns `invalid_cursor` for three causes: scope mismatch, expiry, and
`source` mismatch. The SDK cannot distinguish them from the error code alone, and
`seatdata/_transport.py` already maps the code onto `CursorExpiredError`.

Keep that mapping. D-01 prevents the `source` mismatch case from arising through the
iterator. Document that a cursor cannot be replayed under a different `source`, and
that recovery means restarting the walk, not resending.

A distinct server-side error code would let the SDK tell these apart. Filed under
"Server-side findings" below.

### D-07 — Batch result lookup is by decimal string

`prepare_batch_payload()` coerces every id to `int`, so the server keys `results`,
`errors`, and `sources` by the decimal string of that int. A caller who passed
`"105294241"` looks up `results["105294241"]`. A caller who passed `105294241` looks
up the same key.

`normalize_batch_response()` passes keys through untouched. That is correct and
stays. Tests must cover int ids, digit-string ids, and the same numeric id sent in
both `event_ids` and `event_ids_sh`.

### D-08 — `source` is omitted when not supplied

The SDK sends no `source` parameter unless the caller passes one. It does not default
to `"sh"` explicitly. An omitted `source` reproduces the pre-update request exactly,
which keeps billing and cursor behavior identical to today.

### D-09 — `sources[].status` is surfaced, not raised

A `status` of `"unavailable"` means one marketplace could not be read. The response
still succeeds with the rows that were available. The SDK returns it as data. It does
not raise and does not warn.

## Scope

### Stage 1 — land before 1.1.0, as its own PR

Cherry-pick from `feat/batch-salesdata` onto a fresh branch off `main`:

- `748fa9f` — `SeatDataPaymentError` and its export
- `7fbc572` — SDK-wide 402 transport wiring, with tests
- `3f18eb4` — deprecation targets v1.1 to v2.0
- `5aebcea` — the matching README correction

Additive, merges clean, and fixes 402 handling for `get_sales_data()` and
`get_listings()` today.

### Stage 2 — 1.1.0

1. `get_event_sales()` and `iter_event_sales()`, sync and async, on the v1 single endpoint. Keep the `event_id` / `event_id_sh` argument pair, mapping `event_id_sh` to `id_type=marketplace`.
2. `get_event_sales_batch()`, sync and async, on the v1 batch endpoint. Reuse `prepare_batch_payload()` unchanged.
3. A `source` parameter on all three, per D-08.
4. Types per D-02: `SHSalesRow`, `VSSalesRow`, `SalesRow`, `SalesPage`, `SourceBlock`, and a `sources` key on `BatchSalesResult`.
5. `first_page` capture on both iterators, per D-03.
6. Deprecate `get_sales_data()` with a `DeprecationWarning` naming `get_event_sales()`, removal target v2.0. Leave it on `/api/v0.3/salesdata/get`.
7. Bump to 1.1.0.
8. Docs, CHANGELOG, examples, and the migration table below.

### Naming

`get_event_sales()`, `iter_event_sales()`, `get_event_sales_batch()`. These match
`get_event_stats()` and `iter_event_stats()`, and avoid tying new methods to the
deprecated `get_sales_data` name. The rename from the branch's
`get_sales_data_batch()` is free, because that method never shipped on `main`.

### Reserved for 2.0

- Remove `get_sales_data()`, `search_events_legacy()`, `event_request_add()`, `event_request_status()`
- Repoint `get_listings()` to the v1 live listings route once it is public
- Adopt v1 replacements for daily CSV and event requests once they exist

## Migration table

| `get_sales_data()` | `get_event_sales()` |
|---|---|
| `GET /api/v0.3/salesdata/get` | `GET /api/v1/events/{event_id}/sales` |
| returns `List[Dict[str, Any]]` | returns `SalesPage`; rows are in `page["data"]` |
| all rows in one response | cursor paginated, `limit` default 100, max 200 |
| `sh` only | `source` selects `sh`, `vs`, or `all` |
| no `source` field on rows | every row carries `source` and `all_in_price` |
| no `total_count` | `total_count` on the first page |
| no marketplace metadata | `sources` block on the first page |
| `event_id` / `event_id_sh` | unchanged, `event_id_sh` maps to `id_type=marketplace` |

## Test plan

Required before 1.1.0 ships. Every item runs against both the sync and the async client.

**Pagination and cursor binding**

- A two-page walk under `source` omitted, `sh`, `vs`, and `all`
- Continuation requests carry `source`, `id_type`, and `limit`
- A cursor replayed under a different `source` raises `CursorExpiredError`
- `CursorExpiredError` mid-walk carries `items_yielded` and `last_cursor`
- `first_page` is `None` before the first fetch and populated after
- `total_count` and `sources` are readable from the iterator, and absent from page two

**Row typing**

- An `sh` row and a `vs` row in one page narrow correctly under mypy
- `listing_id` is int on `sh` and str on `vs`
- `norm_zone` and `norm_section` are absent on `sh` rows

**Batch**

- Int ids, digit-string ids, and the same numeric id in both lists
- The 100-cap raises `ValueError` client-side with no network call
- An empty payload raises `ValueError`
- `results`, `errors`, and `sources` all key by decimal string
- Per-event `payment_required` returns as data
- A raw HTTP 402 raises `SeatDataPaymentError`
- `retry_safe=False` is honoured: a 429 is not retried

**402 SDK-wide**

- 402 raises `SeatDataPaymentError` from `get_sales_data()` and `get_listings()`
- Every documented 402 body shape maps to the same class

**Gates**

- `pytest` green, `mypy seatdata/` clean, `black --check` clean

## Server-side findings

Verified by the API team against `4b81fe87`. All five facts confirmed. Two of my premises were
wrong; the corrections are folded in below. None block 1.1.0.

### 1. The batch endpoint has no response size bound — CONFIRMED, open

`merge_two_store_page(..., limit=None)`, no slice on the `sh` queryset, no `LIMIT` in
`fetch_sales_for_events`, and `parse_limit` is called only by the single endpoint. The only bound
is the 100-event cap. Nothing caps it upstream or in the service layer.

Corrections to my original claim. The "roughly doubles under `source=all`" line was too strong:
`vs` collection began 2026-08-21, so those row counts are far smaller than `sh`'s
multi-year history, and the default is `sh`, so a caller only takes the extra rows by opting in.
It is pre-existing, as I thought — the v0.3 batch has the same shape and has been live since
2026-07-10.

The fix is bigger than adding a `limit` parameter, because a truncated event still gets charged.
With Chaz as a follow-up.

### 2. `invalid_cursor` conflates three causes — CONFIRMED, open, but my fix was wrong

Three raise sites, one code, three messages. My proposed `cursor_source_mismatch` would make sales
the odd endpoint out: search and stats already use the same single code for scope mismatch and
expiry. A fix should be one machine-readable sub-reason across all of v1, not a sales-only code.

Until then, `error.param` and the message text do differ per cause. The SDK does not depend on
telling them apart, because D-01 prevents the `source` mismatch from arising.

### 3. No idempotency on billed calls — CONFIRMED, broader than I said, open

The only `request_id` is server-generated per request and used as a ledger note. There is no
uniqueness constraint on the click rows. This exposes **every billed v1 endpoint**, not just batch.

D-04's no-retry policy is the right thing to ship.

### 4. `listing_id` type union — fact confirmed, my premise was wrong

I wrote that this is already public and therefore breaking to change. It is not public. The
help-center article is `state: "draft"` with an empty `article_id` and has never synced, and the
branch is unpushed. The wire format is still free to change. See the open question under D-02.

### 5. `sources` names three shapes, not two — fact confirmed, my premise was wrong

Same publicity error as finding 4. And there are three shapes, not two: `/sales` returns an array,
`/sales/batch` returns a map keyed by client-sent event id, and `/sales/live` returns live-feed
health as `{recent, transactions}`.

The API team is keeping it deliberately. The batch envelope already keys `results` and `errors` by
event id, so keying `sources` the same way is the consistent choice, and the live endpoint's is
nested rather than top-level. Recorded as a known wart, not a surprise.

## Model assignment

Planning runs on Opus at `max` effort. Implementation runs on Sonnet.

| Work | Model |
|---|---|
| This spec, and the plan derived from it | Opus, `max` effort |
| Design review and between-task review | Opus |
| Writing code the plan already specifies | Sonnet |

Within implementation, a task may be promoted to Opus when it is correctness-critical
or subtle. On this plan that means D-02 row-union typing, D-03 first-page capture,
D-04 retry policy, and D-05 402 routing. The remaining tasks are mechanical and stay
on Sonnet. The plan carries a per-task `**Model:**` line and a summary table.
