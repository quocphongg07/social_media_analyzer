from .client import FacebookClient


class MockFacebookClient(FacebookClient):

    def get_group(self, group_id: str) -> dict:

        return {
            "group_id": group_id,
            "name": "Demo Facebook Group",
            "url": f"https://www.facebook.com/groups/{group_id}",
        }

    def get_group_posts(
        self,
        group_id: str,
        limit: int = 100,
    ) -> list[dict]:

        posts = [
            {
                "post_id": "post_001",
                "group_id": group_id,
                "post_url": "https://facebook.com/post_001",
                "author_name": "Nguyen Van A",
                "content": "Bài viết có nhiều tương tác nhất.",
                "created_time": "2026-09-10 08:00:00",
                "likes": 1500,
                "comments": 320,
                "shares": 180,
            },
            {
                "post_id": "post_002",
                "group_id": group_id,
                "post_url": "https://facebook.com/post_002",
                "author_name": "Tran Thi B",
                "content": "Một bài viết khác trong Group.",
                "created_time": "2026-09-10 09:30:00",
                "likes": 800,
                "comments": 500,
                "shares": 50,
            },
            {
                "post_id": "post_003",
                "group_id": group_id,
                "post_url": "https://facebook.com/post_003",
                "author_name": "Le Van C",
                "content": "Bài viết có lượng chia sẻ cao.",
                "created_time": "2026-09-10 10:00:00",
                "likes": 400,
                "comments": 100,
                "shares": 600,
            },
        ]

        return posts[:limit]

    def get_post(
        self,
        post_id: str,
    ) -> dict:

        return {
            "post_id": post_id,
            "group_id": "123456789",
            "post_url": f"https://facebook.com/{post_id}",
            "author_name": "Nguyen Van A",
            "content": "Đây là bài viết mẫu.",
            "created_time": "2026-09-10 08:00:00",
            "likes": 1500,
            "comments": 320,
            "shares": 180,
        }

    def get_post_comments(
        self,
        post_id: str,
        limit: int = 100,
    ) -> list[dict]:

        comments = [
            {
                "comment_id": "comment_001",
                "post_id": post_id,
                "comment_url": "https://facebook.com/comment_001",
                "author_name": "User A",
                "content": "Bình luận nhận nhiều reaction.",
                "created_time": "2026-09-10 08:10:00",
                "reactions": 800,
                "replies": 120,
            },
            {
                "comment_id": "comment_002",
                "post_id": post_id,
                "comment_url": "https://facebook.com/comment_002",
                "author_name": "User B",
                "content": "Bình luận có nhiều phản hồi.",
                "created_time": "2026-09-10 08:20:00",
                "reactions": 300,
                "replies": 500,
            },
            {
                "comment_id": "comment_003",
                "post_id": post_id,
                "comment_url": "https://facebook.com/comment_003",
                "author_name": "User C",
                "content": "Bình luận thông thường.",
                "created_time": "2026-09-10 08:30:00",
                "reactions": 100,
                "replies": 20,
            },
        ]

        return comments[:limit]