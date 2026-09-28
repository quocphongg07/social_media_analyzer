from .common import csv_bytes, POST_FIELDS, COMMENT_FIELDS

def posts_to_csv(posts):
    return csv_bytes(posts, POST_FIELDS)

def comments_to_csv(comments):
    return csv_bytes(comments, COMMENT_FIELDS)
