"""Helpers for browser-delivered feeds; never replay private API requests."""
import json
import re


def decode_feed(text):
    """JSON, anti-XSSI JSON, NDJSON and multipart JSON response bodies."""
    text = text.strip()
    if text.startswith('for (;;);'):
        text = text[9:].lstrip()
    try:
        return [json.loads(text)]
    except (ValueError, RecursionError):
        pass
    # Multipart framing has a blank line between headers and each JSON body.
    result = []
    for part in re.split(r'\r?\n--[^\r\n]+\r?\n', text):
        if '\n\n' in part.replace('\r\n', '\n'):
            header, body = part.replace('\r\n', '\n').split('\n\n', 1)
            if 'content-type:' in header.lower():
                part = body
        candidate = re.sub(r'\r?\n--[^\r\n]+--\s*$', '', part).strip()
        try:
            value = json.loads(candidate)
        except (ValueError, RecursionError):
            pass
        else:
            if isinstance(value, (dict, list)):
                result.append(value)
            continue
        for line in part.splitlines():
            line = line.strip().removeprefix('for (;;);').strip()
            try:
                value = json.loads(line)
            except (ValueError, RecursionError):
                continue
            if isinstance(value, (dict, list)):
                result.append(value)
    return result


def is_feed_response(response):
    if response.request.resource_type not in {'xhr', 'fetch'}:
        return False
    content_type = response.headers.get('content-type', '').lower()
    return (any(kind in content_type for kind in ('json', 'javascript', 'multipart/mixed'))
            or '/graphql' in response.url or '/api/v1/' in response.url)


class FeedProgress:
    """No-data counter also watches actual movement through a virtualized feed."""
    def __init__(self, patience=12):
        self.patience = patience
        self.last = None
        self.idle = 0

    def stalled(self, count, position):
        state = (count, position)
        self.idle = self.idle + 1 if state == self.last else 0
        self.last = state
        return self.idle >= self.patience


def advance_feed(page, selector):
    """Scroll the feed's last rendered post and its overflow ancestor, not a fixed point.

    Return scroll coordinates and the last post URL for virtualized feeds whose
    scrollHeight stays constant. Moving through already-loaded cards is progress.
    """
    return page.evaluate('''selector => {
        const visible = el => el.getClientRects().length &&
            getComputedStyle(el).visibility !== 'hidden';
        const links = [...document.querySelectorAll(selector)].filter(visible);
        const last = links[links.length - 1];
        let scroller = document.scrollingElement;
        if (last) {
            for (let el = last.parentElement; el; el = el.parentElement) {
                const style = getComputedStyle(el);
                if (/(auto|scroll)/.test(style.overflowY) &&
                    el.scrollHeight > el.clientHeight + 2) {
                    scroller = el; break;
                }
            }
            const before = scroller ? scroller.scrollTop : 0;
            const card = last.closest('[role="article"], article') || last;
            card.scrollIntoView({block: 'end', behavior: 'instant'});
            // Do not jump backwards to an unchanged timestamp on a tall card.
            if (scroller && scroller.scrollTop < before) scroller.scrollTop = before;
        }
        if (!scroller) return ['no_scroll_container'];
        scroller.scrollBy({top: Math.max(500, scroller.clientHeight * 0.85),
                           behavior: 'instant'});
        return [Math.round(scroller.scrollTop), scroller.scrollHeight,
                last ? last.getAttribute('href') : '', links.length];
    }''', selector)
