import pytest
from starlette.responses import Response

from backend.services.content_disposition import content_disposition


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("handbook.pdf", 'inline; filename="handbook.pdf"'),
        (None, "inline"),
        (
            'my "final" menu.pdf',
            'inline; filename="my _final_ menu.pdf"; '
            "filename*=UTF-8''my%20%22final%22%20menu.pdf",
        ),
        (
            "menú 🍕.pdf",
            'inline; filename="men_ _.pdf"; '
            "filename*=UTF-8''men%C3%BA%20%F0%9F%8D%95.pdf",
        ),
        (
            "a\\b\r\nX-Injected: 1.pdf",
            'inline; filename="a_b__X-Injected: 1.pdf"; '
            "filename*=UTF-8''a%5Cb%0D%0AX-Injected%3A%201.pdf",
        ),
    ],
)
def test_content_disposition(filename, expected):
    assert content_disposition("inline", filename) == expected


@pytest.mark.parametrize("filename", ['q"uote.pdf', "menú 🍕.pdf", "x\r\ny.pdf"])
def test_value_is_always_a_valid_header(filename):
    # Starlette encodes header values as Latin-1; this raised for non-ASCII
    # names before, turning the download into a server error.
    value = content_disposition("attachment", filename)
    response = Response(headers={"Content-Disposition": value})

    assert response.headers["content-disposition"] == value
    assert "\r" not in value and "\n" not in value
