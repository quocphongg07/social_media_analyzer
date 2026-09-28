from .common import json_bytes

def data_to_json(data):
    return json_bytes(data)

def analysis_to_json(posts, comments):
    return json_bytes(dict(posts=posts, comments=comments, timezone="Asia/Ho_Chi_Minh"))
