from typing import Literal
from urllib.parse import quote


def content_disposition(
    disposition: Literal["inline", "attachment"], filename: str | None
) -> str:
    """A Content-Disposition value that's safe for any uploaded filename.

    Header values must be Latin-1 and the quoted `filename` can't contain `"`,
    `\\` or control characters, so it gets an ASCII fallback, plus the exact
    name as UTF-8 in `filename*` (RFC 6266 / RFC 5987) when they differ.
    """
    if not filename:
        return disposition

    fallback = "".join(
        char if 32 <= ord(char) < 127 and char not in '"\\' else "_"
        for char in filename
    )
    value = f'{disposition}; filename="{fallback}"'
    if fallback != filename:
        value += f"; filename*=UTF-8''{quote(filename, safe='')}"
    return value
