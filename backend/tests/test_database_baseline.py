"""Run against a migrated disposable database using PHASE1_TEST_DATABASE_URL."""
import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from backend.models import (
    AdminUser,
    AuditLog,
    FileVersion,
    Location,
    Membership,
    Organization,
)


@pytest.mark.asyncio
async def test_database_enforces_version_payloads():
    url = os.environ.get("PHASE1_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires a migrated disposable PostgreSQL database")
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            location_id = uuid.uuid4()
            organization_id = uuid.uuid4()
            user_id = uuid.uuid4()
            await connection.execute(insert(Organization).values(
                id=organization_id, name="Test"
            ))
            await connection.execute(insert(AdminUser).values(
                id=user_id, email=f"{user_id}@example.com", display_name="Test"
            ))
            await connection.execute(insert(Location).values(
                id=location_id, slug=str(location_id), display_name="Test",
                organization_id=organization_id,
            ))
            file_payload = dict(original_filename="test.pdf", content_type="application/pdf",
                                file_size_bytes=1, s3_key="test.pdf")
            link_payload = dict(kind="link", link_url="https://example.com", link_mode="redirect")
            # Default kind keeps existing file uploads compatible.
            for number, payload in enumerate([file_payload, link_payload], 1):
                await connection.execute(insert(FileVersion).values(
                    location_id=location_id, uploaded_by="test", uploaded_by_id=user_id,
                    version_number=number,
                    **payload
                ))
            assert await connection.scalar(select(FileVersion.kind).where(
                FileVersion.location_id == location_id, FileVersion.version_number == 1
            )) == "file"
            invalid = [
                {}, {**file_payload, "s3_key": None},
                {**file_payload, "link_url": "https://example.com"},
                {**file_payload, "kind": "unknown"},
                {**link_payload, "link_url": None},
                {**link_payload, "link_url": "   "},
                {**link_payload, "link_mode": None},
                {**link_payload, "link_mode": "proxy"},
                {**link_payload, "s3_key": "unexpected"},
                {**file_payload, "status": "invalid"},
            ]
            for payload in invalid:
                with pytest.raises(IntegrityError):
                    async with connection.begin_nested():
                        await connection.execute(insert(FileVersion).values(
                            location_id=location_id, uploaded_by="test", uploaded_by_id=user_id,
                    version_number=3,
                            **payload
                        ))
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(Location.__table__.update().where(
                        Location.id == location_id
                    ).values(current_approved_version_id=uuid.uuid4()))
            await connection.execute(insert(AuditLog).values(
                action="test", entity_type="location", entity_id=location_id,
                created_at=datetime.now(timezone.utc)
            ))
            await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_database_enforces_organization_and_identity_constraints():
    url = os.environ.get("PHASE1_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires a migrated disposable PostgreSQL database")
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            organization_id = uuid.uuid4()
            user_id = uuid.uuid4()
            location_id = uuid.uuid4()
            await connection.execute(insert(Organization).values(
                id=organization_id, name="Test"
            ))
            await connection.execute(insert(AdminUser).values(
                id=user_id, email=f"{user_id}@example.com", display_name="Test"
            ))
            await connection.execute(insert(Location).values(
                id=location_id, slug=str(location_id), display_name="Test",
                organization_id=organization_id,
            ))
            assert await connection.scalar(
                select(Location.required_approvals).where(Location.id == location_id)
            ) == 1
            assert await connection.scalar(
                select(Organization.allow_self_approval).where(
                    Organization.id == organization_id
                )
            ) is True

            await connection.execute(insert(Membership).values(
                organization_id=organization_id, user_id=user_id, role="uploader"
            ))

            link = dict(kind="link", link_url="https://example.com", link_mode="redirect")
            invalid = [
                insert(Membership).values(
                    organization_id=organization_id, user_id=user_id, role="owner"
                ),  # one membership per user and organization
                insert(Membership).values(
                    organization_id=uuid.uuid4(), user_id=user_id, role="owner"
                ),
                insert(Location).values(
                    id=uuid.uuid4(), slug=str(uuid.uuid4()), display_name="No org"
                ),
                insert(Location).values(
                    id=uuid.uuid4(), slug=str(uuid.uuid4()), display_name="Negative",
                    organization_id=organization_id, required_approvals=-1,
                ),
                insert(FileVersion).values(
                    location_id=location_id, uploaded_by="test", version_number=1, **link
                ),
                insert(FileVersion).values(
                    location_id=location_id, uploaded_by="test",
                    uploaded_by_id=uuid.uuid4(), version_number=1, **link
                ),
            ]
            for statement in invalid:
                with pytest.raises(IntegrityError):
                    async with connection.begin_nested():
                        await connection.execute(statement)

            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(Membership.__table__.update().where(
                        Membership.user_id == user_id
                    ).values(role="superuser"))
            await transaction.rollback()
    finally:
        await engine.dispose()
