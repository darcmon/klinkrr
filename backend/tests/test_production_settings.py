import pytest

from backend.config import Settings

SAFE = dict(
    environment="production",
    secret_key="x" * 48,
    allowed_origins="https://app.klinkrr.com",
    frontend_url="https://app.klinkrr.com",
    database_url="postgresql+asyncpg://klinkrr:s3cret@db.internal:5432/klinkrr",
    aws_access_key_id="key",
    aws_secret_access_key="secret",
)


def settings(**overrides):
    # _env_file=None: ignore the developer's local .env.
    return Settings(_env_file=None, **{**SAFE, **overrides})


def test_safe_production_settings_have_no_problems():
    assert settings().production_problems() == []


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"secret_key": "changemelater"}, "SECRET_KEY"),
        ({"secret_key": "short"}, "SECRET_KEY"),
        ({"allowed_origins": "https://app.klinkrr.com, http://localhost:5173"}, "ALLOWED_ORIGINS"),
        ({"allowed_origins": "http://app.klinkrr.com"}, "ALLOWED_ORIGINS"),
        ({"frontend_url": "http://app.klinkrr.com"}, "FRONTEND_URL"),
        ({"database_url": "postgresql+asyncpg://klinkrr:localdev@localhost/klinkrr"}, "DATABASE_URL"),
        ({"aws_secret_access_key": ""}, "AWS_"),
    ],
)
def test_each_unsafe_setting_is_reported(override, fragment):
    problems = settings(**override).production_problems()

    assert len(problems) == 1
    assert fragment in problems[0]


def test_development_is_the_default():
    assert Settings(_env_file=None).is_production is False


@pytest.mark.parametrize(
    "url",
    [
        "postgres://u:p@dpg-abc-a/klinkrr",
        "postgresql://u:p@dpg-abc-a/klinkrr",
        "postgresql+asyncpg://u:p@dpg-abc-a/klinkrr",
    ],
)
def test_database_url_uses_asyncpg(url):
    assert Settings(_env_file=None, database_url=url).database_url == (
        "postgresql+asyncpg://u:p@dpg-abc-a/klinkrr"
    )


def test_neon_style_ssl_options_are_translated_for_asyncpg():
    url = (
        "postgresql://u:p@ep-x.eu-central-1.aws.neon.tech/klinkrr"
        "?sslmode=require&channel_binding=require"
    )
    assert Settings(_env_file=None, database_url=url).database_url == (
        "postgresql+asyncpg://u:p@ep-x.eu-central-1.aws.neon.tech/klinkrr?ssl=require"
    )
