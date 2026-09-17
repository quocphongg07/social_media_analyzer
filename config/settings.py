import os

from dotenv import load_dotenv


load_dotenv()


class Settings:

    APP_NAME = os.getenv(
        "APP_NAME",
        "Facebook Engagement Analyzer",
    )

    DATABASE_PATH = os.getenv(
        "DATABASE_PATH",
        "data/facebook.db",
    )

    LIKE_WEIGHT = float(
        os.getenv(
            "LIKE_WEIGHT",
            "1",
        )
    )

    COMMENT_WEIGHT = float(
        os.getenv(
            "COMMENT_WEIGHT",
            "2",
        )
    )

    SHARE_WEIGHT = float(
        os.getenv(
            "SHARE_WEIGHT",
            "3",
        )
    )

    REACTION_WEIGHT = float(
        os.getenv(
            "REACTION_WEIGHT",
            "1",
        )
    )

    REPLY_WEIGHT = float(
        os.getenv(
            "REPLY_WEIGHT",
            "2",
        )
    )

    LOG_LEVEL = os.getenv(
        "LOG_LEVEL",
        "INFO",
    )

    # ========================================================
    # FACEBOOK API
    # ========================================================

    FACEBOOK_ACCESS_TOKEN = os.getenv(
        "FACEBOOK_ACCESS_TOKEN",
        "",
    )

    FACEBOOK_GRAPH_API_VERSION = os.getenv(
        "FACEBOOK_GRAPH_API_VERSION",
        "v23.0",
    )

    FACEBOOK_API_BASE_URL = os.getenv(
        "FACEBOOK_API_BASE_URL",
        "https://graph.facebook.com",
    )


settings = Settings()