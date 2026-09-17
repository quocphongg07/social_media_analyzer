import json
from datetime import datetime, timezone
from database.database import get_connection


def save_run(result):
    connection = get_connection()
    try:
        with connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS threads_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL,
                collected_at TEXT NOT NULL, payload TEXT NOT NULL)''')
            cursor = connection.execute('INSERT INTO threads_runs (username, collected_at, payload) VALUES (?, ?, ?)',
                (result['username'], datetime.now(timezone.utc).isoformat(), json.dumps(result, ensure_ascii=False)))
            return cursor.lastrowid
    finally:
        connection.close()


def latest_run(username):
    connection = get_connection()
    try:
        exists = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='threads_runs'").fetchone()
        if not exists:
            return None
        row = connection.execute('SELECT payload FROM threads_runs WHERE username=? ORDER BY id DESC LIMIT 1', (username,)).fetchone()
        return json.loads(row['payload']) if row else None
    finally:
        connection.close()
