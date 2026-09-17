from typing import Any, Dict, Optional, Tuple, Union


def _coerce_event_id(name: str, value: Optional[Union[int, str]]) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Invalid event id in {name}: {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid event id in {name}: {value!r}") from None
    raise ValueError(f"Invalid event id in {name}: {value!r}")


def resolve_sales_id(
    event_id: Optional[Union[int, str]],
    event_id_sh: Optional[Union[int, str]],
) -> Tuple[int, Optional[str]]:
    if event_id is None and event_id_sh is None:
        raise ValueError("Either event_id or event_id_sh must be provided")
    if event_id is not None and event_id_sh is not None:
        raise ValueError("Provide only one of event_id or event_id_sh")
    if event_id is not None:
        return _coerce_event_id("event_id", event_id), None
    return _coerce_event_id("event_id_sh", event_id_sh), "marketplace"


def build_event_sales_params(
    *,
    limit: Optional[int] = None,
    starting_after: Optional[str] = None,
    source: Optional[str] = None,
    id_type: Optional[str] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    if limit is not None:
        params["limit"] = limit
    if starting_after is not None:
        params["starting_after"] = starting_after
    if source is not None:
        params["source"] = source
    if id_type is not None:
        params["id_type"] = id_type
    return params
