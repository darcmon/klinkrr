"""Delete public "access" audit events older than the retention period.

Every public link visit writes one, so they grow with traffic. Everything
else in the audit log (approvals, member changes, publishing) is kept.

Run it on a schedule, e.g. daily:

    python -m backend.scripts.prune_audit_logs            # uses AUDIT_ACCESS_RETENTION_DAYS
    python -m backend.scripts.prune_audit_logs --days 30
    python -m backend.scripts.prune_audit_logs --dry-run

Deletes in small batches, each in its own transaction, so it never holds
long locks on a large table.
"""

import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from backend.config import get_settings
from backend.db.session import engine

logger = logging.getLogger(__name__)

BATCH_SIZE = 5000

COUNT = text(
    "SELECT count(*) FROM audit_logs WHERE action = 'access' AND created_at < :cutoff"
)
DELETE_BATCH = text(
    """
    DELETE FROM audit_logs
    WHERE id IN (
        SELECT id FROM audit_logs
        WHERE action = 'access' AND created_at < :cutoff
        LIMIT :batch
    )
    """
)


async def prune(days: int, *, dry_run: bool = False, batch_size: int = BATCH_SIZE) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    if dry_run:
        async with engine.connect() as connection:
            return (await connection.execute(COUNT, {"cutoff": cutoff})).scalar_one()

    deleted = 0
    while True:
        async with engine.begin() as connection:
            result = await connection.execute(
                DELETE_BATCH, {"cutoff": cutoff, "batch": batch_size}
            )
        deleted += result.rowcount
        if result.rowcount < batch_size:
            return deleted


async def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--days",
        type=int,
        default=settings.audit_access_retention_days,
        help="keep access events newer than this many days "
        f"(default {settings.audit_access_retention_days})",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="count what would be deleted"
    )
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be at least 1")

    try:
        count = await prune(args.days, dry_run=args.dry_run)
    finally:
        await engine.dispose()

    verb = "Would delete" if args.dry_run else "Deleted"
    print(f"{verb} {count} access events older than {args.days} days.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
