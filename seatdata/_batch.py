from typing import Any, Dict, List, Optional, Sequence, Union

from .types import BatchSalesResult


def _coerce_ids(name: str, values: Optional[Sequence[Union[int, str]]]) -> List[int]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be an iterable of event ids, not {type(values).__name__}")
    try:
        iterator = iter(values)
    except TypeError:
        raise ValueError(
            f"{name} must be an iterable of event ids, not {type(values).__name__}"
        ) from None
    coerced: List[int] = []
    for value in iterator:
        if isinstance(value, bool):
            raise ValueError(f"Invalid event id in {name}: {value!r}")
        if isinstance(value, int):
            coerced.append(value)
        elif isinstance(value, str):
            try:
                coerced.append(int(value))
            except (TypeError, ValueError):
                raise ValueError(f"Invalid event id in {name}: {value!r}") from None
        else:
            raise ValueError(f"Invalid event id in {name}: {value!r}")
    return list(dict.fromkeys(coerced))


def prepare_batch_payload(
    event_ids_sh: Optional[Sequence[Union[int, str]]],
    event_ids: Optional[Sequence[Union[int, str]]],
) -> Dict[str, List[int]]:
    sh_ids = _coerce_ids("event_ids_sh", event_ids_sh)
    sd_ids = _coerce_ids("event_ids", event_ids)
    if not sh_ids and not sd_ids:
        raise ValueError("Either event_ids_sh or event_ids must be provided")
    total = len(sh_ids) + len(sd_ids)
    if total > 100:
        raise ValueError(f"A batch supports at most 100 unique event ids, got {total}")
    payload: Dict[str, List[int]] = {}
    if sh_ids:
        payload["event_ids_sh"] = sh_ids
    if sd_ids:
        payload["event_ids"] = sd_ids
    return payload


def normalize_batch_response(body: Any) -> BatchSalesResult:
    data = body or {}
    return {
        "results": data.get("results") or {},
        "errors": data.get("errors") or {},
        "sources": data.get("sources") or {},
    }
