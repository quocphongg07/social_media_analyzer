from __future__ import annotations

import math
from datetime import datetime
from .parser import METRICS


def rank_posts(posts, weights, start=None, end=None, keyword='', include_incomplete=True):
    if start and end and start > end:
        raise ValueError('Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.')
    if any(not math.isfinite(float(weights.get(k, 0))) or float(weights.get(k, 0)) < 0 for k in METRICS):
        raise ValueError('Trọng số phải là số hữu hạn không âm.')
    rows = []
    for post in posts:
        p = dict(post)
        try:
            day = datetime.fromisoformat(p['created_time'].replace('Z', '+00:00')).date()
        except (KeyError, ValueError, TypeError):
            day = None
        if (start or end) and day is None:
            continue
        if start and day < start or end and day > end:
            continue
        if keyword.casefold() not in str(p.get('content', '')).casefold():
            continue
        missing = [k for k in METRICS if p.get(k) is None and weights.get(k, 0) > 0]
        if missing and not include_incomplete:
            continue
        p['missing_metrics'] = ', '.join(k for k in METRICS if p.get(k) is None)
        p['score_status'] = 'partial' if missing else 'complete'
        p['engagement_score'] = sum((p.get(k) or 0) * weights.get(k, 0) for k in METRICS)
        rows.append(p)
    rows.sort(key=lambda p: (-p['engagement_score'], p['post_id']))
    for i, row in enumerate(rows, 1):
        row['rank'] = i
    return rows