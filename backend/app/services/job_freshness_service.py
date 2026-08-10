"""Job freshness classification.

Freshness is computed ONLY from source-provided timestamps. When a source exposes a real
posting date (``posted_at``) it is *verified*; otherwise an ``updated_at``/discovered time
is used but never presented as a verified posting time.
"""

from __future__ import annotations

import enum
from datetime import datetime, timedelta


class Freshness(str, enum.Enum):
    LAST_HOUR = "LAST_HOUR"
    LAST_24_HOURS = "LAST_24_HOURS"
    LAST_3_DAYS = "LAST_3_DAYS"
    LAST_7_DAYS = "LAST_7_DAYS"
    OLDER = "OLDER"
    UNKNOWN = "UNKNOWN"


def classify_freshness(
    posted_at: datetime | None,
    updated_at: datetime | None = None,
    discovered_at: datetime | None = None,
    now: datetime | None = None,
) -> tuple[Freshness, bool]:
    """Return (freshness, posting_verified).

    posting_verified is True only when the classification used a real posted_at value.
    """
    now = now or datetime.utcnow()
    stamp = posted_at
    if stamp is not None:
        posting_verified = True
    else:
        stamp = updated_at or discovered_at
        posting_verified = False
    if stamp is None:
        return Freshness.UNKNOWN, False
    delta = now - stamp
    if delta <= timedelta(hours=1):
        freshness = Freshness.LAST_HOUR
    elif delta <= timedelta(hours=24):
        freshness = Freshness.LAST_24_HOURS
    elif delta <= timedelta(days=3):
        freshness = Freshness.LAST_3_DAYS
    elif delta <= timedelta(days=7):
        freshness = Freshness.LAST_7_DAYS
    else:
        freshness = Freshness.OLDER
    return freshness, posting_verified


def within_time_range(time_range: str, freshness: Freshness, posting_verified: bool) -> bool:
    """Return True when a job passes the requested time-range filter.

    The "Last 1 hour" filter uses postedAt when available; jobs without a verified posting
    time are excluded from strict time filters (they surface under "any").
    """
    if not time_range or time_range in ("any", "all"):
        return True
    if not posting_verified and time_range in ("1h", "24h", "3d", "7d"):
        return False
    cutoff_hours = {"1h": 1, "24h": 24, "3d": 72, "7d": 168}.get(time_range)
    if cutoff_hours is None:
        return True
    return freshness in {
        Freshness.LAST_HOUR,
        Freshness.LAST_24_HOURS,
        Freshness.LAST_3_DAYS,
        Freshness.LAST_7_DAYS,
    } and {
        Freshness.LAST_HOUR: 1,
        Freshness.LAST_24_HOURS: 24,
        Freshness.LAST_3_DAYS: 72,
        Freshness.LAST_7_DAYS: 168,
    }[freshness] <= cutoff_hours
