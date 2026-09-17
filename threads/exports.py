import csv
import io
import json

COLUMNS = ['rank', 'post_id', 'author_name', 'content', 'created_time', 'likes', 'comments',
           'reposts', 'quotes', 'shares', 'engagement_score', 'score_status', 'missing_metrics',
           'post_url', 'collected_at']


def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def to_csv(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=COLUMNS, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: safe_cell(row.get(k)) for k in COLUMNS})
    return stream.getvalue().encode('utf-8-sig')


def to_excel(rows):
    from openpyxl import Workbook
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = 'Threads'
    ws.append(COLUMNS)
    for row in rows:
        values = []
        for key in COLUMNS:
            value = safe_cell(row.get(key))
            values.append(ILLEGAL_CHARACTERS_RE.sub('', value) if isinstance(value, str) else value)
        ws.append(values)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 22
    ws.column_dimensions['D'].width = 70
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_json(rows, metadata):
    return json.dumps({'metadata': metadata, 'posts': rows}, ensure_ascii=False, indent=2).encode('utf-8')