"""COMPASS matching engine. Pure Python: no Django, no database."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

QUESTION_NAMES = ["Pace", "Communication", "Structure", "Social energy", "Learning"]

STRONG, GOOD, WEAKER, NOT_SUGGESTED = "Strong", "Good", "Weaker", "Not suggested"
RED, AMBER, INFO = "Red", "Amber", "Info"


@dataclass
class MatchSettings:
    close_gap: int = 1
    strong_threshold: int = 5
    good_threshold: int = 4
    weaker_threshold: int = 3
    amber_gap: int = 2
    red_gap: int = 3
    candidates_per_tier: int = 3
    old_answers_months: int = 12


@dataclass
class Joiner:
    id: str
    department: str
    location: str
    answers: list
    version: int = 1
    manager_id: str = ""
    manager_chain: tuple = ()  # (manager id, skip-level manager id, ...)


@dataclass
class Buddy:
    id: str
    name: str
    department: str
    location: str
    answers: list
    version: int = 1
    pool_active: bool = True
    manager_id: str = ""
    completed_at: date | None = None
    total_joiners: int = 0
    active_joiners: int = 0


@dataclass
class Flag:
    level: str
    code: str
    text: str
    question: int | None = None


@dataclass
class Candidate:
    buddy_id: str
    name: str
    department: str
    location: str
    tier: int
    answers: list
    gaps: list
    close_count: int
    total_gap: int
    largest_gap: int
    band: str
    total_joiners: int
    active_joiners: int
    completed_at: str
    flags: list = field(default_factory=list)


@dataclass
class MatchResult:
    tier_reached: str  # "1", "2", "3", "FALLBACK" or "MANUAL"
    shown: list  # top N for the tier reached
    more: list  # the rest ("Show more")
    tiers: dict  # {1: [...], 2: [...], 3: [...]} Strong/Good only, ranked (for "Expand search")
    weaker: list  # Weaker matches, tier order (the fallback)
    scored: list  # every eligible buddy incl. Not suggested (for manual search)

    def to_dict(self):
        return asdict(self)


def in_reporting_line(joiner: Joiner, buddy: Buddy) -> bool:
    if buddy.id in joiner.manager_chain:
        return True
    # a direct report of the joiner's manager in the same team
    return bool(buddy.manager_id) and buddy.manager_id == joiner.manager_id \
        and buddy.department == joiner.department


def is_eligible(joiner: Joiner, buddy: Buddy) -> bool:
    return (
        buddy.pool_active
        and buddy.version == joiner.version
        and len(buddy.answers) == 5
        and all(a is not None for a in buddy.answers)
        and not in_reporting_line(joiner, buddy)
    )


def band_for(close_count: int, s: MatchSettings) -> str:
    if close_count >= s.strong_threshold:
        return STRONG
    if close_count >= s.good_threshold:
        return GOOD
    if close_count >= s.weaker_threshold:
        return WEAKER
    return NOT_SUGGESTED


def score_answers(joiner_answers, buddy_answers, s: MatchSettings):
    gaps = [abs(j - b) for j, b in zip(joiner_answers, buddy_answers)]
    close = sum(1 for g in gaps if g <= s.close_gap)
    return gaps, close, sum(gaps), max(gaps), band_for(close, s)


def tier_of(joiner: Joiner, buddy: Buddy) -> int:
    if buddy.department == joiner.department:
        return 1 if buddy.location == joiner.location else 2
    return 3


def make_flags(joiner, buddy, gaps, band, s, today) -> list:
    flags = []
    for i, gap in enumerate(gaps):
        detail = f"{QUESTION_NAMES[i]}: joiner {joiner.answers[i]}, buddy {buddy.answers[i]}"
        if gap >= s.red_gap:
            flags.append(Flag(RED, "OPPOSITE", detail, i + 1))
        elif gap >= s.amber_gap:
            flags.append(Flag(AMBER, "STYLE_GAP", detail, i + 1))
    if band == WEAKER:
        flags.append(Flag(AMBER, "WEAKER", "Weaker match"))
    if buddy.location != joiner.location:
        flags.append(Flag(INFO, "OTHER_LOCATION", "Buddy is at a different location"))
    if buddy.department != joiner.department:
        flags.append(Flag(INFO, "OTHER_DEPARTMENT", "Buddy is in a different department"))
    if sum(a == 3 for a in joiner.answers) >= 4 or sum(a == 3 for a in buddy.answers) >= 4:
        flags.append(Flag(INFO, "MIDDLE_ANSWERS", "Mostly middle answers, so the match tells you less"))
    if buddy.completed_at and (today - buddy.completed_at).days > s.old_answers_months * 30:
        flags.append(Flag(INFO, "OLD_ANSWERS", f"Buddy's answers are over {s.old_answers_months} months old"))
    return flags


def rank_key(c: Candidate):
    return (-c.close_count, c.total_gap, c.largest_gap, c.completed_at)


def run_match(joiner: Joiner, buddies: list, settings: MatchSettings | None = None,
              today: date | None = None) -> MatchResult:
    s = settings or MatchSettings()
    today = today or date.today()

    scored = []
    for b in buddies:
        if not is_eligible(joiner, b):
            continue
        gaps, close, total, largest, band = score_answers(joiner.answers, b.answers, s)
        scored.append(Candidate(
            buddy_id=b.id, name=b.name, department=b.department, location=b.location,
            tier=tier_of(joiner, b), answers=list(b.answers), gaps=gaps,
            close_count=close, total_gap=total, largest_gap=largest, band=band,
            total_joiners=b.total_joiners, active_joiners=b.active_joiners,
            completed_at=b.completed_at.isoformat() if b.completed_at else "9999-12-31",
            flags=make_flags(joiner, b, gaps, band, s, today),
        ))

    good = (STRONG, GOOD)
    tiers = {t: sorted([c for c in scored if c.tier == t and c.band in good], key=rank_key)
             for t in (1, 2, 3)}
    weaker = sorted([c for c in scored if c.band == WEAKER], key=lambda c: (c.tier, rank_key(c)))
    ranked_scored = sorted(scored, key=lambda c: (c.band == NOT_SUGGESTED, c.tier, rank_key(c)))

    tier_reached, ranked = "MANUAL", []
    for t in (1, 2, 3):
        if tiers[t]:
            tier_reached, ranked = str(t), tiers[t]
            break
    else:
        if weaker:
            tier_reached, ranked = "FALLBACK", weaker

    n = s.candidates_per_tier
    return MatchResult(tier_reached, ranked[:n], ranked[n:], tiers, weaker, ranked_scored)