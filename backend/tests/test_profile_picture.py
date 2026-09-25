from unittest.mock import patch

import httpx
import pytest

from backend.services.profile_picture import get_profile_picture


@pytest.mark.asyncio
@pytest.mark.parametrize('info,expected', [
    ({'picture': 'https://example.com/avatar.jpg'}, 'https://example.com/avatar.jpg'),
    ({}, None),
    ({'picture': 'javascript:alert(1)'}, None),
])
async def test_google_picture(info, expected):
    assert await get_profile_picture('google', info, {}) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('status,content_type,body,expected', [
    (200, 'image/jpeg', b'photo', 'data:image/jpeg;base64,cGhvdG8='),
    (404, 'application/json', b'{}', None),
    (403, 'application/json', b'{}', None),
    (200, 'text/html', b'error', None),
    (200, 'image/jpeg', b'x' * 100_001, None),
])
async def test_microsoft_picture(status, content_type, body, expected):
    def respond(request):
        assert request.headers['Authorization'] == 'Bearer test-token'
        return httpx.Response(status, headers={'content-type': content_type}, content=body)

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    with patch('backend.services.profile_picture.httpx.AsyncClient', return_value=client):
        assert await get_profile_picture('microsoft', {}, {'access_token': 'test-token'}) == expected


@pytest.mark.asyncio
async def test_photo_timeout_does_not_block_login():
    def respond(request):
        raise httpx.ReadTimeout('timeout', request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    with patch('backend.services.profile_picture.httpx.AsyncClient', return_value=client):
        assert await get_profile_picture('microsoft', {}, {'access_token': 'test-token'}) is None
