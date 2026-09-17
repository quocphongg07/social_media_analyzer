from config.settings import settings
from facebook.api_client import (
    FacebookApiClient,
    FacebookApiError,
)

def main():
    print("=" * 60)
    print("FACEBOOK GROUP API TEST")
    print("=" * 60)

    if not settings.FACEBOOK_ACCESS_TOKEN:
        print("❌ Chưa cấu hình Access Token.")
        return

    group_id = input(
        "Nhập Group ID cần kiểm tra: "
    ).strip()

    if not group_id:
        print("❌ Group ID không được để trống.")
        return

    try:
        client = FacebookApiClient()

        print()
        print("Đang kiểm tra Group...")
        print("Group ID:", group_id)

        group = client.get_group(group_id)

        print()
        print("✅ CÓ THỂ TRUY CẬP GROUP")

        print("ID:", group.get("group_id"))
        print("Tên:", group.get("name"))
        print("URL:", group.get("url"))

    except FacebookApiError as exc:
        print()
        print("❌ FACEBOOK API ERROR")
        print(exc)

    except Exception as exc:
        print()
        print("❌ LỖI")
        print(exc)

    print("=" * 60)


if __name__ == "__main__":
    main()