"""Demonstrates every current SeatData API endpoint, one section each.

Legacy endpoints are deliberately excluded. get_sales_data(), search_events_legacy(),
event_request_add() and get_event_request_status()'s alias event_request_status() are
all deprecated and slated for removal in v2.0.

Three calls are metered or rate-limited, so they are skipped unless you set
SEATDATA_RUN_BILLED=1: get_event_sales(), get_event_sales_batch() and
download_daily_csv(), which also needs a Daily Event CSV subscription.

See https://docs.seatdata.io/docs/api/ for pricing and rate limits.

Usage:
    export SEATDATA_API_KEY="<your 64-character key>"
    python all_endpoints.py
"""

import os

from seatdata import SeatDataClient, SeatDataError, SeatDataPaymentError

RUN_BILLED = os.environ.get("SEATDATA_RUN_BILLED") == "1"


def show_account(client):
    """GET /api/v1/account"""
    account = client.get_account()
    print(f"  user_id: {account.get('user_id')}")
    print(f"  email:   {account.get('email')}")
    print(f"  company: {account.get('company')}")
    for plan in account.get("plans", []):
        print(f"  plan:    {plan}")


def show_usage(client):
    """GET /api/v1/usage"""
    usage = client.get_usage()
    print(f"  period: {usage.get('period_start')} -> {usage.get('period_end')}")
    print(f"  totals: {usage.get('totals')}")
    for row in usage.get("by_endpoint", []):
        print(f"    {row.get('endpoint')}: {row.get('count')}")


def search_events(client):
    """GET /api/v1/events/search, read three ways. Returns the items for later sections."""
    events = client.search_events(event_name="$uicideboy$", limit=5)
    print(f"  search_events() returned {len(events)} items")
    for event in events[:3]:
        print(f"    {event.get('event_id')}  {event.get('event_name')}  {event.get('event_date')}")

    page = client.search_events_page(event_name="$uicideboy$", limit=5)
    print(f"  search_events_page() has_more={page.get('has_more')}")
    print(f"  next_cursor={page.get('next_cursor')}")

    walked = 0
    for _ in client.iter_search_events(event_name="$uicideboy$", limit=5):
        walked += 1
        if walked >= 12:
            break
    print(f"  iter_search_events() walked {walked} items across pages")

    return events


def show_event_stats(client, event_id):
    """GET /api/v1/events/{event_id}/stats, one page then a cursor walk."""
    page = client.get_event_stats(int(event_id), limit=5)
    print(f"  total_count: {page.get('total_count')}")
    print(f"  has_more: {page.get('has_more')}")
    for snapshot in page.get("data", [])[:3]:
        print(f"    {snapshot}")

    walked = 0
    for _ in client.iter_event_stats(int(event_id), limit=5):
        walked += 1
        if walked >= 12:
            break
    print(f"  iter_event_stats() walked {walked} snapshots")


def show_event_sales(client, event_id):
    """GET /api/v1/events/{event_id}/sales, one page then a cursor walk."""
    page = client.get_event_sales(event_id=event_id, limit=5, source="all")
    print(f"  total_count: {page.get('total_count')}")
    for block in page.get("sources", []):
        print(
            f"    {block['source']}: tracked={block['tracked_for_event']} "
            f"status={block['status']} since={block['collecting_since']}"
        )
    for sale in page["data"][:3]:
        print(f"    {sale['source']} {sale['section']} row {sale['row']} ${sale['price']}")

    rows = client.iter_event_sales(event_id=event_id, limit=5, source="all")
    walked = 0
    for _ in rows:
        walked += 1
        if walked >= 12:
            break
    print(f"  iter_event_sales() walked {walked} rows")
    print(f"  first_page total_count: {rows.first_page.get('total_count')}")


def show_event_sales_batch(client, event_ids):
    """POST /api/v1/events/sales/batch, every sale for each event in one response."""
    result = client.get_event_sales_batch(event_ids=event_ids, source="all")
    for event_id, sales in result["results"].items():
        print(f"    event {event_id}: {len(sales)} sales")
    if result["errors"]:
        for event_id, reason in result["errors"].items():
            print(f"    event {event_id}: {reason}")
    else:
        print("    no per-event errors")


def show_listings(client, event_id):
    """GET /api/v0.1/listings/get"""
    listings = client.get_listings(event_id=str(event_id))
    rows = listings.get("listings", [])
    print(f"  {len(rows)} live listings")
    for listing in rows[:3]:
        print(f"    {listing.get('section')} row {listing.get('row')} ${listing.get('price')}")


def show_daily_csv(client):
    """GET /api/v0.5/daily-csv/download. Needs a Daily Event CSV subscription."""
    csv_text = client.download_daily_csv()
    lines = csv_text.splitlines()
    print(f"  {len(lines)} lines")
    for line in lines[:2]:
        print(f"    {line[:100]}")


def show_event_request(client):
    """POST /api/v0.4/events/event-request-add then GET .../event-request-status/{job_id}/"""
    submitted = client.create_event_request(search_query="Golden State Warriors")
    job_id = submitted.get("job_id")
    print(f"  job_id: {job_id}")
    if not job_id:
        return
    status = client.get_event_request_status(job_id=job_id)
    print(f"  status: {status.get('status')}")


def run(label, fn, *args):
    print(f"\n=== {label} ===")
    try:
        return fn(*args)
    except SeatDataPaymentError as e:
        print(f"  payment required: {e}")
    except SeatDataError as e:
        print(f"  API error: {e}")
    except Exception as e:
        print(f"  {type(e).__name__}: {e}")
    return None


def skip(label, reason):
    print(f"\n=== {label} ===")
    print(f"  skipped: {reason}")


def main():
    api_key = os.environ.get("SEATDATA_API_KEY")
    if not api_key:
        print("Please set SEATDATA_API_KEY environment variable")
        print("You can get an API key from support@seatdata.io")
        return

    base_url = os.environ.get("SEATDATA_BASE_URL", "https://seatdata.io").rstrip("/")
    print(f"Base URL: {base_url}")
    if not RUN_BILLED:
        print("Metered sections are skipped. Set SEATDATA_RUN_BILLED=1 to include them.")

    with SeatDataClient(api_key=api_key, base_url=base_url) as client:
        run("Account", show_account, client)
        run("Usage", show_usage, client)

        events = run("Event search", search_events, client) or []
        if not events:
            print("\nNo events found, so the per-event sections are skipped.")
            run("Event request", show_event_request, client)
            return

        event_id = events[0]["event_id"]
        event_ids = [e["event_id"] for e in events[:3]]
        print(f"\nUsing event_id={event_id} for the per-event sections.")

        run("Event stats", show_event_stats, client, event_id)
        run("Listings", show_listings, client, event_id)

        if RUN_BILLED:
            run("Event sales (v1)", show_event_sales, client, event_id)
            run("Event sales batch (v1)", show_event_sales_batch, client, event_ids)
            run("Daily CSV", show_daily_csv, client)
        else:
            skip("Event sales (v1)", "metered")
            skip("Event sales batch (v1)", "metered")
            skip("Daily CSV", "metered, and needs a Daily Event CSV subscription")

        run("Event request", show_event_request, client)


if __name__ == "__main__":
    main()
