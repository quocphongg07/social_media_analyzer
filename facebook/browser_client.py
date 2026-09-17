"""Đây là bản đã lấy được danh sách bài, đếm được comment
    nhưng chưa có xếp hạng bài viết, comment chưa lấy được hết"""

from __future__ import annotations

import html
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .client import FacebookClient


class FacebookBrowserClient(FacebookClient):
    """
    Facebook collector sử dụng Chrome + persistent profile.

    Lưu ý:
    - Đăng nhập Facebook được thực hiện thủ công.
    - Không tự động nhập username/password.
    - Structured GraphQL data là nguồn chính.
    - DOM chỉ được sử dụng làm fallback.
    """

    CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    DEFAULT_PROFILE_DIR = (
        str(Path(__file__).resolve().parents[1] / "data" / "facebook_group_account_2")
    )

    DEFAULT_WAIT_MS = 2500

    # Ghi nhớ Group ID cuối cùng đã xác định thành công.
    # Điều này giúp tab phân tích bình luận hoạt động ngay cả khi
    # Streamlit tạo FacebookBrowserClient mới trong một lần rerun.
    _global_last_group_id: str = ""

    def __init__(
        self,
        executable_path: str | None = None,
        user_data_dir: str | None = None,
        headless: bool = False,
        slow_mo: int = 50,
        debug_dir: str = "logs/facebook_debug",
    ):
        self.executable_path = executable_path or self.CHROME_PATH
        self.user_data_dir = Path(
            user_data_dir or self.DEFAULT_PROFILE_DIR
        )

        self.headless = headless
        self.slow_mo = slow_mo

        # Luôn ghi debug theo thư mục project, không phụ thuộc CWD.
        if debug_dir == "logs/facebook_debug":
            project_root = Path(__file__).resolve().parents[1]
            self.debug_dir = project_root / "logs" / "facebook_debug"
        else:
            self.debug_dir = Path(debug_dir).expanduser().resolve()
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Debug] Debug directory: {self.debug_dir}")

        self._playwright = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    # ============================================================
    # PLAYWRIGHT
    # ============================================================

    def _ensure_browser(self) -> Page:
        if self._page is not None:
            return self._page

        self.user_data_dir.mkdir(parents=True, exist_ok=True)

        self._playwright = sync_playwright().start()

        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            executable_path=self.executable_path,
            headless=self.headless,
            slow_mo=self.slow_mo,
            viewport={"width": 1440, "height": 1000},
            locale="vi-VN",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-notifications",
            ],
        )

        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = self._context.new_page()

        self._page.set_default_timeout(15000)

        return self._page

    def close(self):
        try:
            if self._context is not None:
                self._context.close()
        except Exception:
            pass

        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass

        self._page = None
        self._context = None
        self._playwright = None

    # ============================================================
    # TEXT / JSON UTILITIES
    # ============================================================

    @staticmethod
    def _clean_text(value: Any) -> str:
        """
        Làm sạch text Unicode, đặc biệt tránh lỗi lone surrogate
        khi ghi HTML / print ra console.
        """
        if value is None:
            return ""

        if not isinstance(value, str):
            value = str(value)

        value = value.replace("\x00", " ")

        try:
            value = value.encode(
                "utf-16",
                "surrogatepass",
            ).decode(
                "utf-16",
                "replace",
            )
        except Exception:
            value = value.encode(
                "utf-8",
                "replace",
            ).decode(
                "utf-8",
                "replace",
            )

        value = re.sub(r"\s+", " ", value).strip()

        return value

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        if value is None:
            return default

        if isinstance(value, bool):
            return int(value)

        if isinstance(value, int):
            return value

        if isinstance(value, float):
            return int(value)

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return default

            # 1,234 / 1.234 / "43"
            cleaned = re.sub(r"[^\d-]", "", value)

            if not cleaned:
                return default

            try:
                return int(cleaned)
            except Exception:
                return default

        return default

    @staticmethod
    def _deep_get(obj: Any, *paths: str) -> Any:
        """
        Lấy value từ nhiều path dạng:
        feedback.reactors.count_reduced
        feedback.replies_fields.total_count
        """
        for path in paths:
            current = obj

            try:
                for key in path.split("."):
                    if not isinstance(current, dict):
                        raise KeyError

                    current = current.get(key)

                if current is not None:
                    return current

            except Exception:
                continue

        return None

    @staticmethod
    def _extract_text(obj: Any) -> str:
        if not isinstance(obj, dict):
            return ""

        for key in (
            "text",
            "message",
            "body",
            "preferred_body",
        ):
            value = obj.get(key)

            if isinstance(value, str):
                text = FacebookBrowserClient._clean_text(value)

                if text:
                    return text

            if isinstance(value, dict):
                text = FacebookBrowserClient._extract_text(value)

                if text:
                    return text

        return ""

    @staticmethod
    def _extract_balanced_object(
        source: str,
        start: int,
    ) -> dict[str, Any] | None:
        """
        Parse JSON object bằng cách đếm brace, có xử lý string + escape.

        start phải trỏ vào ký tự '{'.
        """
        if start < 0 or start >= len(source):
            return None

        if source[start] != "{":
            return None

        depth = 0
        in_string = False
        escaped = False

        for i in range(start, len(source)):
            char = source[i]

            if in_string:
                if escaped:
                    escaped = False

                elif char == "\\":
                    escaped = True

                elif char == '"':
                    in_string = False

                continue

            if char == '"':
                in_string = True

            elif char == "{":
                depth += 1

            elif char == "}":
                depth -= 1

                if depth == 0:
                    raw = source[start : i + 1]

                    try:
                        return json.loads(raw)
                    except Exception:
                        return None

        return None

    @staticmethod
    def _find_nearest_json_object(
        source: str,
        marker_pos: int,
        candidates: tuple[str, ...],
    ) -> dict[str, Any] | None:
        """
        Tìm object JSON gần marker nhất.

        Ví dụ với comment:
            {"node":{"id":... "legacy_fbid":"217..." ...}}
        """
        best_pos = -1

        for candidate in candidates:
            pos = source.rfind(candidate, 0, marker_pos)

            if pos > best_pos:
                best_pos = pos

        if best_pos < 0:
            return None

        brace = source.find("{", best_pos)

        if brace < 0:
            return None

        return FacebookBrowserClient._extract_balanced_object(
            source,
            brace,
        )

    @staticmethod
    def _decode_possible_html_json(source: str) -> str:
        """
        HTML có thể chứa escaped JSON.

        Không cố decode toàn bộ bằng json.loads vì HTML của Facebook
        không phải một JSON document duy nhất.
        """
        result = html.unescape(source)

        # KHÔNG thay \" thành \" trên toàn HTML.
        # Dấu \" bên trong JSON string là escape hợp lệ; thay toàn cục
        # sẽ làm hỏng JSON và khiến balanced-object parser thất bại.
        return result

    # ============================================================
    # URL
    # ============================================================

    @staticmethod
    def _normalize_group_url(group: str) -> str:
        group = str(group).strip()

        if not group:
            return ""

        if group.startswith("http://") or group.startswith("https://"):
            url = group

        else:
            if group.isdigit():
                return (
                    f"https://www.facebook.com/groups/"
                    f"{group}/"
                )

            return (
                f"https://www.facebook.com/groups/"
                f"{group}/"
            )

        return url.split("?")[0].rstrip("/") + "/"

    @staticmethod
    def _extract_group_id(group: str) -> str:
        group = str(group).strip()

        if group.isdigit():
            return group

        group = html.unescape(group).replace("\\/", "/")

        match = re.search(
            r"/groups/([^/?#]+)",
            group,
            flags=re.I,
        )

        if not match:
            return ""

        return match.group(1)

    @staticmethod
    def _extract_post_id_from_url(url: str) -> str:
        if not url:
            return ""

        url = html.unescape(url)
        # Facebook's serialized GraphQL state frequently escapes "/".
        url = url.replace("\\/", "/")

        # A comment URL still identifies its parent post.  The caller may
        # decide whether it wants the comment itself or the parent post.
        patterns = [
            r"/groups/\d+/(?:posts|permalink)/(\d+)",
            r"/posts/(\d+)",
            r"/permalink/(\d+)",
            r"[?&]story_fbid=(\d+)",
            r"[?&]fbid=(\d+)",
            r"[?&]set=gm\.(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url, flags=re.I)
            if match:
                return match.group(1)

        return ""

    @staticmethod
    def _is_valid_post_url(
        url: str,
        group_id: str | None = None,
    ) -> bool:
        if not url:
            return False

        lower = url.lower()

        if "comment_id=" in lower:
            return False

        if "/groups/" not in lower:
            return False

        if not (
            "/posts/" in lower
            or "/permalink/" in lower
            or "story_fbid=" in lower
        ):
            return False

        if group_id:
            extracted_group = FacebookBrowserClient._extract_group_id(url)

            if extracted_group and extracted_group != group_id:
                return False

        return bool(
            FacebookBrowserClient._extract_post_id_from_url(url)
        )

    @staticmethod
    def _canonical_post_url(
        group_id: str,
        post_id: str,
    ) -> str:
        return (
            f"https://www.facebook.com/groups/"
            f"{group_id}/posts/{post_id}/"
        )

    @staticmethod
    def _canonical_comment_url(
        group_id: str,
        post_id: str,
        comment_id: str,
    ) -> str:
        return (
            f"https://www.facebook.com/groups/"
            f"{group_id}/posts/{post_id}/"
            f"?comment_id={comment_id}"
        )

    # ============================================================
    # LOGIN
    # ============================================================

    def _has_facebook_session(self) -> bool:
        if self._context is None:
            return False

        try:
            cookies = self._context.cookies(
                ["https://www.facebook.com"]
            )

            return any(
                cookie.get("name") == "c_user"
                and cookie.get("value")
                for cookie in cookies
            )

        except Exception:
            return False

    def ensure_login(self) -> bool:
        page = self._ensure_browser()
        if self._has_facebook_session():
            return True
        print("Đăng nhập Facebook trong cửa sổ Chrome. Chương trình tự tiếp tục khi đăng nhập xong.", flush=True)
        page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=60000)
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            if page.is_closed():
                raise RuntimeError("Cửa sổ đăng nhập đã đóng. Nhấn phân tích để mở lại.")
            if self._has_facebook_session():
                print("Đã nhận phiên đăng nhập Facebook.", flush=True)
                return True
            page.wait_for_timeout(1000)
        raise RuntimeError("Hết 5 phút chờ đăng nhập. Nhấn phân tích để thử lại.")

    # ============================================================
    # PAGE HTML
    # ============================================================

    def _get_html(self) -> str:
        page = self._ensure_browser()

        try:
            return page.content()
        except Exception:
            return ""

    def _save_debug_html(
        self,
        html_text: str,
        filename: str,
    ):
        path = self.debug_dir / filename

        try:
            path.write_text(
                html_text,
                encoding="utf-8",
                errors="replace",
            )

            print(f"[Debug] HTML: {path}")

        except Exception as exc:
            print(
                f"[!] Không ghi được debug HTML: {exc}"
            )

    def _wait_page(self, milliseconds: int | None = None):
        page = self._ensure_browser()

        wait = (
            self.DEFAULT_WAIT_MS
            if milliseconds is None
            else milliseconds
        )

        try:
            page.wait_for_timeout(wait)
        except Exception:
            time.sleep(wait / 1000)

    # ============================================================
    # STORY / POST STRUCTURED PARSER
    # ============================================================

    def _extract_story_objects(
        self,
        html_text: str,
        group_id: str,
    ) -> list[dict[str, Any]]:
        """
        Trích Story thuộc đúng group và GỘP các representation của cùng post.

        Facebook thường render cùng một post ở nhiều GraphQL object:
        - một Story shell có post_id/feedback;
        - một Story đầy đủ có actors/comet_sections;
        - một object permalink chỉ có URL/post_id.

        Bản cũ dedupe ngay object đầu tiên nên có thể giữ shell và làm mất
        author/content/metrics. Ở đây tất cả Story hợp lệ được gom theo
        post_id rồi merge đệ quy, ưu tiên dữ liệu không rỗng.
        """
        source = self._decode_possible_html_json(html_text)
        grouped: dict[str, dict[str, Any]] = {}

        marker = '"__typename":"Story"'
        search_from = 0
        raw_count = 0

        while True:
            pos = source.find(marker, search_from)
            if pos < 0:
                break

            # Marker Story có thể nằm ở đầu object hoặc ngay trong object.
            # Thử nhiều điểm bắt đầu để tránh bắt nhầm object con.
            candidates = []
            exact = source.rfind('{"__typename":"Story"', 0, pos + len(marker))
            spaced = source.rfind('{"__typename": "Story"', 0, pos + len(marker))
            if exact >= 0:
                candidates.append(exact)
            if spaced >= 0:
                candidates.append(spaced)

            # Một số representation có whitespace/metadata trước marker.
            near = source.rfind('{', 0, pos)
            if near >= 0 and pos - near <= 2000:
                candidates.append(near)

            obj = None
            # Ưu tiên start gần marker nhất nhưng chỉ nhận object Story.
            for brace in sorted(set(candidates), reverse=True):
                obj = self._extract_balanced_object(source, brace)
                if isinstance(obj, dict) and obj.get("__typename") == "Story":
                    break
                obj = None

            if obj is not None:
                raw_count += 1
                post_id = self._safe_int(obj.get("post_id"), 0)
                if not post_id and str(obj.get("id", "")).isdigit():
                    post_id = int(obj["id"])
                post_id_str = str(post_id) if post_id else ""

                if post_id_str:
                    feedback = obj.get("feedback")
                    if not isinstance(feedback, dict):
                        feedback = {}
                    assoc = feedback.get("associated_group")
                    assoc_id = str(assoc.get("id", "")) if isinstance(assoc, dict) else ""

                    url = self._clean_text(
                        obj.get("url") or feedback.get("url") or obj.get("permalink_url") or ""
                    )
                    group_match = assoc_id == str(group_id)
                    if not group_match and url:
                        group_match = (
                            f"/groups/{group_id}/" in url.lower()
                            and bool(self._extract_post_id_from_url(url))
                        )
                    # Nếu object không có group nhưng có post permalink thuộc group, nhận.
                    if not group_match and url:
                        m = re.search(r"/groups/(\d+)/(?:posts|permalink)/(\d+)", url, re.I)
                        group_match = bool(m and m.group(1) == str(group_id) and m.group(2) == post_id_str)

                    if group_match:
                        old = grouped.get(post_id_str)
                        grouped[post_id_str] = (
                            self._merge_rich_objects(old, obj) if old else obj
                        )

            search_from = pos + len(marker)

        # ------------------------------------------------------------
        # MERGE FEEDBACK OBJECTS
        # ------------------------------------------------------------
        # Metrics thường nằm ở UFI renderer riêng, không nằm trong Story.
        # Tất cả representation dùng cùng feedback.id, vì vậy nối chúng lại.
        feedbacks: dict[str, dict[str, Any]] = {}
        # Lấy feedback block theo mọi occurrence của feedback.id.
        # Không giả định id phải là field đầu tiên: UFI comment renderer có
        # dạng {"feedback":{"comment_rendering_instance":...,"id":"..."}}.
        fid_candidates = set()
        for fm in re.finditer(r'"feedback":\{.{0,1200}?"id":"([^"]+)"', source, re.S):
            fid_candidates.add(fm.group(1))

        for fid in fid_candidates:
            for im in re.finditer(r'"id":"' + re.escape(fid) + r'"', source):
                # feedback object thường bắt đầu trong vòng vài trăm ký tự trước id.
                window_start = max(0, im.start() - 1800)
                fb_pos = source.rfind('"feedback":{', window_start, im.start() + 1)
                if fb_pos < 0:
                    continue
                brace = source.find("{", fb_pos + len('"feedback":'))
                obj = self._extract_balanced_object(source, brace)
                if not isinstance(obj, dict):
                    continue
                if str(obj.get("id", "")) != fid:
                    continue
                old = feedbacks.get(fid)
                feedbacks[fid] = self._merge_rich_objects(old, obj) if old else obj

        for post_id, story in grouped.items():
            feedback = story.get("feedback")
            if not isinstance(feedback, dict):
                feedback = {}
                story["feedback"] = feedback
            fid = str(feedback.get("id", ""))
            if fid and fid in feedbacks:
                story["feedback"] = self._merge_rich_objects(
                    feedback, feedbacks[fid]
                )

        print(f"[Structured] Story objects raw: {raw_count}, unique posts: {len(grouped)}")
        return list(grouped.values())

    @classmethod
    def _merge_rich_objects(cls, base: Any, incoming: Any) -> Any:
        """Merge GraphQL representations, giữ dữ liệu giàu thay vì shell rỗng."""
        if isinstance(base, dict) and isinstance(incoming, dict):
            result = dict(base)
            for key, value in incoming.items():
                if key not in result:
                    result[key] = value
                    continue
                current = result[key]
                if isinstance(current, dict) and isinstance(value, dict):
                    result[key] = cls._merge_rich_objects(current, value)
                elif isinstance(current, list) and isinstance(value, list):
                    if len(value) > len(current):
                        result[key] = value
                else:
                    # Không rỗng thắng rỗng; representation dài hơn thường giàu hơn.
                    current_empty = current is None or current == "" or current == [] or current == {}
                    incoming_empty = value is None or value == "" or value == [] or value == {}
                    if current_empty and not incoming_empty:
                        result[key] = value
                    elif isinstance(current, str) and isinstance(value, str) and len(value) > len(current):
                        result[key] = value
            return result
        return incoming if base in (None, "", [], {}) else base

    def _extract_story_author(
        self,
        story: dict[str, Any],
    ) -> str:
        feedback = story.get("feedback", {})

        if not isinstance(feedback, dict):
            feedback = {}

        # Representation đầy đủ thường có actors ngay trên Story.
        actors = story.get("actors")
        if isinstance(actors, list):
            for actor in actors:
                if isinstance(actor, dict):
                    name = self._clean_text(actor.get("name", ""))
                    if name:
                        return name

        owning_profile = feedback.get(
            "owning_profile",
            {},
        )

        if isinstance(owning_profile, dict):
            name = self._clean_text(
                owning_profile.get("name", "")
            )

            if name:
                return name

        # Một số Story có actor.
        for key in (
            "actors",
            "owner",
            "author",
            "actor",
        ):
            value = story.get(key)

            if isinstance(value, dict):
                name = self._clean_text(
                    value.get("name", "")
                )

                if name:
                    return name

            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        name = self._clean_text(
                            item.get("name", "")
                        )

                        if name:
                            return name

        # Một số cấu trúc nằm trong comet_sections.
        sections = story.get(
            "comet_sections",
            {},
        )

        if isinstance(sections, dict):
            candidates = []

            for value in sections.values():
                if isinstance(value, dict):
                    candidates.append(value)

            for candidate in candidates:
                name = self._deep_find_name(candidate)

                if name:
                    return name

        return ""

    def _deep_find_name(
        self,
        obj: Any,
        depth: int = 0,
    ) -> str:
        if depth > 6:
            return ""

        if isinstance(obj, dict):
            typename = obj.get("__typename")

            if typename in (
                "User",
                "Profile",
                "GroupAnonAuthorProfile",
                "Page",
            ):
                name = self._clean_text(
                    obj.get("name", "")
                )

                if name:
                    return name

            for key, value in obj.items():
                if key in (
                    "name",
                    "text",
                ):
                    continue

                result = self._deep_find_name(
                    value,
                    depth + 1,
                )

                if result:
                    return result

        elif isinstance(obj, list):
            for item in obj[:30]:
                result = self._deep_find_name(
                    item,
                    depth + 1,
                )

                if result:
                    return result

        return ""

    def _extract_story_content(
        self,
        story: dict[str, Any],
    ) -> str:
        candidates: list[str] = []

        def add(value: Any):
            if isinstance(value, str):
                text = self._clean_text(value)
                if text:
                    candidates.append(text)
            elif isinstance(value, dict):
                text = self._extract_text(value)
                if text:
                    candidates.append(text)

        # Direct fields first.
        for key in ("message", "preferred_body", "body"):
            add(story.get(key))

        # Modern Facebook often puts the real text several levels down in
        # content -> story -> attached_story -> ... -> message.
        def walk(value: Any, depth: int = 0):
            if depth > 14 or len(candidates) >= 40:
                return

            if isinstance(value, dict):
                for key, child in value.items():
                    if key in {"message", "preferred_body", "body"}:
                        add(child)
                        continue

                    if key in {
                        "content",
                        "story",
                        "attached_story",
                        "comet_sections",
                        "message_container",
                        "message",
                        "above_message",
                        "seo_llm_title",
                    }:
                        walk(child, depth + 1)

            elif isinstance(value, list):
                for child in value[:30]:
                    walk(child, depth + 1)

        walk(story.get("comet_sections", {}))

        # Remove obvious UI-only values.
        bad_values = {
            "like", "comment", "share", "view more", "v",
        }
        candidates = [
            x for x in candidates
            if x.lower() not in bad_values
        ]

        if not candidates:
            return ""

        # The actual post body is normally the longest meaningful text block.
        candidates.sort(key=len, reverse=True)
        return candidates[0]

    def _iter_feedback_objects(
        self,
        story: dict[str, Any],
    ):
        """Yield feedback dictionaries nested anywhere in a Story."""
        seen: set[int] = set()

        def walk(value: Any, depth: int = 0):
            if depth > 16:
                return

            if isinstance(value, dict):
                ident = id(value)
                if ident in seen:
                    return
                seen.add(ident)

                for key, child in value.items():
                    if key == "feedback" and isinstance(child, dict):
                        yield child
                    yield from walk(child, depth + 1)

            elif isinstance(value, list):
                for child in value[:50]:
                    yield from walk(child, depth + 1)

        yield from walk(story)

    def _extract_story_reactions(
        self,
        story: dict[str, Any],
    ) -> int:
        best = 0

        for feedback in self._iter_feedback_objects(story):
            for path in (
                "reactors.count_reduced",
                "reaction_count",
                "reactions.count",
                "reactions.total_count",
            ):
                value = self._deep_get(feedback, path)
                count = self._safe_int(value, -1)
                if count >= 0:
                    best = max(best, count)

            top_reactions = feedback.get("top_reactions")
            if isinstance(top_reactions, dict):
                edges = top_reactions.get("edges", [])
                if isinstance(edges, list):
                    total = 0
                    for edge in edges:
                        if isinstance(edge, dict):
                            total += self._safe_int(
                                edge.get("reaction_count"), 0
                            )
                    best = max(best, total)

        return best

    def _extract_story_metrics(
        self,
        story: dict[str, Any],
    ) -> tuple[int, int, int]:
        best_comments = 0
        best_shares = 0

        for feedback in self._iter_feedback_objects(story):
            comments = self._safe_int(
                self._deep_get(
                    feedback,
                    "comments.total_count",
                    "comments.count",
                    "comment_rendering_instance.comments.total_count",
                    "total_comment_count",
                ),
                0,
            )

            shares = self._safe_int(
                self._deep_get(
                    feedback,
                    "share_count.count",
                    "share_count",
                ),
                0,
            )

            best_comments = max(best_comments, comments)
            best_shares = max(best_shares, shares)

        reactions = self._extract_story_reactions(story)
        return reactions, best_comments, best_shares

    def _story_to_post(
        self,
        story: dict[str, Any],
        group_id: str,
    ) -> dict[str, Any] | None:
        post_id_value = story.get("post_id")

        if not post_id_value:
            return None

        post_id = str(post_id_value)

        if not post_id.isdigit():
            return None

        feedback = story.get(
            "feedback",
            {},
        )

        if not isinstance(feedback, dict):
            feedback = {}

        associated_group = feedback.get(
            "associated_group",
            {},
        )

        if isinstance(
            associated_group,
            dict,
        ):
            associated_group_id = str(
                associated_group.get(
                    "id",
                    "",
                )
            )

            if (
                associated_group_id
                and associated_group_id != group_id
            ):
                return None

        post_url = (
            story.get("url")
            or feedback.get("url")
            or self._canonical_post_url(
                group_id,
                post_id,
            )
        )

        post_url = self._clean_text(post_url)

        if not self._is_valid_post_url(
            post_url,
            group_id,
        ):
            post_url = self._canonical_post_url(
                group_id,
                post_id,
            )

        author_name = self._extract_story_author(
            story
        )

        content = self._extract_story_content(
            story
        )

        created_time = story.get(
            "creation_time"
        )

        if created_time is None:
            created_time = story.get(
                "created_time"
            )

        reactions, comments, shares = (
            self._extract_story_metrics(story)
        )

        return {
            "post_id": post_id,
            "group_id": group_id,
            "post_url": post_url,
            "author_name": author_name,
            "content": content,
            "created_time": created_time or "",
            "likes": reactions,
            "comments": comments,
            "shares": shares,
        }

    # ============================================================
    # DOM POST FALLBACK
    # ============================================================

    def _extract_post_links(
        self,
        html_text: str,
        group_id: str,
    ) -> list[tuple[str, str]]:
        """
        Discover parent post IDs from the modern Facebook Group feed.

        Facebook can expose a post through:
        - a canonical /groups/<gid>/posts/<pid>/ or /permalink/<pid>/ URL;
        - a comment URL whose path contains the parent post ID;
        - GroupHighlightPostUnit objects;
        - photo links using set=gm.<pid> together with idorvanity=<gid>.
        """
        if not html_text:
            return []

        source = html.unescape(html_text).replace("\\/", "/")
        found: dict[str, str] = {}

        def add(pid: str):
            pid = str(pid or "").strip()
            if not pid.isdigit() or pid == str(group_id):
                return
            found.setdefault(
                pid,
                self._canonical_post_url(group_id, pid),
            )

        # 1. Canonical group URLs, including comment URLs.  We deliberately
        # ignore the query string: comment_id identifies a child comment, but
        # the path still gives us the parent post ID.
        url_pattern = (
            r'https?://(?:www\.)?facebook\.com/groups/'
            r'(\d+)/(?:posts|permalink)/(\d+)'
            r'(?P<tail>[^"\'<>\s]*)'
        )
        for match in re.finditer(url_pattern, source, flags=re.I):
            if match.group(1) == str(group_id):
                add(match.group(2))

        # 2. Serialized GraphQL/HTML may contain relative group URLs.
        rel_pattern = (
            r'/groups/(\d+)/(?:posts|permalink)/(\d+)'
        )
        for match in re.finditer(rel_pattern, source, flags=re.I):
            if match.group(1) == str(group_id):
                add(match.group(2))

        # 3. Group highlights are actual posts, not comments.
        highlight_pattern = (
            r'"__typename"\s*:\s*"GroupHighlightPostUnit"'
            r'\s*,\s*"id"\s*:\s*"(\d+)"'
            r'\s*,\s*"type"\s*:\s*"POST"'
        )
        for match in re.finditer(
            highlight_pattern,
            source,
            flags=re.I,
        ):
            add(match.group(1))

        # 4. Photo links: accept set=gm.<pid> only when the link explicitly
        # belongs to the target group through idorvanity=<group_id>.
        photo_pattern = (
            r'https?://(?:www\.)?facebook\.com/photo/'
            r'[^"\'<>\s]*[?&]set=gm\.(\d+)'
            r'[^"\'<>\s]*[?&]idorvanity='
            + re.escape(str(group_id))
        )
        for match in re.finditer(
            photo_pattern,
            source,
            flags=re.I,
        ):
            add(match.group(1))

        return list(found.items())

    def _parse_dom_posts(
        self,
        html_text: str,
        group_id: str,
    ) -> list[dict[str, Any]]:
        """
        DOM fallback.

        Chỉ dùng article có post/permalink link.
        """
        page = self._ensure_browser()

        posts: list[dict[str, Any]] = []

        try:
            articles = page.locator(
                '[role="article"]'
            )

            count = articles.count()

        except Exception:
            return posts

        for index in range(count):
            try:
                article = articles.nth(index)

                hrefs = article.locator(
                    "a[href]"
                )

                valid_link = ""
                post_id = ""

                href_count = hrefs.count()

                for i in range(href_count):
                    href = hrefs.nth(i).get_attribute(
                        "href"
                    )

                    if not href:
                        continue

                    if self._is_valid_post_url(
                        href,
                        group_id,
                    ):
                        post_id = (
                            self._extract_post_id_from_url(
                                href
                            )
                        )

                        if post_id:
                            valid_link = href
                            break

                if not post_id:
                    continue

                try:
                    text = article.inner_text()
                except Exception:
                    text = ""

                text = self._clean_text(text)

                posts.append(
                    {
                        "post_id": post_id,
                        "group_id": group_id,
                        "post_url": valid_link,
                        "author_name": "",
                        "content": text,
                        "created_time": "",
                        "likes": 0,
                        "comments": 0,
                        "shares": 0,
                    }
                )

            except Exception:
                continue

        return posts

    # ============================================================
    # POST COLLECTION
    # ============================================================

    def _scan_current_page_for_posts(
        self,
        group_id: str,
        known_post_ids: set[str],
    ) -> list[dict[str, Any]]:
        html_text = self._get_html()

        if not html_text:
            return []

        posts: list[dict[str, Any]] = []

        # -------------------------------
        # 1. STRUCTURED
        # -------------------------------

        stories = self._extract_story_objects(
            html_text,
            group_id,
        )

        print(
            f"[Structured] Story objects: "
            f"{len(stories)}"
        )

        # Lấy tất cả comment IDs đang xuất hiện.
        comment_ids = set(
            re.findall(
                r'[?&]comment_id=(\d+)',
                html_text,
                flags=re.I,
            )
        )

        for story in stories:
            post = self._story_to_post(
                story,
                group_id,
            )

            if post is None:
                continue

            post_id = post["post_id"]

            if post_id in comment_ids:
                continue

            if post_id in known_post_ids:
                continue

            known_post_ids.add(post_id)

            posts.append(post)

            print(
                f"+ POST STRUCTURED: {post_id}"
            )
            print(
                f"  Author   : "
                f"{post['author_name']}"
            )
            print(
                f"  Reaction : "
                f"{post['likes']}"
            )
            print(
                f"  Comments : "
                f"{post['comments']}"
            )
            print(
                f"  Shares   : "
                f"{post['shares']}"
            )
            print(
                f"  Content  : "
                f"{post['content'][:120]}"
            )

        # -------------------------------
        # 2. DOM FALLBACK
        # -------------------------------

        dom_posts = self._parse_dom_posts(
            html_text,
            group_id,
        )

        valid_dom = 0

        for post in dom_posts:
            post_id = post["post_id"]

            if post_id in comment_ids:
                continue

            if post_id in known_post_ids:
                continue

            known_post_ids.add(post_id)

            posts.append(post)

            valid_dom += 1

            print(
                f"+ POST DOM: {post_id}"
            )

        print(
            f"[DOM] Posts hợp lệ mới: "
            f"{valid_dom}"
        )

        # -------------------------------
        # 3. LINK FALLBACK
        # -------------------------------

        links = self._extract_post_links(
            html_text,
            group_id,
        )

        link_new = 0
        for post_id, post_url in links:
            if post_id in known_post_ids:
                continue

            known_post_ids.add(post_id)
            posts.append(
                {
                    "post_id": post_id,
                    "group_id": group_id,
                    "post_url": post_url,
                    "author_name": "",
                    "content": "",
                    "created_time": "",
                    "likes": 0,
                    "comments": 0,
                    "shares": 0,
                }
            )
            link_new += 1
            print(f"+ POST ID FROM LINK: {post_id}")

        print(
            f"[Links] Post links hợp lệ: "
            f"{len(links)}, mới: {link_new}"
        )

        return posts

    def _get_scroll_state(self) -> dict[str, int]:
        page = self._ensure_browser()

        try:
            return page.evaluate(
                """
                () => ({
                    y: Math.round(window.scrollY),
                    height: Math.round(document.body.scrollHeight),
                    viewport: Math.round(window.innerHeight),
                    articles: document.querySelectorAll(
                        '[role="article"]'
                    ).length
                })
                """
            )
        except Exception:
            return {
                "y": 0,
                "height": 0,
                "viewport": 0,
                "articles": 0,
            }

    def _scroll_once(self):
        page = self._ensure_browser()

        try:
            page.mouse.wheel(0, 1800)
        except Exception:
            pass

        try:
            page.evaluate(
                """
                () => {
                    window.scrollBy({
                        top: Math.floor(window.innerHeight * 1.4),
                        left: 0,
                        behavior: "instant"
                    });
                }
                """
            )
        except Exception:
            pass

        self._wait_page(1800)

    def _enrich_post_from_detail_page(
        self,
        post: dict[str, Any],
        group_id: str,
    ) -> dict[str, Any]:
        """
        Open the canonical post page and merge the full Story representation.

        This is the reliable second stage for Group pages where the feed DOM
        exposes only comments and the GraphQL Story in the feed is a shell.
        """
        post_id = str(post.get("post_id", ""))
        if not post_id.isdigit():
            return post

        page = self._ensure_browser()
        url = self._canonical_post_url(group_id, post_id)

        try:
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )
            self._wait_page(2500)

            detail_html = self._get_html()
            stories = self._extract_story_objects(
                detail_html,
                group_id,
            )

            for story in stories:
                if str(story.get("post_id", "")) != post_id:
                    continue

                rich = self._story_to_post(story, group_id)
                if rich:
                    merged = dict(post)
                    for key, value in rich.items():
                        if value not in ("", None):
                            merged[key] = value

                    # Keep explicit zero metrics from a real detail page.
                    for key in ("likes", "comments", "shares"):
                        if key in rich:
                            merged[key] = rich[key]

                    return merged

        except Exception as exc:
            print(
                f"[!] Không enrich được post {post_id}: "
                f"{exc}"
            )

        return post

    def _collect_group_posts(
        self,
        group_id: str,
        max_posts: int = 100,
        max_scrolls: int = 60,
    ) -> list[dict[str, Any]]:
        page = self._ensure_browser()

        url = self._normalize_group_url(
            group_id
        )

        print()
        print("=" * 70)
        print("BẮT ĐẦU QUÉT GROUP")
        print("=" * 70)
        print(f"Group: {url}")
        print(f"Target posts: {max_posts}")
        print(f"Max scrolls: {max_scrolls}")
        print("=" * 70)

        try:
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )
        except PlaywrightTimeoutError:
            print(
                "[!] Facebook page load timeout, "
                "tiếp tục xử lý HTML hiện tại."
            )
        except Exception as exc:
            print(
                f"[!] Không mở được Group: {exc}"
            )
            return []

        self._wait_page(4000)

        # Snapshot ngay sau khi Group tải xong.
        self._save_debug_html(
            self._get_html(),
            "group_initial.html",
        )

        actual_group_id = self._extract_group_id(
            group_id
        )

        # Nếu group_id là vanity name, thử lấy ID
        # từ URL / HTML.
        if not actual_group_id.isdigit():
            html_text = self._get_html()

            matches = re.findall(
                r'"associated_group":\{"id":"(\d+)"',
                html_text,
            )

            if matches:
                actual_group_id = matches[0]

            else:
                story_group_matches = re.findall(
                    r'"groups/(\d+)',
                    html_text,
                )

                if story_group_matches:
                    actual_group_id = (
                        story_group_matches[0]
                    )

        if not actual_group_id:
            print(
                "[!] Không xác định được Group ID."
            )
            return []

        print(
            f"[+] Group ID sử dụng: "
            f"{actual_group_id}"
        )

        known_post_ids: set[str] = set()
        posts: list[dict[str, Any]] = []

        previous_height = -1
        previous_link_count = -1
        previous_y = -1

        stable_rounds = 0

        for scroll_index in range(
            1,
            max_scrolls + 1,
        ):
            print()
            print(
                f"[{scroll_index}/{max_scrolls}] "
                f"Đang quét..."
            )

            before_count = len(posts)

            current_posts = (
                self._scan_current_page_for_posts(
                    actual_group_id,
                    known_post_ids,
                )
            )

            posts.extend(current_posts)

            # Giới hạn target.
            if len(posts) >= max_posts:
                posts = posts[:max_posts]
                print(
                    f"[+] Đã đạt target "
                    f"{max_posts} posts."
                )
                break

            state = self._get_scroll_state()

            html_text = self._get_html()

            # Lưu snapshot từng vòng để có thể đối chiếu Facebook đã tải gì.
            self._save_debug_html(
                html_text,
                f"group_scroll_{scroll_index:03d}.html",
            )

            links = self._extract_post_links(
                html_text,
                actual_group_id,
            )

            link_count = len(links)

            new_count = len(posts) - before_count

            print(
                f"Scroll state: "
                f"Y={state['y']} "
                f"Height={state['height']} "
                f"Articles={state['articles']} "
                f"PostLinks={link_count}"
            )

            print(
                f"Posts đã nhận diện: "
                f"{len(posts)} "
                f"(new={new_count})"
            )

            # -------------------------------
            # STOP / STABILITY
            # -------------------------------

            height_stable = (
                state["height"] == previous_height
            )

            links_stable = (
                link_count == previous_link_count
            )

            y_stable = (
                state["y"] == previous_y
            )

            if (
                new_count == 0
                and height_stable
                and links_stable
                and y_stable
            ):
                stable_rounds += 1
            else:
                stable_rounds = 0

            if stable_rounds >= 4:
                print(
                    "[+] Trang đã ổn định "
                    "4 vòng liên tiếp."
                )
                break

            previous_height = state["height"]
            previous_link_count = link_count
            previous_y = state["y"]

            # Nếu chưa tới cuối trang thì tiếp tục.
            self._scroll_once()

            after_state = self._get_scroll_state()

            # Nếu không thể scroll thêm.
            if (
                after_state["y"] == state["y"]
                and after_state["height"]
                == state["height"]
            ):
                stable_rounds += 1

                if stable_rounds >= 4:
                    print(
                        "[+] Không thể scroll thêm."
                    )
                    break

        # ------------------------------------------------------------
        # SECOND STAGE: enrich shell/link-discovered posts.
        # The Group feed may expose parent IDs through comment links but not
        # the complete post object.  Open each canonical post once.
        # ------------------------------------------------------------
        print()
        print("=" * 70)
        print("ENRICH POST DETAILS")
        print("=" * 70)

        enriched_posts: list[dict[str, Any]] = []
        for index, post in enumerate(posts, 1):
            print(
                f"[Enrich {index}/{len(posts)}] "
                f"Post {post.get('post_id', '')}"
            )
            rich = self._enrich_post_from_detail_page(
                post,
                actual_group_id,
            )
            enriched_posts.append(rich)

        posts = enriched_posts

        # Debug HTML cuối.
        final_html = self._get_html()

        self._save_debug_html(
            final_html,
            "group_posts_final.html",
        )

        print()
        print("=" * 70)
        print(
            f"HOÀN TẤT: {len(posts)} POSTS"
        )
        print("=" * 70)

        return posts

    # ============================================================
    # GET GROUP
    # ============================================================

    def get_group(
        self,
        group_id: str,
    ) -> dict[str, Any]:
        """
        Graph API Group endpoint không được sử dụng.

        Trả về metadata tối thiểu tương thích với
        FacebookClient.
        """
        page = self._ensure_browser()

        group_url = self._normalize_group_url(
            group_id
        )

        try:
            page.goto(
                group_url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            self._wait_page(2500)

        except Exception:
            pass

        title = ""

        try:
            title = self._clean_text(
                page.title()
            )
        except Exception:
            pass

        actual_id = self._extract_group_id(
            group_id
        )

        html_text = self._get_html()

        # Cố gắng lấy group ID từ structured data.
        if not actual_id.isdigit():
            matches = re.findall(
                r'"associated_group":\{"id":"(\d+)"',
                html_text,
            )

            if matches:
                actual_id = matches[0]

        if actual_id.isdigit():
            FacebookBrowserClient._global_last_group_id = actual_id

        return {
            "group_id": actual_id,
            "name": title,
            "url": group_url,
        }

    # ============================================================
    # PUBLIC: GROUP POSTS
    # ============================================================

    def get_group_posts(
        self,
        group_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not self.ensure_login():
            return []

        actual_group_id = self._extract_group_id(
            group_id
        )

        if actual_group_id.isdigit():
            FacebookBrowserClient._global_last_group_id = actual_group_id

        return self._collect_group_posts(
            actual_group_id,
            max_posts=limit,
            max_scrolls=60,
        )

    # ============================================================
    # GET SINGLE POST
    # ============================================================

    def _find_story_by_post_id(
        self,
        html_text: str,
        group_id: str,
        post_id: str,
    ) -> dict[str, Any] | None:
        stories = self._extract_story_objects(
            html_text,
            group_id,
        )

        for story in stories:
            if str(
                story.get("post_id", "")
            ) == str(post_id):
                return story

        return None

    def _parse_single_post_dom(
        self,
        group_id: str,
        post_id: str,
    ) -> dict[str, Any] | None:
        page = self._ensure_browser()

        try:
            articles = page.locator(
                '[role="article"]'
            )

            count = articles.count()

        except Exception:
            return None

        for index in range(count):
            try:
                article = articles.nth(index)

                hrefs = article.locator(
                    "a[href]"
                )

                found = False

                for i in range(
                    hrefs.count()
                ):
                    href = hrefs.nth(i).get_attribute(
                        "href"
                    )

                    extracted = (
                        self._extract_post_id_from_url(
                            href or ""
                        )
                    )

                    if (
                        extracted == post_id
                        and "comment_id="
                        not in (href or "").lower()
                    ):
                        found = True
                        break

                if not found:
                    continue

                text = self._clean_text(
                    article.inner_text()
                )

                return {
                    "post_id": post_id,
                    "group_id": group_id,
                    "post_url": self._canonical_post_url(
                        group_id,
                        post_id,
                    ),
                    "author_name": "",
                    "content": text,
                    "created_time": "",
                    "likes": 0,
                    "comments": 0,
                    "shares": 0,
                }

            except Exception:
                continue

        return None

    def get_post(
        self,
        post_id: str,
    ) -> dict[str, Any]:
        if not self.ensure_login():
            return {}

        post_input = str(post_id).strip()

        # Cho phép truyền cả Post ID lẫn Post URL.
        # Khi truyền URL, lấy đồng thời Group ID + Post ID từ chính URL đó.
        input_group_id = self._extract_group_id(post_input)
        input_post_id = self._extract_post_id_from_url(post_input)

        if input_post_id:
            post_id = input_post_id
        else:
            post_id = post_input

        page = self._ensure_browser()

        current_url = ""
        try:
            current_url = page.url
        except Exception:
            pass

        group_id = input_group_id if input_group_id.isdigit() else self._extract_group_id(current_url)

        if not group_id.isdigit():
            group_id = FacebookBrowserClient._global_last_group_id

        if not group_id.isdigit():
            print(
                "[!] get_post() không xác định được Group ID. "
                "Hãy dùng Post URL có /groups/<group_id>/... hoặc "
                "chạy phân tích Group trước."
            )
            return {}

        FacebookBrowserClient._global_last_group_id = group_id

        post_url = self._canonical_post_url(
            group_id,
            post_id,
        )

        print()
        print(
            f"[+] Mở post: {post_url}"
        )

        try:
            page.goto(
                post_url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

        except PlaywrightTimeoutError:
            pass

        except Exception as exc:
            print(
                f"[!] Không mở được post: {exc}"
            )
            return {}

        self._wait_page(3500)

        html_text = self._get_html()

        story = self._find_story_by_post_id(
            html_text,
            group_id,
            post_id,
        )

        if story:
            post = self._story_to_post(
                story,
                group_id,
            )

            if post:
                print(
                    "[+] POST STRUCTURED:"
                    f" {post_id}"
                )

                return post

        print(
            "[!] Không tìm thấy Story structured."
        )

        dom_post = self._parse_single_post_dom(
            group_id,
            post_id,
        )

        if dom_post:
            print(
                "[+] POST DOM:"
                f" {post_id}"
            )

            return dom_post

        return {}

    # ============================================================
    # COMMENT STRUCTURED PARSER
    # ============================================================

    def _extract_comment_nodes(
        self,
        html_text: str,
        post_id: str,
    ) -> list[dict[str, Any]]:
        """Extract top-level comments from Facebook's structured GraphQL state.

        Structured data is preferred.  The parser is deliberately tolerant because
        Facebook changes the exact shape of comment nodes frequently.
        """
        source = self._decode_possible_html_json(html_text)
        results: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for match in re.finditer(r'"legacy_fbid":"(\d+)"', source):
            comment_id = match.group(1)
            if comment_id in seen_ids:
                continue

            node_obj = self._find_nearest_json_object(
                source, match.start(), ('{"node":{', '{"node": {')
            )
            if not node_obj or not isinstance(node_obj.get("node"), dict):
                continue
            node = node_obj["node"]
            if str(node.get("legacy_fbid", "")) != comment_id:
                continue

            feedback = node.get("feedback") if isinstance(node.get("feedback"), dict) else {}
            comment_url = self._clean_text(
                feedback.get("url", "") or node.get("url", "")
            )

            # Only comments belonging to the requested post.
            if comment_url:
                m = re.search(r"/groups/\d+/(?:posts|permalink)/(\d+)", comment_url, re.I)
                if m and m.group(1) != str(post_id):
                    continue
            else:
                local = source[max(0, match.start()-10000):min(len(source), match.end()+10000)]
                if f"comment_id={comment_id}" not in local:
                    continue

            # depth=0 means a top-level comment.  Never interpret depth as reply count.
            depth = node.get("depth")
            try:
                if depth is not None and int(depth) != 0:
                    continue
            except Exception:
                pass

            author_name = ""
            author = node.get("author")
            if isinstance(author, dict):
                author_name = self._clean_text(author.get("name", ""))
            if not author_name:
                for key in ("author", "owning_profile", "owner"):
                    value = node.get(key)
                    if isinstance(value, dict):
                        author_name = self._clean_text(value.get("name", ""))
                        if author_name:
                            break

            # Content: try all common comment body representations, including
            # body_renderer / renderer structures used by some Facebook builds.
            content_candidates: list[str] = []
            def collect_text(value: Any, depth: int = 0):
                if depth > 8 or len(content_candidates) >= 20:
                    return
                if isinstance(value, str):
                    value = self._clean_text(value)
                    if value and value.lower() not in {"like", "comment", "share", "reply"}:
                        content_candidates.append(value)
                elif isinstance(value, dict):
                    for key in ("preferred_body", "body", "body_renderer", "message", "text", "renderer"):
                        if key in value:
                            collect_text(value[key], depth + 1)
                elif isinstance(value, list):
                    for item in value[:20]:
                        collect_text(item, depth + 1)

            for key in ("preferred_body", "body", "body_renderer", "message", "text"):
                if key in node:
                    collect_text(node[key])
            if not content_candidates:
                collect_text(node.get("comment"))
            content = max(content_candidates, key=len) if content_candidates else ""

            created_time = node.get("created_time") or node.get("creation_time") or ""

            reactions = self._safe_int(
                self._deep_get(feedback, "reactors.count_reduced", "reaction_count"), -1
            )
            if reactions < 0:
                reactions = 0
                top = feedback.get("top_reactions")
                if isinstance(top, dict) and isinstance(top.get("edges"), list):
                    reactions = sum(
                        self._safe_int(e.get("reaction_count"), 0)
                        for e in top["edges"] if isinstance(e, dict)
                    )

            replies = self._safe_int(
                self._deep_get(
                    feedback,
                    "replies_fields.total_count",
                    "replies.total_count",
                    "replies.count",
                    "reply_count",
                ), 0
            )

            if not comment_url:
                comment_url = self._canonical_comment_url(
                    self._extract_group_id_from_comment_context(source, match.start())
                    or self._extract_group_id(self._page.url if self._page else "")
                    or "", str(post_id), comment_id
                )
            comment_url = self._clean_text(comment_url)

            if comment_url:
                m = re.search(r"/(?:posts|permalink)/(\d+)", comment_url, re.I)
                if m and m.group(1) != str(post_id):
                    continue

            results.append({
                "comment_id": comment_id,
                "post_id": str(post_id),
                "comment_url": comment_url,
                "author_name": author_name,
                "content": content,
                "created_time": created_time,
                "reactions": reactions,
                "replies": replies,
            })
            seen_ids.add(comment_id)

        return results

    def _extract_group_id_from_comment_context(self, source: str, position: int) -> str:
        """Best-effort group ID lookup near a structured comment node."""
        local = source[max(0, position-12000):min(len(source), position+12000)]
        matches = re.findall(r"/groups/(\d+)", local, re.I)
        return matches[0] if matches else ""

    # ============================================================
    # COMMENT DOM FALLBACK
    # ============================================================

    def _extract_comment_links(
        self,
        html_text: str,
        post_id: str,
    ) -> list[str]:
        source = html.unescape(html_text)

        pattern = (
            r'https?://(?:www\.)?facebook\.com/'
            r'groups/\d+/'
            r'(?:posts|permalink)/'
            + re.escape(str(post_id))
            + r'[^"\'<>\s]*'
            r'[?&]comment_id=(\d+)'
            r'[^"\'<>\s]*'
        )

        results = []

        for match in re.finditer(
            pattern,
            source,
            flags=re.I,
        ):
            url = match.group(0)

            url = url.rstrip(
                '",\\\'<>);'
            )

            if url not in results:
                results.append(url)

        return results

    def _parse_dom_comments(
        self,
        post_id: str,
    ) -> list[dict[str, Any]]:
        page = self._ensure_browser()

        comments: list[dict[str, Any]] = []
        seen: set[str] = set()

        try:
            articles = page.locator(
                '[role="article"]'
            )

            count = articles.count()

        except Exception:
            return comments

        for index in range(count):
            try:
                article = articles.nth(index)

                hrefs = article.locator(
                    "a[href]"
                )

                comment_id = ""
                comment_url = ""

                for i in range(
                    hrefs.count()
                ):
                    href = hrefs.nth(i).get_attribute(
                        "href"
                    )

                    if not href:
                        continue

                    if (
                        "comment_id="
                        not in href.lower()
                    ):
                        continue

                    match = re.search(
                        r"[?&]comment_id=(\d+)",
                        href,
                        flags=re.I,
                    )

                    if not match:
                        continue

                    extracted_post = re.search(
                        r"/(?:posts|permalink)/(\d+)",
                        href,
                        flags=re.I,
                    )

                    if (
                        not extracted_post
                        or extracted_post.group(1)
                        != str(post_id)
                    ):
                        continue

                    comment_id = match.group(1)
                    comment_url = href

                    break

                if not comment_id:
                    continue

                if comment_id in seen:
                    continue

                # -------------------------------
                # AUTHOR
                # -------------------------------

                author_name = ""

                profile_links = article.locator(
                    'a[href*="/user/"], '
                    'a[href*="/profile.php"], '
                    'a[href*="facebook.com/"]'
                )

                for i in range(
                    min(
                        profile_links.count(),
                        20,
                    )
                ):
                    try:
                        text = self._clean_text(
                            profile_links.nth(i).inner_text()
                        )

                        if (
                            text
                            and len(text) < 120
                            and text.lower()
                            not in {
                                "like",
                                "comment",
                                "share",
                                "reply",
                            }
                        ):
                            author_name = text
                            break

                    except Exception:
                        continue

                # aria-label fallback.
                if not author_name:
                    try:
                        aria_nodes = article.locator(
                            '[aria-label*="Comment by"]'
                        )

                        if aria_nodes.count():
                            label = (
                                aria_nodes.nth(0)
                                .get_attribute(
                                    "aria-label"
                                )
                                or ""
                            )

                            match = re.search(
                                r"Comment by\s+(.+?)(?:\s+on\s+|\s+a\s+\w+|\s+\d+)",
                                label,
                                flags=re.I,
                            )

                            if match:
                                author_name = (
                                    self._clean_text(
                                        match.group(1)
                                    )
                                )

                    except Exception:
                        pass

                # -------------------------------
                # CONTENT
                # -------------------------------

                content = ""

                try:
                    candidates = article.locator(
                        'div[dir="auto"]'
                    )

                    candidate_texts = []

                    for i in range(
                        min(
                            candidates.count(),
                            30,
                        )
                    ):
                        try:
                            text = self._clean_text(
                                candidates.nth(i).inner_text()
                            )

                            if not text:
                                continue

                            lower = text.lower()

                            if lower in {
                                "like",
                                "comment",
                                "share",
                                "reply",
                                "most relevant",
                            }:
                                continue

                            candidate_texts.append(text)

                        except Exception:
                            continue

                    if candidate_texts:
                        candidate_texts.sort(
                            key=len,
                            reverse=True,
                        )

                        content = (
                            candidate_texts[0]
                        )

                except Exception:
                    pass

                # -------------------------------
                # REACTIONS
                # -------------------------------

                reactions = 0

                try:
                    labels = article.locator(
                        '[aria-label]'
                    )

                    for i in range(
                        min(
                            labels.count(),
                            50,
                        )
                    ):
                        label = (
                            labels.nth(i)
                            .get_attribute(
                                "aria-label"
                            )
                            or ""
                        )

                        match = re.search(
                            r"(\d+)\s+"
                            r"(?:reaction|reactions|like|likes)",
                            label,
                            flags=re.I,
                        )

                        if match:
                            reactions = int(
                                match.group(1)
                            )
                            break

                except Exception:
                    pass

                # -------------------------------
                # REPLIES
                # -------------------------------

                replies = 0

                try:
                    text = self._clean_text(
                        article.inner_text()
                    )

                    match = re.search(
                        r"(\d+)\s+"
                        r"(?:repl(?:y|ies)|phản hồi)",
                        text,
                        flags=re.I,
                    )

                    if match:
                        replies = int(
                            match.group(1)
                        )

                except Exception:
                    pass

                comments.append(
                    {
                        "comment_id": comment_id,
                        "post_id": str(post_id),
                        "comment_url": comment_url,
                        "author_name": author_name,
                        "content": content,
                        "created_time": "",
                        "reactions": reactions,
                        "replies": replies,
                    }
                )

                seen.add(comment_id)

                print(
                    f"+ COMMENT DOM: "
                    f"{comment_id}"
                )

            except Exception:
                continue

        return comments

    # ============================================================
    # COMMENT EXPANSION
    # ============================================================

    def _click_comment_expansion_controls(self) -> int:
        """Click controls that load more comments/replies.

        Facebook may expose these as role=button, links, or plain text nodes.
        We inspect visible elements and use conservative Vietnamese/English
        patterns so that ordinary Reply/Like/Share controls are not clicked.
        """
        page = self._ensure_browser()
        patterns = [
            re.compile(r"view\s+more\s+comments?|more\s+comments?", re.I),
            re.compile(r"xem\s+thêm\s+bình\s+luận|xem\s+thêm\s+comment", re.I),
            re.compile(r"view\s+more\s+repl(?:y|ies)|more\s+repl(?:y|ies)", re.I),
            re.compile(r"xem\s+thêm\s+(?:câu\s+)?trả\s+lời", re.I),
        ]
        clicked = 0
        seen_labels: set[str] = set()

        # First inspect semantic buttons/links.
        for selector in ('[role="button"]', 'a[role="button"]', 'button'):
            try:
                locator = page.locator(selector)
                count = min(locator.count(), 120)
            except Exception:
                continue
            for i in range(count):
                try:
                    el = locator.nth(i)
                    if not el.is_visible():
                        continue
                    label = self._clean_text(
                        el.get_attribute("aria-label") or el.inner_text() or ""
                    )
                    if not label or label.lower() in seen_labels:
                        continue
                    if "most relevant" in label.lower() or label.lower() in {"like", "comment", "share", "reply"}:
                        continue
                    if not any(p.search(label) for p in patterns):
                        continue
                    seen_labels.add(label.lower())
                    el.scroll_into_view_if_needed(timeout=1500)
                    el.click(timeout=2500)
                    clicked += 1
                    page.wait_for_timeout(700)
                except Exception:
                    continue

        # Then text nodes, useful for Facebook's span/div controls.
        for pattern in patterns:
            try:
                locator = page.get_by_text(pattern, exact=False)
                count = min(locator.count(), 30)
            except Exception:
                continue
            for i in range(count):
                try:
                    el = locator.nth(i)
                    if not el.is_visible():
                        continue
                    label = self._clean_text(el.inner_text() or el.get_attribute("aria-label") or "")
                    if not label or label.lower() in seen_labels:
                        continue
                    if not any(p.search(label) for p in patterns):
                        continue
                    seen_labels.add(label.lower())
                    el.scroll_into_view_if_needed(timeout=1500)
                    el.click(timeout=2500)
                    clicked += 1
                    page.wait_for_timeout(700)
                except Exception:
                    continue

        return clicked

    # ============================================================
    # COMMENT COLLECTION
    # ============================================================

    def _get_expected_comment_count(
        self,
        html_text: str,
        post_id: str,
    ) -> int:
        """
        Lấy comments.total_count từ Story thuộc post_id.
        """
        # Không có group ID thì scan Story generic.
        stories = []

        source = self._decode_possible_html_json(
            html_text
        )

        marker = '"__typename":"Story"'

        search_from = 0

        while True:
            pos = source.find(
                marker,
                search_from,
            )

            if pos < 0:
                break

            obj = self._find_nearest_json_object(
                source,
                pos,
                (
                    '{"__typename":"Story"',
                    '{"__typename": "Story"',
                ),
            )

            if obj:
                if str(
                    obj.get(
                        "post_id",
                        "",
                    )
                ) == str(post_id):
                    stories.append(obj)

            search_from = (
                pos + len(marker)
            )

        for story in stories:
            feedback = story.get(
                "feedback",
                {},
            )

            if not isinstance(
                feedback,
                dict,
            ):
                continue

            value = self._deep_get(
                feedback,
                "comments.total_count",
                "comments.count",
            )

            count = self._safe_int(
                value,
                -1,
            )

            if count >= 0:
                return count

        return -1

    def _collect_post_comments(
        self,
        post_id: str,
        max_comments: int = 100,
        max_rounds: int = 12,
    ) -> list[dict[str, Any]]:
        page = self._ensure_browser()

        current_url = ""

        try:
            current_url = page.url
        except Exception:
            pass

        # Hỗ trợ cả Post ID và Post URL.
        post_input = str(post_id).strip()
        input_group_id = self._extract_group_id(post_input)
        input_post_id = self._extract_post_id_from_url(post_input)

        if input_post_id:
            post_id = input_post_id

        group_id = (
            input_group_id
            if input_group_id.isdigit()
            else self._extract_group_id(current_url)
        )

        if not group_id.isdigit():
            group_id = FacebookBrowserClient._global_last_group_id

        if not group_id.isdigit():
            print(
                "[!] Không xác định được Group ID "
                "khi lấy comments. "
                "Hãy truyền Post URL có Group ID hoặc chạy phân tích Group trước."
            )
            return []

        FacebookBrowserClient._global_last_group_id = group_id

        post_url = self._canonical_post_url(
            group_id,
            str(post_id),
        )

        print()
        print("=" * 70)
        print("BẮT ĐẦU QUÉT COMMENTS")
        print("=" * 70)
        print(f"Post ID: {post_id}")
        print(f"URL    : {post_url}")
        print("=" * 70)

        # Nếu chưa ở post này.
        if str(post_id) not in current_url:
            try:
                page.goto(
                    post_url,
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
            except Exception:
                pass

            self._wait_page(3500)

        comments: list[dict[str, Any]] = []
        seen_comment_ids: set[str] = set()

        no_new_rounds = 0

        expected = -1

        for round_index in range(
            1,
            max_rounds + 1,
        ):
            print()
            print(
                f"[Comment round "
                f"{round_index}/{max_rounds}]"
            )

            html_text = self._get_html()

            if round_index == 1:
                expected = (
                    self._get_expected_comment_count(
                        html_text,
                        str(post_id),
                    )
                )

                if expected >= 0:
                    print(
                        f"Facebook báo "
                        f"{expected} comments."
                    )

            before = len(comments)

            # ----------------------------------------
            # STRUCTURED COMMENTS
            # ----------------------------------------

            structured = (
                self._extract_comment_nodes(
                    html_text,
                    str(post_id),
                )
            )

            print(
                f"[Structured] Comments: "
                f"{len(structured)}"
            )

            for comment in structured:
                cid = comment[
                    "comment_id"
                ]

                if cid in seen_comment_ids:
                    continue

                seen_comment_ids.add(cid)
                comments.append(comment)

                print(
                    f"+ COMMENT STRUCTURED: "
                    f"{cid}"
                )
                print(
                    f"  Author   : "
                    f"{comment['author_name']}"
                )
                print(
                    f"  Reaction : "
                    f"{comment['reactions']}"
                )
                print(
                    f"  Replies  : "
                    f"{comment['replies']}"
                )
                print(
                    f"  Content  : "
                    f"{comment['content'][:120]}"
                )

            # ----------------------------------------
            # DOM FALLBACK
            # ----------------------------------------

            if len(comments) < max_comments:
                dom_comments = self._parse_dom_comments(str(post_id))

                # DOM is not only an "add new" fallback.  It is also used to
                # enrich structured comments whose body/author is missing.
                by_id = {c["comment_id"]: c for c in comments}
                for dom_comment in dom_comments:
                    cid = dom_comment["comment_id"]
                    existing = by_id.get(cid)
                    if existing is None:
                        if len(comments) < max_comments:
                            seen_comment_ids.add(cid)
                            comments.append(dom_comment)
                            by_id[cid] = dom_comment
                    else:
                        for key in ("author_name", "content", "comment_url", "created_time"):
                            if not existing.get(key) and dom_comment.get(key):
                                existing[key] = dom_comment[key]
                        # Keep structured numeric values unless DOM has a
                        # demonstrably larger value.
                        for key in ("reactions", "replies"):
                            if self._safe_int(dom_comment.get(key), 0) > self._safe_int(existing.get(key), 0):
                                existing[key] = self._safe_int(dom_comment.get(key), 0)

            new_count = (
                len(comments) - before
            )

            print(
                f"Comments thu được: "
                f"{len(comments)}"
                + (
                    f" / {expected}"
                    if expected >= 0
                    else ""
                )
            )

            # Target đạt.
            if len(comments) >= max_comments:
                comments = comments[
                    :max_comments
                ]

                print(
                    f"[+] Đạt giới hạn "
                    f"{max_comments} comments."
                )

                break

            # Đã đạt expected.
            if (
                expected >= 0
                and len(comments) >= expected
            ):
                print(
                    "[+] Đã thu đủ số comments "
                    "Facebook công bố."
                )
                break

            # ----------------------------------------
            # EXPAND
            # ----------------------------------------

            clicked = (
                self._click_comment_expansion_controls()
            )

            print(
                f"[Expand] Clicked: {clicked}"
            )

            if new_count == 0 and clicked == 0:
                no_new_rounds += 1
            else:
                no_new_rounds = 0

            # Do not stop too early: Facebook often needs several scroll/click
            # cycles before exposing the next comment batch.
            if no_new_rounds >= 5:
                print("[+] 5 vòng liên tiếp không có comment mới.")
                break

            self._wait_page(1800)

            # Scroll xuống để Facebook load thêm.
            try:
                page.mouse.wheel(0, 2200)
            except Exception:
                pass

            self._wait_page(1800)

        # Debug.
        final_html = self._get_html()

        self._save_debug_html(
            final_html,
            "comments_final.html",
        )

        # ----------------------------------------
        # FINAL REPORT
        # ----------------------------------------

        print()
        print("=" * 70)

        if expected >= 0:
            if len(comments) >= expected:
                print(
                    f"HOÀN TẤT COMMENTS: "
                    f"{len(comments)} / "
                    f"{expected}"
                )
            else:
                print(
                    f"COMMENTS THU ĐƯỢC: "
                    f"{len(comments)} / "
                    f"{expected}"
                )
                print(
                    "[!] Chưa thể khẳng định "
                    "đã thu đủ comments."
                )

        else:
            print(
                f"COMMENTS THU ĐƯỢC: "
                f"{len(comments)}"
            )

        print("=" * 70)

        return comments

    # ============================================================
    # PUBLIC: COMMENTS
    # ============================================================

    def get_post_comments(
        self,
        post_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not self.ensure_login():
            return []

        try:
            limit = max(1, int(limit))
        except Exception:
            limit = 100

        return self._collect_post_comments(
            post_id=str(post_id),
            max_comments=limit,
            max_rounds=20,
        )


# =================================================================
# STANDALONE TEST
# =================================================================

def _print_post(post: dict[str, Any]):
    print()
    print("-" * 70)
    print("POST")
    print("-" * 70)

    for key in (
        "post_id",
        "group_id",
        "post_url",
        "author_name",
        "created_time",
        "likes",
        "comments",
        "shares",
    ):
        print(
            f"{key:15}: "
            f"{post.get(key, '')}"
        )

    print(
        f"{'content':15}: "
        f"{post.get('content', '')}"
    )


def _print_comment(comment: dict[str, Any]):
    print()
    print("-" * 70)
    print("COMMENT")
    print("-" * 70)

    for key in (
        "comment_id",
        "post_id",
        "comment_url",
        "author_name",
        "created_time",
        "reactions",
        "replies",
    ):
        print(
            f"{key:15}: "
            f"{comment.get(key, '')}"
        )

    print(
        f"{'content':15}: "
        f"{comment.get('content', '')}"
    )


def main():
    # Fix Unicode console trên Windows.
    try:
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
        sys.stderr.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        pass

    print("=" * 70)
    print("FACEBOOK BROWSER COLLECTOR TEST")
    print("=" * 70)

    group = input(
        "Nhập Group URL hoặc Group ID: "
    ).strip()

    if not group:
        print("[!] Group không được để trống.")
        return

    try:
        max_posts = int(
            input(
                "Số posts cần lấy [10]: "
            ).strip()
            or "10"
        )
    except ValueError:
        max_posts = 10

    try:
        max_comments = int(
            input(
                "Số comments cần lấy [100]: "
            ).strip()
            or "100"
        )
    except ValueError:
        max_comments = 100

    client = FacebookBrowserClient()

    try:
        if not client.ensure_login():
            print(
                "[!] Chưa đăng nhập Facebook."
            )
            return

        # --------------------------------------------------------
        # POSTS
        # --------------------------------------------------------

        posts = client.get_group_posts(
            group,
            limit=max_posts,
        )

        print()
        print("=" * 70)
        print(
            f"POSTS: {len(posts)}"
        )
        print("=" * 70)

        for index, post in enumerate(
            posts,
            start=1,
        ):
            print()
            print(
                f"[{index}] "
                f"{post['post_id']} | "
                f"{post['author_name']} | "
                f"R={post['likes']} "
                f"C={post['comments']} "
                f"S={post['shares']}"
            )
            print(
                f"URL: {post['post_url']}"
            )
            print(
                f"CONTENT: "
                f"{post['content'][:200]}"
            )

        if not posts:
            print(
                "[!] Không lấy được post nào."
            )
            return

        # --------------------------------------------------------
        # SELECT POST
        # --------------------------------------------------------

        print()
        print("=" * 70)
        print("CHỌN POST ĐỂ TEST COMMENTS")
        print("=" * 70)

        for index, post in enumerate(
            posts,
            start=1,
        ):
            print(
                f"{index}. "
                f"{post['post_id']} - "
                f"{post['content'][:80]}"
            )

        try:
            choice = int(
                input(
                    "Chọn số post [1]: "
                ).strip()
                or "1"
            )
        except ValueError:
            choice = 1

        if (
            choice < 1
            or choice > len(posts)
        ):
            print(
                "[!] Lựa chọn không hợp lệ."
            )
            return

        selected_post = posts[
            choice - 1
        ]

        post_id = selected_post[
            "post_id"
        ]

        # --------------------------------------------------------
        # COMMENTS
        # --------------------------------------------------------

        # Điều hướng lại chính xác tới post.
        post_url = selected_post[
            "post_url"
        ]

        page = client._ensure_browser()

        try:
            page.goto(
                post_url,
                wait_until="domcontentloaded",
                timeout=30000,
            )
        except Exception:
            pass

        client._wait_page(3500)

        comments = client.get_post_comments(
            post_id,
            limit=max_comments,
        )

        print()
        print("=" * 70)
        print(
            f"COMMENTS: {len(comments)}"
        )
        print("=" * 70)

        for index, comment in enumerate(
            comments,
            start=1,
        ):
            print()
            print(
                f"[{index}] "
                f"{comment['comment_id']} | "
                f"{comment['author_name']} | "
                f"R={comment['reactions']} "
                f"Replies={comment['replies']}"
            )
            print(
                f"CONTENT: "
                f"{comment['content'][:200]}"
            )
            print(
                f"URL: "
                f"{comment['comment_url']}"
            )

    finally:
        client.close()

if __name__ == "__main__":
    main()