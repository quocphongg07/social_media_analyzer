from abc import ABC, abstractmethod
from typing import Any


class FacebookClient(ABC):
    """
    Interface chung cho nguồn dữ liệu Facebook.

    Các service phía trên chỉ làm việc với interface này,
    không phụ thuộc trực tiếp vào cách lấy dữ liệu.
    """

    @abstractmethod
    def get_group(self, group_id: str) -> dict[str, Any]:
        """
        Lấy thông tin Group.
        """
        raise NotImplementedError

    @abstractmethod
    def get_group_posts(
        self,
        group_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Lấy danh sách bài viết của Group.
        """
        raise NotImplementedError

    @abstractmethod
    def get_post(
        self,
        post_id: str,
    ) -> dict[str, Any]:
        """
        Lấy thông tin một bài viết.
        """
        raise NotImplementedError

    @abstractmethod
    def get_post_comments(
        self,
        post_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Lấy danh sách bình luận của bài viết.
        """
        raise NotImplementedError