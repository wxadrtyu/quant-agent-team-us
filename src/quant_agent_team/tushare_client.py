"""Tushare Pro client via low-cost proxy (15000-point plan).

The cheap plan routes the official ``tushare`` SDK through a third-party proxy by
overriding ``pro._DataApi__http_url``. Token is read from the gitignored
``.tushare_token`` file (or ``TUSHARE_TOKEN`` env). Per the plan's config doc:

  - rate limit: 100 calls/min, total volume unlimited  -> we throttle to <=~85/min.
  - "fetch as much as possible per call" (batch by trade_date / wide date range),
    never loop per-stock-per-day.
  - any TUSHARE token *env var* must NOT shadow the proxy setting, so we pass the
    token explicitly to ``set_token`` and always re-assert the proxy URL.

Source tag for everything pulled here is ``"tushare"`` (see multi-source data
discipline: tag source, never blend within a factor).
"""
from __future__ import annotations

import os
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_TOKEN_FILE = _ROOT / ".tushare_token"
PROXY_HTTP_URL = os.environ.get("TUSHARE_HTTP_URL", "https://fastapic.stockai888.top")
SOURCE_TAG = "tushare"

# 100/min hard cap on the shared proxy -> 0.7s spacing keeps us ~85/min with margin.
_MIN_INTERVAL = float(os.environ.get("TUSHARE_MIN_INTERVAL", "0.7"))
_last_call = [0.0]


def _read_token() -> str:
    tok = os.environ.get("TUSHARE_TOKEN", "").strip()
    if tok:
        return tok
    if _TOKEN_FILE.exists():
        return _TOKEN_FILE.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        f"No Tushare token: set TUSHARE_TOKEN or create {_TOKEN_FILE}"
    )


def get_pro():
    """Return a proxy-configured Tushare ``pro`` api handle."""
    import tushare as ts

    ts.set_token(_read_token())
    pro = ts.pro_api()
    # Route through the cheap-plan proxy. Must be re-asserted after pro_api().
    pro._DataApi__http_url = PROXY_HTTP_URL  # noqa: SLF001 (documented proxy hook)
    return pro


def throttle() -> None:
    """Sleep so consecutive calls respect the proxy's 100/min cap."""
    dt = time.monotonic() - _last_call[0]
    if dt < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - dt)
    _last_call[0] = time.monotonic()


def call(fn, *args, retries: int = 4, backoff: float = 2.0, **kwargs):
    """Throttled, retrying wrapper around a ``pro.<endpoint>`` call.

    Retries transient proxy/network errors with exponential backoff. Raises the
    last exception if all attempts fail.
    """
    last = None
    for attempt in range(retries):
        throttle()
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - surface after retries
            last = exc
            time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"tushare call failed after {retries} retries: {last!r}")


def ts_to_stock_code(ts_code: str) -> str:
    """'000001.SZ' -> '000001' to match market_daily.stock_code (6-digit)."""
    return ts_code.split(".")[0]
