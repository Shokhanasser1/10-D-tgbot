import math
from collections.abc import Mapping
from typing import Any

from app.schemas.geo import Coordinates


def _as_finite_number(value: Any) -> float | None:
    # bool is an int subclass; a stray True/False must not pass for a coordinate.
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) else None


def destination_from_address(address: Mapping[str, Any]) -> Coordinates | None:
    """The customer's delivery pin, if they set one.

    Tolerates addresses stored before pins existed (no keys) and anything malformed: a bad
    value means "no destination", never an error.
    """
    latitude = _as_finite_number(address.get("latitude"))
    longitude = _as_finite_number(address.get("longitude"))
    if latitude is None or longitude is None:
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return Coordinates(latitude=latitude, longitude=longitude)
