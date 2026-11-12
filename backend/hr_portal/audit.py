"""The audit log in plain words: each entry becomes a sentence ("superuser resumed buddy Anita Desai")
and a list of what changed ("Pool status: Paused → Active"), so the page never shows raw data.

The log itself is unchanged (compass_app.models.AuditLog); this only describes it."""
from compass_app.models import Buddy, InductionItem, Joiner, Pairing, Response

# {who} and {target} are filled in; the page shows them in bold, the target as a link.
SENTENCES = {
    "joiner_created": "{who} added joiner {target}",
    "buddy_added": "{who} added buddy {target}",
    "joiners_imported": "{who} imported joiners from a CSV file",
    "buddies_imported": "{who} imported buddies from a CSV file",
    "joiners_removed": "{who} removed joiners",
    "joiner_remind": "{who} sent a reminder to {target}",
    "joiner_manual": "{who} routed {target} to manual pairing",
    "joiner_hold": "{who} put {target} on hold",
    "joiner_release": "{who} released {target} from hold",
    "joiner_not_required": "{who} marked {target} as not needing a buddy",
    "joiner_note": "{who} added a note to {target}",
    "joiner_send_login": "{who} sent login details again to {target}",
    "joiner_day_one_changed": "{who} changed the Day 1 details of {target}",
    "buddy_assigned": "{who} assigned a buddy to {target}",
    "buddy_changed": "{who} changed the buddy of {target}",
    "match_run": "{who} ran the match for {target}",
    "routed_to_manual": "{who} routed {target} to manual pairing: no answers by the due day",
    "assessment_submitted": "{who} answered their 5 questions",
    "attendance_confirmed": "{who} confirmed they'll be there on Day 1",
    "buddy_reviewed": "{who} reviewed their buddy",
    "pairing_closed": "{who} closed the pairing of {target}",
    "buddy_edited": "{who} edited buddy {target}",
    "buddy_pause": "{who} paused buddy {target}",
    "buddy_resume": "{who} resumed buddy {target}",
    "buddy_leave": "{who} marked buddy {target} as on leave",
    "buddy_remove": "{who} removed buddy {target}",
    "buddy_remind": "{who} sent a profile reminder to {target}",
    "buddy_send_login": "{who} sent login details again to {target}",
    "buddy_retake": "{who} asked {target} to retake their profile",
    "buddy_reset": "{who} reset the profile of {target}",
    "response_reset": "{who} cleared the profile answers of {target}",
    "profile_reopened": "{who} reopened their profile to update it",
    "settings_changed": "{who} changed {target}",
    "induction_item_added": "{who} added induction item {target}",
    "induction_item_edited": "{who} edited induction item {target}",
    "induction_item_removed": "{who} removed induction item {target}",
}
# Things the person did themselves in their portal: they are the "who".
BY_THE_PERSON = {"assessment_submitted", "attendance_confirmed", "buddy_reviewed", "profile_reopened"}

LABELS = {
    "status": "Status", "compass_status": "Status", "pool_status": "Pool status", "buddy": "Buddy",
    "source": "Chosen by", "reason": "Reason", "note": "Note", "tier_reached": "Result",
    "intro": "Introduction", "manual_cutoff_day": "Questions due (days before joining)",
    "candidates_per_tier": "Buddies shown per tier", "story_video_link": "Our story video link",
    "handbook_link": "Handbook link", "contact_phone": "Phone for Day 1 changes", "dress_code": "What to wear",
    "office_details": "Office by location", "joiner_intro": "Joiner welcome text",
    "buddy_intro": "Buddy welcome text", "end_date": "Ended on", "owner": "With",
    "created": "Added", "updated": "Updated", "errors": "Rows with errors", "removed": "Removed",
}
# Ids and bookkeeping that mean nothing to a reader.
SKIP = {"pairing_id", "run_id", "id", "name", "position", "question_set_version", "answers", "days_to_joining"}
TIERS = {"1": "Tier 1: same department and location", "2": "Tier 2: same department, other locations",
         "3": "Tier 3: other departments", "weaker": "Weaker matches only", "MANUAL": "No good match: manual pairing"}
ENUM_WORDS = {"SYSTEM": "COMPASS's top suggestion", "SYSTEM_OVERRIDE": "Admin (not the top suggestion)",
              "MANUAL": "Manual", "WEAKER": "Weaker match"}


def _label(key):
    return LABELS.get(key, key.replace("_", " ").capitalize())


def _value(key, value, buddies):
    """A value in words: statuses as words, buddy ids as names, lists joined, blanks said."""
    if value in (None, "", [], {}):
        return "blank"
    if key == "buddy":
        return buddies.get(str(value), str(value))
    if key == "tier_reached":
        return TIERS.get(str(value), str(value))
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        return "updated"
    text = str(value)
    if text in ENUM_WORDS:
        return ENUM_WORDS[text]
    if text.isupper() and len(text) > 1:  # PAUSED, AWAITING_PAIRING, TIER_1 …
        return text.replace("_", " ").capitalize()
    return text if len(text) <= 90 else text[:87] + "…"


def changes(before, after, buddies) -> list:
    """[{label, before, after}] for each field that changed; `before` is None for a new value."""
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}
    rows = []
    for key in [*after, *(k for k in before if k not in after)]:
        if key in SKIP:
            continue
        old, new = before.get(key), after.get(key)
        if key in before and key in after and old == new:
            continue
        if key not in after:
            # Only a removal (an induction item, say) shows what it was; elsewhere the "after" side
            # simply did not record that field, which is not a change.
            if not after:
                rows.append({"label": _label(key), "before": _value(key, old, buddies), "after": None})
        elif key not in before or old in (None, ""):
            if new in (None, "", [], {}):
                continue
            rows.append({"label": _label(key), "before": None, "after": _value(key, new, buddies)})
        else:
            rows.append({"label": _label(key), "before": _value(key, old, buddies), "after": _value(key, new, buddies)})
    return rows


def describe(logs) -> list:
    """The page's rows for these log entries, with names looked up in one go."""
    ids = {kind: set() for kind in ("Joiner", "Buddy", "Pairing", "InductionItem")}
    buddy_codes = set()
    for log in logs:
        kind = {Response.Code.JOINER: "Joiner", Response.Code.BUDDY: "Buddy"}.get(log.object_type, log.object_type)
        if kind in ids and log.object_id.isdigit():
            ids[kind].add(int(log.object_id))
        for side in (log.before, log.after):
            if isinstance(side, dict) and side.get("buddy"):
                buddy_codes.add(str(side["buddy"]))
    joiners = {j.pk: j.name for j in Joiner.objects.filter(pk__in=ids["Joiner"])}
    buddies = {b.pk: b.name for b in Buddy.objects.filter(pk__in=ids["Buddy"])}
    pairings = {p.pk: p for p in Pairing.objects.filter(pk__in=ids["Pairing"]).select_related("joiner", "buddy")}
    items = {i.pk: i.activity for i in InductionItem.objects.filter(pk__in=ids["InductionItem"])}
    buddy_names = {b.employee_id: b.name for b in Buddy.objects.filter(employee_id__in=buddy_codes)}
    buddy_names.update({str(b.pk): b.name for b in Buddy.objects.filter(pk__in=[int(c) for c in buddy_codes if c.isdigit()])})

    rows = []
    for log in logs:
        kind = {Response.Code.JOINER: "Joiner", Response.Code.BUDDY: "Buddy"}.get(log.object_type, log.object_type)
        pk = int(log.object_id) if log.object_id.isdigit() else None
        target, link = None, None
        if kind == "Joiner":
            target = joiners.get(pk, "a joiner no longer in COMPASS")
            link = f"/hr/joiners/{pk}" if pk in joiners else None
        elif kind == "Buddy":
            target = buddies.get(pk, "a buddy no longer in COMPASS")
            link = f"/hr/buddies?buddy={pk}" if pk in buddies else None
        elif kind == "Pairing":
            p = pairings.get(pk)
            target = f"{p.joiner.name} and {p.buddy.name}" if p else "a pairing no longer in COMPASS"
            link = f"/hr/joiners/{p.joiner_id}" if p else None
        elif kind == "InductionItem":
            side = log.after if isinstance(log.after, dict) else log.before if isinstance(log.before, dict) else {}
            target = items.get(pk) or side.get("activity") or "an induction item"
        elif kind == "Settings":
            target, link = "Settings", "/hr/settings"

        if log.action in BY_THE_PERSON:
            who, who_link = target or "Someone", link
            if log.action == "buddy_reviewed" and kind == "Pairing" and pairings.get(pk):
                who, who_link = pairings[pk].joiner.name, f"/hr/joiners/{pairings[pk].joiner_id}"
        else:
            who, who_link = (log.user.username if log.user else "COMPASS"), None
        sentence = SENTENCES.get(log.action, "{who}: " + log.action.replace("_", " ") + (" {target}" if target else ""))
        rows.append({
            "id": log.pk, "when": log.created_at, "user": log.user.username if log.user else "system",
            "action": log.action,
            "sentence": sentence, "who": who, "who_link": who_link, "target": target, "target_link": link,
            "changes": changes(log.before, log.after, buddy_names),
        })
    return rows
