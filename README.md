# SeatData Python SDK

[![PyPI version](https://img.shields.io/pypi/v/seatdata-sdk.svg)](https://pypi.org/project/seatdata-sdk/)
[![Tests](https://github.com/SeatDataIO/python-sdk/actions/workflows/test.yml/badge.svg)](https://github.com/SeatDataIO/python-sdk/actions/workflows/test.yml)
[![Python Support](https://img.shields.io/pypi/pyversions/seatdata-sdk)](https://pypi.org/project/seatdata-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Official Python SDK for SeatData API - access ticket sales data, event listings, and search functionality.

**API Documentation:** https://docs.seatdata.io

## Installation

```bash
pip install seatdata-sdk
```

## Quick Start

### Sync

```python
from seatdata import SeatDataClient

client = SeatDataClient(api_key="your_64_char_api_key")

# Verify auth + see your plans and rate limits
account = client.get_account()
print(account["plans"])

# Search events (v1) - returns list of items from one page
events = client.search_events(venue_name="Madison Square Garden", venue_city="New York")

# Or iterate all matching events across pages
for event in client.iter_search_events(event_name="$uicideboy$"):
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
        events = await client.search_events(event_name="$uicideboy$")
        if events:
            event_id = str(events[0]["event_id"])
            sales = await client.get_sales_data(event_id=event_id)
            print(f"{len(sales)} sales records for event {event_id}")


asyncio.run(main())
```

## v1 Sales

`get_event_sales()`, `iter_event_sales()`, and `get_event_sales_batch()` read
`GET /api/v1/events/{event_id}/sales` and `POST /api/v1/events/sales/batch`. All three accept
`event_id` or `event_id_sh`, plus an optional `source` (`sh`, `vs`, or `all`). Omitting `source`
reproduces the previous sh-only behavior.

### Sync

```python
from seatdata import SeatDataClient

client = SeatDataClient(api_key="your_64_char_api_key")

# One page
page = client.get_event_sales(event_id=12345, limit=50)
for row in page["data"]:
    print(row["source"], row["price"], row["quantity"])

# A full cursor walk. first_page holds the metadata the server sends once, on page one.
iterator = client.iter_event_sales(event_id=12345, source="all")
rows = list(iterator)
print(len(rows), "rows")
print(iterator.first_page["total_count"], iterator.first_page["sources"])

# Up to 100 events in one call
result = client.get_event_sales_batch(event_ids=[12345, 67890])
for event_id, event_rows in result["results"].items():
    print(event_id, len(event_rows))
for event_id, reason in result["errors"].items():
    print(event_id, reason)  # "not_found" or "payment_required"
```

### Async

```python
import asyncio
from seatdata import AsyncSeatDataClient


async def main():
    async with AsyncSeatDataClient(api_key="your_64_char_api_key") as client:
        # One page
        page = await client.get_event_sales(event_id=12345, limit=50)
        for row in page["data"]:
            print(row["source"], row["price"], row["quantity"])

        # A full cursor walk. first_page holds the metadata the server sends once, on page one.
        iterator = client.iter_event_sales(event_id=12345, source="all")
        rows = [row async for row in iterator]
        print(len(rows), "rows")
        print(iterator.first_page["total_count"], iterator.first_page["sources"])

        # Up to 100 events in one call
        result = await client.get_event_sales_batch(event_ids=[12345, 67890])
        for event_id, event_rows in result["results"].items():
            print(event_id, len(event_rows))


asyncio.run(main())
```

### Retries

- `get_event_sales()` retries on the client's default `max_retries` (3). Construct the client
  with `max_retries=0` to disable them.
- `get_event_sales_batch()` is **never** retried automatically, because the endpoint is not
  idempotent. It calls the transport with `retry_safe=False`, which suppresses retries not only
  on `429`, `502`, `503`, and `504` responses but also on `ConnectError`, `ReadTimeout`, and
  `RemoteProtocolError`. A timeout there may mean the server processed the request and the
  response was lost, not that nothing happened. A caller who accepts that risk can retry in
  their own code.
- A `402` response raises `SeatDataPaymentError` from either method. A per-event failure inside
  a batch call is data, not an exception: it shows up as `"payment_required"` in
  `result["errors"]`.

See [the API documentation](https://docs.seatdata.io/docs/api/) for pricing.

### Migrating from `get_sales_data()`

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

## Migrating from v0.3.x

- `search_events()` now calls `GET /v1/events/search` and returns the v1 envelope's `data`. The legacy `POST /v0.3.1/events/search` is available as `search_events_legacy()` (deprecated, removed in v2.0).
- `event_request_add` → `create_event_request`. `event_request_status` → `get_event_request_status`. Old names remain as deprecated aliases.
- Exceptions gained richer attributes: `SeatDataRateLimitError.retry_after`, `SeatDataInvalidRequestError.param`, `CursorExpiredError.items_yielded` / `.last_cursor`. Legacy exception names (`AuthenticationError`, `RateLimitError`, etc.) are preserved as aliases.
- The HTTP layer is now `httpx`. If you caught `requests.exceptions.*` directly, switch to `seatdata.SeatDataError`.

## API Key

Contact support@seatdata.io to obtain an API key.

## Development

```bash
# Clone the repository
git clone https://github.com/SeatDataIO/python-sdk.git
cd python-sdk

# Install development dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run integration tests (requires API key)
export SEATDATA_API_KEY="your_api_key"
pytest -m integration
```

## License

MIT