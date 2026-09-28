"""Parse profile timeline stories without mixing a shared original's metrics."""
from __future__ import annotations
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

HOSTS = {'facebook.com', 'www.facebook.com', 'm.facebook.com', 'web.facebook.com'}
EMBEDDED = {'attached_story', 'shared_story', 'quoted_story', 'attachments'}


def parse_profile(value):
    value = value.strip()
    if not value.startswith(('http://', 'https://')):
        raise ValueError('Hãy nhập link Facebook đầy đủ, ví dụ https://www.facebook.com/username.')
    u = urlparse(value)
    if u.hostname not in HOSTS or u.username or u.password or u.port:
        raise ValueError('Link phải thuộc facebook.com.')
    parts = [p for p in u.path.split('/') if p]
    if parts == ['profile.php']:
        ids = parse_qs(u.query).get('id', [])
        if len(ids) != 1 or not ids[0].isdigit():
            raise ValueError('Link profile.php phải có một id dạng số.')
        key = ids[0]
    elif len(parts) == 3 and parts[0] == 'people' and parts[2].isdigit():
        key = parts[2]
    elif len(parts) == 1 and re.fullmatch(r'[A-Za-z0-9.]+', parts[0]):
        key = parts[0].lower()
        if key in {'groups', 'watch', 'reel', 'reels', 'share', 'login', 'login.php', 'home.php', 'story.php', 'permalink.php', 'photo.php', 'photos', 'pages', 'marketplace', 'events', 'settings', 'help'}:
            raise ValueError('Cần link tài khoản, không phải nhóm, bài viết hoặc link chia sẻ rút gọn.')
    else:
        raise ValueError('Link tài khoản cần dạng /username, /profile.php?id=... hoặc /people/tên/id.')
    url = f'https://www.facebook.com/profile.php?id={key}' if key.isdigit() else f'https://www.facebook.com/{key}'
    return {'key': key, 'url': url}


def objects(value, skip=()):
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            yield item
            stack.extend(v for k, v in reversed(list(item.items())) if k not in skip and isinstance(v, (dict, list)))
        elif isinstance(item, list):
            stack.extend(reversed(item))


def own_objects(story):
    ident = str(story.get('post_id', ''))
    stack = [story]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if item is not story and item.get('post_id') and str(item['post_id']) != ident:
                continue
            yield item
            stack.extend(v for k, v in reversed(list(item.items()))
                         if k not in EMBEDDED | {'feedback', 'comments', 'replies'} and isinstance(v, (dict, list)))
        elif isinstance(item, list):
            stack.extend(reversed(item))


def actor_of(story):
    for obj in own_objects(story):
        actors = obj.get('actors')
        if isinstance(actors, list) and actors and isinstance(actors[0], dict):
            return actors[0]
        for key in ('actor', 'author', 'owner'):
            if isinstance(obj.get(key), dict) and obj[key].get('id'):
                return obj[key]
    feedback = story.get('feedback') or {}
    if isinstance(feedback, dict) and isinstance(feedback.get('owning_profile'), dict):
        return feedback['owning_profile']
    return {}


def content_of(story):
    for obj in own_objects(story):
        for key in ('message', 'preferred_body', 'body'):
            value = obj.get(key)
            if isinstance(value, dict):
                value = value.get('text')
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ''


def exact(value):
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r'\d+', value):
        return int(value)
    return None


def metric(feedback, *paths):
    for path in paths:
        value = feedback
        for key in path.split('.'):
            value = value.get(key) if isinstance(value, dict) else None
        value = exact(value)
        if value is not None:
            return value
    return None


def merge(old, new):
    result = dict(old or {})
    for key, value in new.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        elif value is not None and value != '' and value != []:
            result[key] = value
    return result


def decode(text):
    text = text.strip()
    if text.startswith('for (;;);'):
        text = text[9:].lstrip()
    try:
        return [json.loads(text)]
    except (ValueError, RecursionError):
        result = []
        for line in text.splitlines():
            try:
                result.append(json.loads(line))
            except (ValueError, RecursionError):
                pass
        return result


def post_link(value):
    if not isinstance(value, str):
        return ''
    u = urlparse(value)
    if u.scheme not in {'http', 'https'} or u.hostname not in HOSTS or u.username or u.password:
        return ''
    if '/groups/' in u.path:
        return ''
    if re.search(r'/(?:posts|videos)/(?:\d+|pfbid[A-Za-z0-9]+)', u.path) or u.path in {'/permalink.php', '/story.php', '/photo.php'}:
        return value
    return ''


class ProfileParser:
    def __init__(self, target):
        self.target = target
        self.ids = {target['key']} if target['key'].isdigit() else set()
        self.stories, self.feedbacks = {}, {}
        self.entities = {}

    def ingest_response(self, payloads):
        """Apply deferred GraphQL paths within ONE response, then parse the result.

        Later timeline cards may arrive as a Story shell followed by header/body
        fragments. Parsing each fragment alone loses both author and post ID.
        Never reuse a path tree for a different network request.
        """
        tree = None
        pending = []

        def apply_patch(patch):
            nonlocal tree
            path = list(patch.get('path') or [])
            if path and path[0] == 'data':
                path = path[1:]
            if tree is None:
                return False
            current = tree
            try:
                for part in path[:-1]:
                    current = current[part]
                if 'items' in patch:
                    items = deepcopy(patch['items'])
                    if path and isinstance(path[-1], int):
                        if not isinstance(current, list) or path[-1] > len(current):
                            return False
                        for offset, item in enumerate(items):
                            index = path[-1] + offset
                            if index == len(current):
                                current.append(item)
                            else:
                                current[index] = merge(current[index], item) if isinstance(item, dict) else item
                    else:
                        dest = current[path[-1]] if path else current
                        dest.extend(items)
                else:
                    value = deepcopy(patch.get('data'))
                    if not path:
                        tree = merge(tree, value) if isinstance(tree, dict) and isinstance(value, dict) else value
                    else:
                        part = path[-1]
                        if isinstance(current, list) and part == len(current):
                            current.append(value)
                        else:
                            old = current.get(part) if isinstance(current, dict) else current[part]
                            current[part] = merge(old, value) if isinstance(old, dict) and isinstance(value, dict) else value
                return True
            except (KeyError, IndexError, TypeError, AttributeError):
                return False

        for payload in payloads:
            self.ingest(payload)
            if not isinstance(payload, dict):
                continue
            if 'path' in payload:
                pending.append(payload)
            elif isinstance(payload.get('data'), (dict, list)):
                tree = deepcopy(payload['data'])
            pending.extend(p for p in payload.get('incremental', []) if isinstance(p, dict))
            # Dependencies may arrive out of order in the same response.
            while pending:
                remaining = [patch for patch in pending if not apply_patch(patch)]
                if len(remaining) == len(pending):
                    break
                pending = remaining
            if tree is not None:
                self.ingest(tree)

    def matches(self, actor):
        if str(actor.get('id', '')) in self.ids:
            return True
        matched = str(actor.get('username', '')).lower() == self.target['key']
        try:
            matched = matched or parse_profile(actor.get('url', ''))['key'] == self.target['key']
        except (ValueError, AttributeError):
            pass
        if matched and str(actor.get('id', '')).isdigit():
            self.ids.add(str(actor['id']))
        return matched

    def ingest(self, payload):
        # Identity can arrive after story fragments, so retain then resolve.
        for obj in objects(payload, EMBEDDED):
            if obj.get('__typename') in {'User', 'Profile', 'Page'} and self.matches(obj):
                ident = str(obj.get('id', ''))
                if ident.isdigit():
                    self.ids.add(ident)
            entity_id = str(obj.get('id') or '')
            if (obj.get('__typename') == 'Story' or entity_id in self.entities) and entity_id:
                self.entities[entity_id] = merge(self.entities.get(entity_id), obj)
                obj = self.entities[entity_id]
            if obj.get('__typename') == 'Story':
                ident = str(obj.get('post_id') or '')
                if not ident:
                    # A permalink is evidence of a post ID; a Relay Story ID is not.
                    link = post_link(obj.get('url')) or post_link(obj.get('permalink_url'))
                    parsed = urlparse(link)
                    match = re.search(r'/(?:posts|videos)/(\d+|pfbid[A-Za-z0-9]+)', parsed.path)
                    ident = match.group(1) if match else parse_qs(parsed.query).get('story_fbid', [''])[0]
                if re.fullmatch(r'[A-Za-z0-9_-]+', ident):
                    self.stories[ident] = merge(self.stories.get(ident), dict(obj, post_id=ident))
            fb = obj.get('feedback')
            if isinstance(fb, dict) and fb.get('id'):
                ident = str(fb['id'])
                self.feedbacks[ident] = merge(self.feedbacks.get(ident), fb)
            if obj.get('__typename') == 'Feedback' and obj.get('id'):
                ident = str(obj['id'])
                self.feedbacks[ident] = merge(self.feedbacks.get(ident), obj)

    def posts(self):
        result = []
        # Resolve identity before filtering: later cards often carry only actor.id.
        for story in self.stories.values():
            self.matches(actor_of(story))
        for ident, story in self.stories.items():
            actor = actor_of(story)
            if not self.matches(actor):
                continue
            if '/groups/' in str(story.get('url', '')):
                continue
            feedback = {}
            for obj in own_objects(story):
                fb = obj.get('feedback')
                if isinstance(fb, dict) and fb:
                    feedback = merge(fb, self.feedbacks.get(str(fb.get('id', '')), {}))
                    break
            if feedback.get('associated_group'):
                continue
            shared = None
            for obj in own_objects(story):
                for key in ('attached_story', 'shared_story'):
                    if isinstance(obj.get(key), dict):
                        shared = obj[key]
                        break
                if shared is not None:
                    break
            if shared is None:
                for obj in own_objects(story):
                    for attached in objects(obj.get('attachments', [])):
                        if attached.get('__typename') == 'Story' and attached.get('post_id'):
                            shared = attached
                            break
                    if shared is not None:
                        break
            is_share = shared is not None or story.get('is_reshare') is True or story.get('is_share') is True
            url = post_link(story.get('url')) or post_link(story.get('permalink_url')) or post_link(feedback.get('url'))
            if not url:
                url = f'https://www.facebook.com/{actor.get("id") or self.target["key"]}/posts/{ident}'
            timestamp = story.get('creation_time', story.get('created_time'))
            if timestamp is None:
                for obj in own_objects(story):
                    if obj.get('creation_time') is not None:
                        timestamp = obj['creation_time']
                        break
            try:
                created = datetime.fromtimestamp(float(timestamp), timezone.utc).isoformat()
            except (TypeError, ValueError, OSError, OverflowError):
                created = ''
            original = shared or {}
            result.append(dict(post_id=ident, profile_key=self.target['key'], post_url=url,
                author_name=actor.get('name') or self.target['key'], author_id=str(actor.get('id', '')),
                post_type='Bài chia sẻ' if is_share else 'Bài đăng', content=content_of(story),
                shared_content=content_of(original), shared_author=actor_of(original).get('name', ''),
                shared_post_url=post_link(original.get('url')) or post_link(original.get('permalink_url')),
                created_time=created,
                reactions=metric(feedback, 'reaction_count.count', 'reaction_count', 'reactors.count', 'reactions.count', 'reactions.total_count'),
                comments=metric(feedback, 'total_comment_count', 'comments.total_count', 'comment_rendering_instance.comments.total_count', 'comments.count'),
                shares=metric(feedback, 'share_count.count', 'share_count'),
                collected_at=datetime.now(timezone.utc).isoformat(), source='facebook_profile_browser'))
        return result