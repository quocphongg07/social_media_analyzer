import requests

from config.settings import settings


def main():
    print("=" * 60)
    print("FACEBOOK GRAPH API TEST")
    print("=" * 60)

    if not settings.FACEBOOK_ACCESS_TOKEN:
        print("❌ Chưa cấu hình FACEBOOK_ACCESS_TOKEN")
        return

    print("✓ Access Token: ĐÃ CẤU HÌNH")
    print(
        "✓ Graph API Version:",
        settings.FACEBOOK_GRAPH_API_VERSION,
    )

    url = (
        f"{settings.FACEBOOK_API_BASE_URL}/"
        f"{settings.FACEBOOK_GRAPH_API_VERSION}/me"
    )

    params = {
        "fields": "id,name",
        "access_token": settings.FACEBOOK_ACCESS_TOKEN,
    }

    print()
    print("Đang gọi Graph API...")
    print("Endpoint:", url)

    try:
        response = requests.get(
            url,
            params=params,
            timeout=30,
        )

        data = response.json()

    except requests.RequestException as exc:
        print()
        print("❌ Lỗi kết nối:")
        print(exc)
        return

    except ValueError:
        print()
        print("❌ Facebook không trả về JSON.")
        print(response.text)
        return

    print()

    if response.status_code >= 400:
        print("❌ API ERROR")
        print("HTTP Status:", response.status_code)

        error = data.get("error", {})

        print(
            "Message:",
            error.get(
                "message",
                "Unknown error",
            ),
        )

        print(
            "Code:",
            error.get(
                "code",
                "unknown",
            ),
        )

        print(
            "Type:",
            error.get(
                "type",
                "unknown",
            ),
        )

        return

    print("✅ GRAPH API HOẠT ĐỘNG")

    print(
        "User ID:",
        data.get("id"),
    )

    print(
        "User Name:",
        data.get("name"),
    )

    print("=" * 60)


if __name__ == "__main__":
    main()