import sqlite3
from pathlib import Path

from config.settings import settings


def get_connection() -> sqlite3.Connection:
    """
    Tạo kết nối SQLite.
    """

    db_path = Path(settings.DATABASE_PATH)

    # Tạo thư mục data nếu chưa tồn tại
    db_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        db_path,
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database() -> None:
    """
    Khởi tạo toàn bộ database và các bảng cần thiết.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS groups (
            group_id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL DEFAULT '',
            last_scanned TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            post_id TEXT PRIMARY KEY,
            group_id TEXT NOT NULL,
            post_url TEXT NOT NULL DEFAULT '',
            author_name TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            created_time TEXT NOT NULL DEFAULT '',

            likes INTEGER NOT NULL DEFAULT 0,
            comments INTEGER NOT NULL DEFAULT 0,
            shares INTEGER NOT NULL DEFAULT 0,

            engagement_score REAL NOT NULL DEFAULT 0,
            rank INTEGER NOT NULL DEFAULT 0,

            collected_at TEXT NOT NULL,

            FOREIGN KEY (group_id)
                REFERENCES groups(group_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS comments (
            comment_id TEXT PRIMARY KEY,
            post_id TEXT NOT NULL,
            comment_url TEXT NOT NULL DEFAULT '',
            author_name TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            created_time TEXT NOT NULL DEFAULT '',

            reactions INTEGER NOT NULL DEFAULT 0,
            replies INTEGER NOT NULL DEFAULT 0,

            engagement_score REAL NOT NULL DEFAULT 0,
            rank INTEGER NOT NULL DEFAULT 0,

            collected_at TEXT NOT NULL,

            FOREIGN KEY (post_id)
                REFERENCES posts(post_id)
        )
        """
    )

    # Index giúp truy vấn nhanh hơn
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_posts_group_id
        ON posts(group_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_comments_post_id
        ON comments(post_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_posts_score
        ON posts(engagement_score DESC)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_comments_score
        ON comments(engagement_score DESC)
        """
    )

    connection.commit()
    connection.close()