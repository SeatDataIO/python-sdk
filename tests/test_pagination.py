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
