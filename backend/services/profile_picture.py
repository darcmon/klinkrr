"""Optional provider pictures; failure must never prevent sign-in."""
import base64
from urllib.parse import urlsplit

import httpx


async def get_profile_picture(provider: str, info: dict, token: dict) -> str | None:
    if provider == "google":
        picture = info.get("picture")
        if not isinstance(picture, str):
            return None
        try:
            parsed = urlsplit(picture)
            if parsed.scheme == "https" and parsed.hostname and not parsed.username:
                return picture
        except ValueError:
            pass
        return None

    access_token = token.get("access_token")
    if provider != "microsoft" or not access_token:
        return None
    try:
        # Fetch a small photo on the server; never send the Graph token to the browser.
        async with httpx.AsyncClient(timeout=3.0) as client:
            async with client.stream(
                "GET", "https://graph.microsoft.com/v1.0/me/photos/48x48/$value",
                headers={"Authorization": f"Bearer {access_token}"},
            ) as response:
                if response.status_code != 200:
                    return None
                content_type = response.headers.get("content-type", "").split(";")[0].lower()
                if content_type not in {"image/jpeg", "image/png", "image/webp"}:
                    return None
                photo = bytearray()
                async for chunk in response.aiter_bytes():
                    photo.extend(chunk)
                    if len(photo) > 100_000:
                        return None
                if not photo:
                    return None
                encoded = base64.b64encode(photo).decode("ascii")
                return f"data:{content_type};base64,{encoded}"
    except httpx.HTTPError:
        return None
