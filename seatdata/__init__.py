from .client import SeatDataClient
from .exceptions import (
    SeatDataException,
    AuthenticationError,
    RateLimitError,
    SubscriptionError,
    NotFoundError,
    ServiceUnavailableError,
)

__version__ = "0.3.0"
__all__ = [
    "SeatDataClient",
    "SeatDataException",
    "AuthenticationError",
    "RateLimitError",
    "SubscriptionError",
    "NotFoundError",
    "ServiceUnavailableError",
]
