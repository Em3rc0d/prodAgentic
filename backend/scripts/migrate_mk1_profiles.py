"""Run the additive MK0 ContentProfile -> MK1 ProfileVersion bridge."""

import asyncio
import json

from application.profiles.legacy_bridge import migrate_legacy_profiles
from application.tenancy.context import bootstrap_tenant_id
from db.mongo import close_db, connect_db, get_db


async def main() -> None:
    await connect_db(run_bootstrap_migration=True, run_profile_bridge=False)
    db = get_db()
    if db is None:
        raise SystemExit("MongoDB unavailable; Profile bridge was not run")
    try:
        report = await migrate_legacy_profiles(db, bootstrap_tenant_id())
        print(json.dumps(report.__dict__ | {"verified": report.verified}, sort_keys=True))
        if not report.verified:
            raise SystemExit("Profile bridge verification failed")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
