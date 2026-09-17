# SeatData SDK Examples

Two examples: one covering every endpoint synchronously, one covering what the async
client does differently.

## Setup

1. Install the SDK:
```bash
pip install -e ..
```

2. Set your API key as an environment variable:
```bash
export SEATDATA_API_KEY="your_64_character_api_key_here"
```

The key must be a 64-character hexadecimal string. `SeatDataClient` raises `ValueError`
on anything else.

Optionally point the client at a different host:
```bash
export SEATDATA_BASE_URL="https://seatdata.io"
```

## all_endpoints.py

Every current endpoint, one section each, using `SeatDataClient`:

| Section | Methods |
|---|---|
| Account | `get_account()` |
| Usage | `get_usage()` |
| Event search | `search_events()`, `search_events_page()`, `iter_search_events()` |
| Event stats | `get_event_stats()`, `iter_event_stats()` |
| Event sales | `get_event_sales()`, `iter_event_sales()` |
| Event sales batch | `get_event_sales_batch()` |
| Listings | `get_listings()` |
| Daily CSV | `download_daily_csv()` |
| Event request | `create_event_request()`, `get_event_request_status()` |

No deprecated endpoints are used.

```bash
python all_endpoints.py
```

## async_usage.py

`AsyncSeatDataClient`, covering only what differs from the sync client — the client
lifecycle, awaiting, async iteration, and running independent reads concurrently with
`asyncio.gather()`. Every method in the table above exists on the async client with the
same name and arguments, so this file does not repeat the catalogue.

The one real trap it exists to prevent:

```python
rows = client.iter_event_sales(event_id=225220)   # NOT awaited
async for sale in rows:                           # async for, not for
    ...
```

`iter_event_sales()`, `iter_event_stats()` and `iter_search_events()` are plain methods
returning an `AsyncPageIterator`. They are not coroutines, so `await client.iter_...()`
raises `TypeError`. Every other method on the client is a coroutine and must be awaited.

```bash
python async_usage.py
```

## Metered sections

Three calls are metered or rate-limited, so both examples skip them unless you set
`SEATDATA_RUN_BILLED=1`:

- `get_event_sales()`
- `get_event_sales_batch()`
- `download_daily_csv()`, which also needs a Daily Event CSV subscription

```bash
SEATDATA_RUN_BILLED=1 python all_endpoints.py
```

See [the API documentation](https://docs.seatdata.io/docs/api/) for pricing and rate limits.

Note that `get_event_sales_batch()` returns every sale for every event requested — the
endpoint accepts no `limit` and does not paginate. For events with deep sales histories,
`iter_event_sales()` per event gives bounded, cursor-resumable pages instead.

## Deprecated methods

These still work and still emit a `DeprecationWarning`. They are scheduled for removal in
v2.0, and no example here uses them:

| Deprecated | Use instead |
|---|---|
| `get_sales_data()` | `get_event_sales()` |
| `search_events_legacy()` | `search_events()` |
| `event_request_add()` | `create_event_request()` |
| `event_request_status()` | `get_event_request_status()` |

## Getting an API Key

Contact support@seatdata.io to obtain an API key for the SeatData API.
