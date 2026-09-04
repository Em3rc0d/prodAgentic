"""Run/verify the S0 bootstrap-tenant migration against configured MongoDB."""

import asyncio
import json

from application.tenancy.bootstrap import migrate_bootstrap_tenant
from db.mongo import close_db, connect_db, get_db


async def main() -> None:
    await connect_db(run_bootstrap_migration=False)
    db = get_db()
    if db is None:
        raise SystemExit("MongoDB unavailable; bootstrap migration was not run")
    try:
        report = await migrate_bootstrap_tenant(db)
        print(json.dumps({
            "migration": report.migration,
            "tenant_id": report.tenant_id,
            "matched_by_collection": report.matched_by_collection,
            "modified_by_collection": report.modified_by_collection,
            "missing_after_migration": report.missing_after_migration,
            "verified": report.verified,
            "completed_at": report.completed_at.isoformat(),
        }, sort_keys=True))
        if not report.verified:
            raise SystemExit("Bootstrap migration verification failed")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
