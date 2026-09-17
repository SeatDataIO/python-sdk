"""Demonstrates AsyncSeatDataClient, focusing on what differs from the sync client.

For the full endpoint catalogue see all_endpoints.py. Every method there exists on
AsyncSeatDataClient with the same name and the same arguments, so this file covers the
three things the sync example cannot teach rather than repeating all fourteen.

The one real trap:

    rows = client.iter_event_sales(event_id=225220)   # NOT awaited
    async for sale in rows:                           # async for, not for
        ...

iter_event_sales(), iter_event_stats() and iter_search_events() are plain methods that
return an AsyncPageIterator. They are not coroutines. Writing `await client.iter_...()`
raises TypeError. Everything else on the client is a coroutine and must be awaited.

One section is metered and is skipped unless you set SEATDATA_RUN_BILLED=1:
get_event_sales_batch(). See https://docs.seatdata.io/docs/api/ for pricing.

Usage:
    export SEATDATA_API_KEY="<your 64-character key>"
    python async_usage.py
"""

import asyncio
import os

from seatdata import AsyncSeatDataClient, SeatDataError, SeatDataPaymentError

RUN_BILLED = os.environ.get("SEATDATA_RUN_BILLED") == "1"


async def awaited_calls(client):
    """Every non-iterator method is a coroutine. Await it."""
    account = await client.get_account()
    print(f"  user_id: {account.get('user_id')}")

    usage = await client.get_usage()
    print(f"  period:  {usage.get('period_start')} -> {usage.get('period_end')}")

    events = await client.search_events(event_name="$uicideboy$", limit=5)
    print(f"  search_events() returned {len(events)} items")
    return events


async def async_iteration(client, event_id):
    """iter_* methods are NOT coroutines. Do not await them; use async for."""
    snapshots = client.iter_event_stats(int(event_id), limit=5)
    walked = 0
    async for _ in snapshots:
        walked += 1
        if walked >= 10:
            break
    print(f"  iter_event_stats() walked {walked} snapshots")

    rows = client.iter_event_sales(event_id=event_id, limit=5, source="all")
    walked = 0
    async for sale in rows:
        if walked < 3:
            print(f"    {sale['source']} {sale['section']} row {sale['row']} ${sale['price']}")
        walked += 1
        if walked >= 10:
            break
    print(f"  iter_event_sales() walked {walked} rows")
    print(f"  first_page total_count: {rows.first_page.get('total_count')}")


async def billed_batch(client, event_ids):
    """POST /api/v1/events/sales/batch, every sale for each event in one response."""
    result = await client.get_event_sales_batch(event_ids=event_ids, source="all")
    for event_id, sales in result["results"].items():
        print(f"    event {event_id}: {len(sales)} sales")
    for event_id, reason in result["errors"].items():
        print(f"    event {event_id}: {reason}")


async def concurrent_calls(client, event_ids):
    """Independent reads can run together with asyncio.gather()."""
    results = await asyncio.gather(
        *(client.get_listings(event_id=str(event_id)) for event_id in event_ids),
        return_exceptions=True,
    )
    for event_id, result in zip(event_ids, results):
        if isinstance(result, Exception):
            print(f"    event {event_id}: {type(result).__name__}: {result}")
        else:
            print(f"    event {event_id}: {len(result.get('listings', []))} listings")


async def run(label, coro):
    print(f"\n=== {label} ===")
    try:
        return await coro
    except SeatDataPaymentError as e:
        print(f"  payment required: {e}")
    except SeatDataError as e:
        print(f"  API error: {e}")
    except Exception as e:
        print(f"  {type(e).__name__}: {e}")
    return None


async def main():
    api_key = os.environ.get("SEATDATA_API_KEY")
    if not api_key:
        print("Please set SEATDATA_API_KEY environment variable")
        print("You can get an API key from support@seatdata.io")
        return

    base_url = os.environ.get("SEATDATA_BASE_URL", "https://seatdata.io").rstrip("/")
    print(f"Base URL: {base_url}")
    if not RUN_BILLED:
        print("The metered section is skipped. Set SEATDATA_RUN_BILLED=1 to include it.")

    async with AsyncSeatDataClient(api_key=api_key, base_url=base_url) as client:
        events = await run("Awaited calls", awaited_calls(client)) or []
        if not events:
            print("\nNo events found, so the per-event sections are skipped.")
            return

        event_id = events[0]["event_id"]
        event_ids = [e["event_id"] for e in events[:3]]
        print(f"\nUsing event_id={event_id} for the per-event sections.")

        await run("Async iteration", async_iteration(client, event_id))
        await run("Concurrent reads", concurrent_calls(client, event_ids))

        if RUN_BILLED:
            await run("Sales batch (v1)", billed_batch(client, event_ids))
        else:
            print("\n=== Sales batch (v1) ===")
            print("  skipped: metered")


if __name__ == "__main__":
    asyncio.run(main())
