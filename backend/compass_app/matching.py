import logging

from django.db import transaction

from notifications import emails

from .engine import Buddy as EngineBuddy
from .engine import Joiner as EngineJoiner
from .engine import MatchSettings, run_match
from .models import AuditLog, Buddy, Joiner, MatchRun, Response, Settings

logger = logging.getLogger(__name__)


def load_match_settings() -> MatchSettings:
    s = Settings.load()
    return MatchSettings(
        close_gap=s.close_gap, strong_threshold=s.strong_threshold,
        good_threshold=s.good_threshold, weaker_threshold=s.weaker_threshold,
        amber_gap=s.amber_gap, red_gap=s.red_gap,
        candidates_per_tier=s.candidates_per_tier, old_answers_months=s.old_answers_months,
    )


def latest_buddy_responses() -> dict:
    """buddy pk -> that buddy's most recent submitted CMP-BD response."""
    latest = {}
    submitted = (
        Response.objects.filter(assessment_code=Response.Code.BUDDY, submitted_at__isnull=False)
        .select_related("question_set")
        .order_by("submitted_at")
    )
    for r in submitted:
        latest[r.buddy_id] = r
    return latest


def build_pool(joiner: Joiner) -> list:
    responses = latest_buddy_responses()
    pool = []
    for buddy in Buddy.objects.all():
        resp = responses.get(buddy.pk)
        if resp is None:
            continue
        pool.append(EngineBuddy(
            id=buddy.employee_id, name=buddy.name, department=buddy.department,
            location=buddy.location, answers=resp.answers(),
            version=resp.question_set.version,
            pool_active=buddy.pool_status == Buddy.PoolStatus.ACTIVE,
            manager_id=buddy.manager_id, completed_at=resp.submitted_at.date(),
            total_joiners=buddy.total_joiners_buddied, active_joiners=buddy.active_joiners,
        ))
    return pool


def run_match_for_joiner(joiner: Joiner) -> MatchRun:
    resp = joiner.submitted_response()
    if resp is None:
        raise ValueError(f"{joiner.name} has not submitted CMP-NJ yet.")

    # Skip-level managers need the HRMS manager chain; for now only the direct manager is known.
    chain = tuple(m for m in (joiner.reporting_manager_id,) if m)
    engine_joiner = EngineJoiner(
        id=str(joiner.pk), department=joiner.department, location=joiner.location,
        answers=resp.answers(), version=resp.question_set.version,
        manager_id=joiner.reporting_manager_id, manager_chain=chain,
    )
    result = run_match(engine_joiner, build_pool(joiner), load_match_settings())

    with transaction.atomic():
        run = MatchRun.objects.create(
            joiner=joiner, tier_reached=result.tier_reached, results=result.to_dict(),
        )
        open_states = (
            Joiner.Status.AWAITING_ASSESSMENT, Joiner.Status.AWAITING_PAIRING, Joiner.Status.MANUAL,
        )
        if joiner.compass_status in open_states:
            joiner.compass_status = (
                Joiner.Status.MANUAL if result.tier_reached == "MANUAL"
                else Joiner.Status.AWAITING_PAIRING
            )
            joiner.save(update_fields=["compass_status"])
        AuditLog.record("match_run", joiner, after={"run_id": run.pk, "tier_reached": result.tier_reached})

    # No Strong or Good match: tell the admins. A failed email must not undo the match run.
    if result.tier_reached in ("FALLBACK", "MANUAL"):
        try:
            emails.alert_no_good_match(joiner, result.tier_reached, run.pk)
        except Exception:
            logger.exception("Could not send the no-match alert for joiner %s", joiner.pk)
    return run