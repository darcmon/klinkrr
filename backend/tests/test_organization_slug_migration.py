import runpy
from pathlib import Path


MIGRATION = runpy.run_path(
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "0006_add_organization_slugs.py"
)

slugify = MIGRATION["_slugify"]
unique_slug = MIGRATION["_unique_slug"]


def test_organization_slug_generation_handles_edge_cases():
    assert slugify("Montréal Docs") == "montreal-docs"

    used: set[str] = set()

    assert unique_slug("Admin", used) == "admin-org"
    assert unique_slug("!!!", used) == "organization"
    assert unique_slug("!!!", used) == "organization-2"
    assert unique_slug("Acme", used) == "acme"
    assert unique_slug("Acme", used) == "acme-2"

    long_slug = unique_slug("a" * 120, used)
    assert len(long_slug) <= 100
