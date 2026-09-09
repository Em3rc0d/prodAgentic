from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from application.quality.integrity import evaluate_owned_asset_bytes
from application.quality.policy import build_qa_report
from db.mongo import _ensure_mk1_production_indexes
from domain.production.models import (
    ContentRevisionV1,
    GenerationRunState,
    GenerationRunV1,
    RevisionSource,
    RevisionStatus,
)
from domain.quality.models import QAVerdict
from domain.rendering.models import AssetV1
from domain.tenants.models import TenantContext
from infrastructure.mongo.production import MongoProductionRepository
from infrastructure.mongo.quality import MongoQualityRepository


NOW = datetime(2026, 9, 9, 4, 30, tzinfo=timezone.utc)


async def _ensure_quality_indexes(db):
    await db["qa_reports"].create_index(
        [("tenant_id", 1), ("qa_report_id", 1)], unique=True, name="tenant_qa_report_unique"
    )
    await db["qa_reports"].create_index(
        [("tenant_id", 1), ("revision_id", 1), ("created_at", -1)], name="tenant_revision_qa_reports"
    )


def make_run_revision():
    run = GenerationRunV1(
        run_id="run-s6-mongo", tenant_id="tenant-s6-a", content_id="content-s6",
        profile_id="profile-s6", profile_version=1, profile_snapshot_digest="a" * 64,
        plan_id="plan-s6", plan_digest="b" * 64, state=GenerationRunState.QA,
        contract_versions=("ContentSpecV1@1", "VisualSpecV1@1", "RenderResultV1@1"),
        content_spec_ref="content-spec-s6", visual_spec_ref="visual-spec-s6", started_at=NOW,
    )
    revision = ContentRevisionV1(
        revision_id="revision-s6", tenant_id=run.tenant_id, content_id=run.content_id, run_id=run.run_id,
        source=RevisionSource.GENERATION, content_spec_ref=run.content_spec_ref,
        content_spec_digest="c" * 64, visual_spec_ref=run.visual_spec_ref, visual_spec_digest="d" * 64,
        asset_refs=("asset-s6",), status=RevisionStatus.QA_PENDING, created_at=NOW,
    )
    return run, revision


def make_report(*, verdict_fail: bool = False):
    from domain.quality.models import QACheckLayer, QACheckV1, QASeverity, RecoveryAction

    checks = () if not verdict_fail else (
        QACheckV1(
            code="visual.clipping.p0", layer=QACheckLayer.VISUAL, severity=QASeverity.BLOCKING,
            passed=False, message="clipping", recovery_hint=RecoveryAction.LAYOUT_RECOMPOSE,
        ),
    )
    return build_qa_report(
        qa_report_id="qa-s6", tenant_id="tenant-s6-a", revision_id="revision-s6",
        content_spec_digest="c" * 64, render_input_digest="e" * 64,
        asset_digests=("f" * 64,), deterministic_checks=(), semantic_checks=(), visual_checks=checks,
        created_at=NOW,
    )


def test_owned_asset_bytes_revalidate_exact_size_and_sha256():
    data = b"real-owned-render-bytes"
    asset = AssetV1(
        asset_id="asset-bytes", tenant_id="tenant-s6-a", revision_id="revision-s6",
        render_id="render-s6", visual_spec_id="visual-spec-s6", page_id="page-0", page_index=0,
        content_type="image/png", width=1080, height=1350, byte_size=len(data),
        storage_key="renders/t-aaaaaaaa/r-bbbbbbbb/x-cccccccc/page-00.png",
        sha256=hashlib.sha256(data).hexdigest(), render_input_digest="1" * 64, created_at=NOW,
    )
    good = evaluate_owned_asset_bytes(asset, data)
    assert all(check.passed for check in good)
    bad = evaluate_owned_asset_bytes(asset, data + b"tamper")
    assert [check.passed for check in bad] == [False, False]


@pytest.mark.asyncio
async def test_real_mongodb_s6_qa_authority_survives_restart_is_tenant_scoped_and_recovers_crash_boundary():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real S6 quality gate")

    database_name = f"prodagentic_s6_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        await _ensure_mk1_production_indexes(db)
        await _ensure_quality_indexes(db)
        context = TenantContext(tenant_id="tenant-s6-a", actor_id="operator-s6-a")
        production = MongoProductionRepository(db, context)
        quality = MongoQualityRepository(db, context)
        run, revision = make_run_revision()
        await production.create_run(run)
        await production.save_revision(revision)

        report = make_report()
        assert report.verdict == QAVerdict.PASS
        await quality.save_report(report)

        # First half of the transition: a process may die after revision becomes REVIEWABLE.
        reviewable = await quality.mark_revision_reviewable(
            revision_id=revision.revision_id, qa_report=report,
            expected_asset_refs=revision.asset_refs,
            expected_content_spec_digest=revision.content_spec_digest,
            expected_visual_spec_digest=revision.visual_spec_digest,
        )
        assert reviewable is not None and reviewable.status == RevisionStatus.REVIEWABLE
        assert reviewable.qa_report_id == report.qa_report_id

        # Reopen adapters to simulate restart, then safely finish the run.
        reopened = MongoQualityRepository(db, context)
        assert await reopened.get_report(context.tenant_id, report.qa_report_id) == report
        replay = await reopened.mark_revision_reviewable(
            revision_id=revision.revision_id, qa_report=report,
            expected_asset_refs=revision.asset_refs,
            expected_content_spec_digest=revision.content_spec_digest,
            expected_visual_spec_digest=revision.visual_spec_digest,
        )
        assert replay == reviewable
        completed = await reopened.finish_run_completed(
            run_id=run.run_id, revision_id=revision.revision_id, qa_report_id=report.qa_report_id
        )
        assert completed is not None and completed.state == GenerationRunState.COMPLETED
        assert report.qa_report_id in completed.qa_report_refs
        assert completed.completed_at is not None
        assert await reopened.finish_run_completed(
            run_id=run.run_id, revision_id=revision.revision_id, qa_report_id=report.qa_report_id
        ) == completed

        other = MongoQualityRepository(db, TenantContext(tenant_id="tenant-s6-b", actor_id="operator-s6-b"))
        assert await other.get_report("tenant-s6-b", report.qa_report_id) is None
    finally:
        await client.drop_database(database_name)
        client.close()


@pytest.mark.asyncio
async def test_real_mongodb_s6_cas_rejects_stale_assets_and_fail_verdict():
    uri = os.environ.get("MONGO_TEST_URI")
    if not uri:
        pytest.skip("MONGO_TEST_URI is required for the real S6 CAS gate")

    database_name = f"prodagentic_s6_cas_{uuid4().hex}"
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[database_name]
    try:
        await client.admin.command("ping")
        await _ensure_mk1_production_indexes(db)
        await _ensure_quality_indexes(db)
        context = TenantContext(tenant_id="tenant-s6-a", actor_id="operator-s6-a")
        production = MongoProductionRepository(db, context)
        quality = MongoQualityRepository(db, context)
        run, revision = make_run_revision()
        await production.create_run(run)
        await production.save_revision(revision)

        report = make_report()
        await quality.save_report(report)
        stale = await quality.mark_revision_reviewable(
            revision_id=revision.revision_id, qa_report=report,
            expected_asset_refs=("asset-stale",),
            expected_content_spec_digest=revision.content_spec_digest,
            expected_visual_spec_digest=revision.visual_spec_digest,
        )
        assert stale is None
        persisted = await production.get_revision(context.tenant_id, revision.revision_id)
        assert persisted is not None and persisted.status == RevisionStatus.QA_PENDING

        failing = make_report(verdict_fail=True).model_copy(update={"qa_report_id": "qa-s6-fail"})
        # Rebuild digest after changing identity so the repository rejects only on verdict, not integrity.
        failing = build_qa_report(
            qa_report_id="qa-s6-fail", tenant_id="tenant-s6-a", revision_id="revision-s6",
            content_spec_digest="c" * 64, render_input_digest="e" * 64, asset_digests=("f" * 64,),
            deterministic_checks=failing.deterministic_checks, semantic_checks=failing.semantic_checks,
            visual_checks=failing.visual_checks, created_at=NOW,
        )
        await quality.save_report(failing)
        with pytest.raises(ValueError, match="failing QAReportV1"):
            await quality.mark_revision_reviewable(
                revision_id=revision.revision_id, qa_report=failing,
                expected_asset_refs=revision.asset_refs,
                expected_content_spec_digest=revision.content_spec_digest,
                expected_visual_spec_digest=revision.visual_spec_digest,
            )
    finally:
        await client.drop_database(database_name)
        client.close()
