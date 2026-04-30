import asyncio
import os
import sys

from seatdata import AsyncSeatDataClient, SeatDataClient


def banner(label):
    print(f"\n=== {label} ===")


def sync_smoke(api_key, base_url):
    failures = []

    with SeatDataClient(api_key=api_key, base_url=base_url) as client:
        banner("1. get_account()")
        try:
            account = client.get_account()
            print(f"  user_id:        {account['user_id']}")
            print(f"  email:          {account['email']}")
            print(f"  plans:          {[p['id'] for p in account['plans']]}")
            print(f"  rate_limit keys: {sorted(account['rate_limits'].keys())}")
        except Exception as e:
            failures.append(("get_account", e))
            print(f"  FAILED: {type(e).__name__}: {e}")

        banner("2. get_usage()")
        try:
            usage = client.get_usage()
            print(f"  period:         {usage['period_start']} -> {usage['period_end']}")
            print(f"  api_calls:      {usage['totals']['api_calls']}")
            print(f"  events_searched:{usage['totals']['events_searched']}")
        except Exception as e:
            failures.append(("get_usage", e))
            print(f"  FAILED: {type(e).__name__}: {e}")

        banner("3. search_events() v1 GET")
        events = []
        try:
            events = client.search_events(venue_name="Madison Square Garden", limit=5)
            print(f"  found:          {len(events)} events (page 1)")
            for ev in events[:3]:
                print(f"    - {ev['event_id']:>8}  {ev['event_date']}  " f"{ev['event_name'][:50]}")
        except Exception as e:
            failures.append(("search_events", e))
            print(f"  FAILED: {type(e).__name__}: {e}")

        banner("4. iter_search_events() auto-pagination")
        try:
            count = 0
            for _ in client.iter_search_events(venue_name="Madison Square Garden", limit=20):
                count += 1
                if count >= 25:
                    break
            print(f"  iterated:       {count} events across pages")
        except Exception as e:
            failures.append(("iter_search_events", e))
            print(f"  FAILED: {type(e).__name__}: {e}")

        if not events:
            print("\n  Skipping stats/sales/listings checks: no events to test against.")
            return failures

        event_id = events[0]["event_id"]
        print(f"\n  Using event_id={event_id} for paid endpoint checks.")

        banner("5. get_event_stats() v1 paid")
        try:
            page = client.get_event_stats(event_id, limit=10)
            print(f"  event_id:       {page['event_id']}")
            print(f"  data rows:      {len(page['data'])}")
            print(f"  has_more:       {page['has_more']}")
            if "available_zones" in page:
                print(f"  available_zones:{page['available_zones']}")
            if "total_count" in page:
                print(f"  total_count:    {page['total_count']}")
            if page["data"]:
                snap = page["data"][0]
                print(
                    f"  first snapshot: {snap['timestamp']}  "
                    f"get_in={snap['get_in']}  avg={snap['avg_price']}"
                )
        except Exception as e:
            failures.append(("get_event_stats", e))
            print(f"  FAILED: {type(e).__name__}: {e}")

        banner("6. iter_event_stats() auto-pagination")
        try:
            it = client.iter_event_stats(event_id, limit=10)
            count = 0
            for _ in it:
                count += 1
                if count >= 50:
                    break
            print(f"  iterated:       {count} snapshots")
            print(f"  current_cursor: {it.current_cursor}")
        except Exception as e:
            failures.append(("iter_event_stats", e))
            print(f"  FAILED: {type(e).__name__}: {e}")

        banner("7. get_sales_data() v0.x preserved")
        try:
            sales = client.get_sales_data(event_id=str(event_id))
            print(f"  records:        {len(sales)}")
        except Exception as e:
            failures.append(("get_sales_data", e))
            print(f"  FAILED: {type(e).__name__}: {e}")

        banner("8. get_listings() v0.x preserved")
        try:
            listings = client.get_listings(event_id=str(event_id))
            count = len(listings.get("listings", []))
            print(f"  listings:       {count}")
        except Exception as e:
            failures.append(("get_listings", e))
            print(f"  FAILED: {type(e).__name__}: {e}")

    return failures


async def async_smoke(api_key, base_url):
    failures = []
    banner("9. AsyncSeatDataClient: get_account + iter_search_events")
    try:
        async with AsyncSeatDataClient(api_key=api_key, base_url=base_url) as client:
            account = await client.get_account()
            print(f"  user_id:        {account['user_id']}")
            count = 0
            async for _ in client.iter_search_events(venue_name="Madison Square Garden", limit=10):
                count += 1
                if count >= 5:
                    break
            print(f"  async iterated: {count} events")
    except Exception as e:
        failures.append(("async client", e))
        print(f"  FAILED: {type(e).__name__}: {e}")
    return failures


def main():
    api_key = os.environ.get("SEATDATA_API_KEY")
    if not api_key:
        print("SEATDATA_API_KEY environment variable not set.")
        print("Set it before running: export SEATDATA_API_KEY=<your_64_char_hex_key>")
        sys.exit(2)

    if len(api_key) != 64:
        print(f"SEATDATA_API_KEY must be 64 characters (got {len(api_key)}).")
        sys.exit(2)

    base_url = os.environ.get("SEATDATA_BASE_URL", "https://seatdata.io").rstrip("/")

    print("SeatData SDK v1.0.0 smoke test")
    print(f"Base URL:      {base_url}")
    print(f"Using API key: {api_key[:8]}...{api_key[-4:]}")

    sync_failures = sync_smoke(api_key, base_url)
    async_failures = asyncio.run(async_smoke(api_key, base_url))

    failures = sync_failures + async_failures

    print("\n" + "=" * 60)
    if failures:
        print(f"SMOKE TEST FAILED — {len(failures)} step(s) errored:")
        for name, err in failures:
            print(f"  - {name}: {type(err).__name__}: {err}")
        sys.exit(1)
    else:
        print("SMOKE TEST PASSED — all v1 + v0.x + async paths returned successfully.")
        sys.exit(0)


if __name__ == "__main__":
    main()
