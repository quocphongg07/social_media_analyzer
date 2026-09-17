import csv
import io
import json
import math
from datetime import datetime, timezone

FIELDS = ['rank', 'post_type', 'author_name', 'author_id', 'content', 'shared_content', 'shared_author',
          'reactions', 'comments', 'shares', 'engagement_score', 'score_status', 'missing_metrics',
          'created_time', 'post_url', 'shared_post_url', 'post_id', 'collected_at']


def rank_posts(posts, reaction_weight=1.0, comment_weight=2.0, share_weight=3.0):
    weights = dict(reactions=reaction_weight, comments=comment_weight, shares=share_weight)
    if any(not math.isfinite(w) or w < 0 for w in weights.values()):
        raise ValueError('Trọng số phải là số hữu hạn không âm.')
    known, unknown = [], []
    for item in posts:
        row = dict(item)
        missing = [k for k, w in weights.items() if w > 0 and row.get(k) is None]
        row['missing_metrics'] = ', '.join(k for k in weights if row.get(k) is None)
        if all(w == 0 for w in weights.values()) or any(row.get(k) is not None and w > 0 for k, w in weights.items()):
            row['engagement_score'] = sum((row.get(k) or 0) * w for k, w in weights.items())
            row['score_status'] = 'partial' if missing else 'complete'
            known.append(row)
        else:
            row.update(engagement_score=None, rank=None, score_status='unavailable')
            unknown.append(row)
    known.sort(key=lambda p: (-p['engagement_score'], p['post_id']))
    for index, row in enumerate(known, 1):
        row['rank'] = index
    return known + unknown


def save_run(result):
    from database.database import get_connection
    db = get_connection()
    try:
        with db:
            db.execute('''CREATE TABLE IF NOT EXISTS facebook_profile_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, profile_key TEXT NOT NULL,
                collected_at TEXT NOT NULL, payload TEXT NOT NULL)''')
            db.execute('INSERT INTO facebook_profile_runs (profile_key, collected_at, payload) VALUES (?, ?, ?)',
                (result['profile']['key'], datetime.now(timezone.utc).isoformat(), json.dumps(result, ensure_ascii=False)))
    finally:
        db.close()


def safe(value):
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def to_csv(rows):
    s = io.StringIO(newline='')
    w = csv.DictWriter(s, fieldnames=FIELDS)
    w.writeheader()
    for row in rows:
        w.writerow({key: safe(row.get(key)) for key in FIELDS})
    return s.getvalue().encode('utf-8-sig')


def to_excel(rows):
    from openpyxl import Workbook
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = 'Facebook Profile'
    ws.append(FIELDS)
    for row in rows:
        values = [safe(row.get(key)) for key in FIELDS]
        ws.append([ILLEGAL_CHARACTERS_RE.sub('', v) if isinstance(v, str) else v for v in values])
    for c in ws[1]:
        c.font = Font(bold=True)
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 23
    ws.column_dimensions['E'].width = 65
    ws.column_dimensions['F'].width = 65
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_json(rows, metadata):
    return json.dumps({'metadata': metadata, 'posts': rows}, ensure_ascii=False, indent=2).encode('utf-8')