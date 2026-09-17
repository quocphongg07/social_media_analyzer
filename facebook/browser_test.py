from facebook.browser_client import FacebookBrowserClient


def main():

    print("=" * 60)
    print("FACEBOOK BROWSER COLLECTOR TEST")
    print("=" * 60)

    group_url = input(
        "Nhập Facebook Group URL: "
    ).strip()

    if not group_url:

        print(
            "❌ URL không được để trống."
        )

        return

    client = FacebookBrowserClient(
        profile_dir="data/browser_profile",
        headless=False,
        slow_mo=100,
        timeout=30_000,
    )

    try:

        # -----------------------------------------------------
        # Đăng nhập thủ công
        # -----------------------------------------------------

        client.open_facebook()

        # -----------------------------------------------------
        # Thu thập bài viết
        # -----------------------------------------------------

        posts = client.collect_group_posts(
            group_url=group_url,
            limit=20,
            max_scrolls=30,
            scroll_pause=3,
        )

        # -----------------------------------------------------
        # Kết quả
        # -----------------------------------------------------

        print()
        print("=" * 60)
        print("KẾT QUẢ")
        print("=" * 60)

        print(
            "Tổng số post:",
            len(posts),
        )

        for index, post in enumerate(
            posts,
            start=1,
        ):

            print()
            print(
                f"POST #{index}"
            )

            print(
                "ID:",
                post.get(
                    "post_id",
                    "",
                ),
            )

            print(
                "URL:",
                post.get(
                    "post_url",
                    "",
                ),
            )

            print(
                "Author:",
                post.get(
                    "author_name",
                    "",
                ),
            )

            print(
                "Time:",
                post.get(
                    "created_time",
                    "",
                ),
            )

            print(
                "Reactions:",
                post.get(
                    "likes",
                    0,
                ),
            )

            print(
                "Comments:",
                post.get(
                    "comments",
                    0,
                ),
            )

            print(
                "Shares:",
                post.get(
                    "shares",
                    0,
                ),
            )

            content = (
                post.get(
                    "content",
                    "",
                )
                or ""
            )

            print(
                "Content:",
                content[:500],
            )

    except KeyboardInterrupt:

        print(
            "\nĐã dừng bởi người dùng."
        )

    except Exception as exc:

        print()
        print("❌ ERROR")
        print(exc)

    finally:

        client.close()


if __name__ == "__main__":
    main()