from typing import Any, Awaitable, Callable, Dict, Generic, Iterator, List, Optional, TypeVar

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
