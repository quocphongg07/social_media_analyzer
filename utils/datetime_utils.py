from datetime import timedelta, timezone
import math
import re
import pandas as pd

VIETNAM = timezone(timedelta(hours=7))


def vietnam_datetime(value):
    """Convert UTC epochs (s/ms/us/ns), ISO strings or datetimes to Vietnam wall time.

    Return datetime values, not formatted strings, so column sorting stays chronological.
    Naive input dates are interpreted as UTC; blank/invalid/zero timestamps stay blank.
    """
    if value is None or isinstance(value, bool):
        return pd.NaT
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return pd.NaT
        if re.fullmatch(r'\d{2}/\d{2}/\d{4}(?: \d{2}:\d{2}:\d{2})?', value):
            return pd.to_datetime(value, dayfirst=True, errors='coerce')
        if re.fullmatch(r'[+-]?\d+(?:\.\d+)?', value):
            value = float(value) if '.' in value else int(value)
    try:
        if isinstance(value, (int, float)):
            if not math.isfinite(value) or value == 0:
                return pd.NaT
            size = abs(value)
            unit = 'ns' if size >= 10**17 else 'us' if size >= 10**14 else 'ms' if size >= 10**11 else 's'
            parsed = pd.to_datetime(value, unit=unit, utc=True, errors='coerce')
        else:
            parsed = pd.to_datetime(value, utc=True, errors='coerce')
        if pd.isna(parsed):
            return pd.NaT
        # Strip timezone only after converting, preventing browser timezone changes.
        return parsed.tz_convert(VIETNAM).tz_localize(None)
    except (ValueError, TypeError, OverflowError):
        return pd.NaT


DATE_FIELDS = {'created_time', 'collected_at', 'updated_time', 'timestamp', 'Created Time', 'Collected At'}

def format_vietnam(value):
    date = vietnam_datetime(value)
    return '' if pd.isna(date) else date.strftime('%d/%m/%Y %H:%M:%S')

def localize_json(value):
    if isinstance(value, dict):
        return {k: (format_vietnam(v) or None) if k in DATE_FIELDS else localize_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [localize_json(v) for v in value]
    return value