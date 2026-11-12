"""Every COMPASS email lives here. Each is sent at most once per key.

Joiners and buddies never get a link to act on: every email tells them what to do and gives them
the portal's sign-in link with their username and password, where everything is waiting for them.
Bodies are written in the light markup of render.py and sent formatted, with a plain-text copy.
A joiner gets five emails before joining (welcome, login details, our story, Day 1, see you
tomorrow; see prejoining.py) and the buddy review after their induction."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import IntegrityError
from django.utils import timezone

from .models import Notification
from .render import render

SIGN_OFF = "Team United\nUnited Group"


def stamp() -> str:
    """A key part for an email the admin asks for, so asking again sends it again."""
    return timezone.now().strftime("%Y%m%d%H%M%S%f")


def frontend_url() -> str:
    return getattr(settings, "FRONTEND_URL", "http://localhost:8000")


def admin_recipients() -> list:
    """Every Program admin with an email address, or the shared alert address."""
    found = list(
        get_user_model().objects.filter(is_active=True, is_staff=True).exclude(email="")
        .values_list("email", flat=True)
    )
    return found or [getattr(settings, "ALERT_EMAIL", "compass-admin@united-group.local")]


def send_once(key, to, subject, body, *, kind, joiner=None, buddy=None, pairing=None) -> bool:
    """Send one email unless this key was already sent. Returns True if it was sent now."""
    recipients = [to] if isinstance(to, str) else list(to)
    skip = tuple(f"@{d}" for d in getattr(settings, "EMAIL_SKIP_DOMAINS", []))
    recipients = [r for r in recipients if r and not r.lower().endswith(skip)]
    if not recipients or Notification.objects.filter(key=key).exists():
        return False
    text, html = render(body)
    send_mail(subject, text, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False, html_message=html)
    try:
        Notification.objects.create(
            key=key, kind=kind, to_email=", ".join(recipients), subject=subject,
            joiner=joiner, buddy=buddy, pairing=pairing,
        )
    except IntegrityError:
        pass
    return True


def first_name(name: str) -> str:
    parts = (name or "").split()
    return parts[0] if parts else ""


def username(person) -> str:
    return getattr(person, "candidate_id", None) or person.employee_id


def long_date(day) -> str:
    return f"{day.day} {day:%B %Y}"  # 1 December 2026


def day_date(day) -> str:
    return f"{day:%A}, {long_date(day)}"  # Tuesday, 1 December 2026


def sign_in_line(person, button="Sign in to COMPASS") -> str:
    """The portal's sign-in button with their username and their one password."""
    return (
        f"[[{button}|{frontend_url()}/login]]\n\n"
        f"Username: **{username(person)}**\nPassword: **{person.fixed_password()}**\n\n"
    )


def _email(person, body: str, closing: str = "") -> str:
    """Hi, the body, an optional closing line ("See you soon,"), then Team United."""
    end = f"{closing}\n{SIGN_OFF}" if closing else SIGN_OFF
    return f"Hi {first_name(person.name)},\n\n{body}{end}"


# ---------- login details ----------

def send_login_details(person, kind: str, code: str, stamp: str) -> bool:
    """The username and password for a new joiner or buddy. The email log records the subject,
    not the body."""
    to = person.personal_email if kind == "joiner" else person.email
    login_id = person.candidate_id if kind == "joiner" else person.employee_id
    credentials = (
        f"[[Sign in to COMPASS|{frontend_url()}/login]]\n\n"
        f"Username: **{login_id}**\n"
        f"Password: **{code}**\n\n"
        "Keep this email: you use the same password every time you sign in.\n\n"
    )
    if kind == "joiner":
        body = (
            "Here are your login details for COMPASS, United Group's buddy programme portal.\n\n"
            + credentials + joiner_questions(person)
            + "In COMPASS you'll also meet your buddy and follow your 4-week induction.\n\n"
        )
    else:
        body = (
            "You have been added to the COMPASS buddy pool. In COMPASS you complete your buddy profile "
            "(five short questions) and see the joiners assigned to you.\n\n" + credentials
        )
    return send_once(
        f"login_details:{kind}:{person.pk}:{stamp}", to, "Your COMPASS login details",
        _email(person, body), kind="login_details", **{kind: person},
    )


# ---------- joiner: the questions ----------

BUDDY_IS = (
    "Every new joiner at United Group gets a buddy: a colleague who's been with us a while and will "
    "help you find your feet in your first 4 weeks. They're the person to ask the everyday questions, "
    "like where the good lunch spots are or how things really get done around here."
)


def joiner_questions(joiner) -> str:
    """The "help us find your buddy" part of the login email, while the joiner still has to answer."""
    from compass_app.models import Joiner, Settings

    if joiner.compass_status != Joiner.Status.AWAITING_ASSESSMENT:
        return ""
    due = joiner.quiz_due(Settings.load().manual_cutoff_day)
    return (
        "## One thing to do now: help us find your buddy\n"
        f"{BUDDY_IS}\n\n"
        "To find someone you'll get along with, please sign in and answer two short sets of questions:\n"
        "• How you like to work: five quick questions, no right or wrong answers.\n"
        "• What you enjoy outside work: your hobbies and interests, so we can tell you about our clubs "
        "and teams, from sports to books to cooking.\n\n"
        f"Please complete it by **{day_date(due)}**. Your answers are only used to match you with a "
        "buddy and suggest clubs you might enjoy. They aren't used to assess you in any way.\n\n"
    )


def send_joiner_reminder(joiner, reminder_day) -> bool:
    """Sent only when the Program admin presses Send reminder on the joiner's page."""
    body = (
        "A quick reminder: we haven't received your COMPASS answers yet. They help us choose "
        "your buddy before you start.\n\n"
        f"{sign_in_line(joiner)}"
    )
    return send_once(
        f"nj_reminder:{joiner.pk}:{reminder_day}", joiner.personal_email,
        "Reminder: your COMPASS buddy questions", _email(joiner, body),
        kind="joiner_reminder", joiner=joiner,
    )


# ---------- buddy: the profile ----------

def send_buddy_reminder(buddy, number) -> bool:
    body = (
        "A reminder to complete your COMPASS buddy profile so we can match you with new joiners.\n\n"
        f"{sign_in_line(buddy)}"
    )
    return send_once(
        f"buddy_reminder:{buddy.pk}:{number}", buddy.email,
        "Reminder: complete your COMPASS buddy profile", _email(buddy, body),
        kind="buddy_reminder", buddy=buddy,
    )


def send_buddy_retake(buddy, stamp: str) -> bool:
    body = (
        "Please retake your COMPASS buddy profile. It only takes about 2 minutes, and it keeps "
        "your matches accurate.\n\n"
        f"{sign_in_line(buddy)}"
    )
    return send_once(
        f"buddy_retake:{buddy.pk}:{stamp}", buddy.email,
        "Please retake your COMPASS buddy profile", _email(buddy, body),
        kind="buddy_retake", buddy=buddy,
    )


# ---------- assigning a buddy ----------

def send_assignment(pairing) -> None:
    """Tell the buddy. The pairing is already active: nobody has to accept. The joiner sees their
    buddy in their portal and in the Day 1 and See you tomorrow emails."""
    joiner, buddy = pairing.joiner, pairing.buddy
    dates = f"from {pairing.start_date:%d %b %Y} to {pairing.end_date:%d %b %Y}"
    to_buddy = (
        f"You have been assigned as the COMPASS buddy for {joiner.name}"
        f"{', ' + joiner.designation if joiner.designation else ''} ({joiner.department}, {joiner.location}), "
        f"who joins on {joiner.date_of_joining:%d %b %Y}.\n\n"
        f"Please help them through their 4-week induction, {dates}. You can follow their "
        "induction progress in COMPASS.\n\n"
        f"{sign_in_line(buddy)}"
    )
    send_once(
        f"assigned_buddy:{pairing.pk}", buddy.email, f"You are {joiner.name}'s COMPASS buddy",
        _email(buddy, to_buddy), kind="assigned_buddy", joiner=joiner, buddy=buddy, pairing=pairing,
    )


def send_assignment_removed(pairing) -> bool:
    """The admin changed the buddy: tell the buddy who is no longer assigned."""
    joiner, buddy = pairing.joiner, pairing.buddy
    body = (
        f"COMPASS has changed the buddy for {joiner.name}, so you no longer need to look after them. "
        "Thank you, and nothing else is needed from you.\n\n"
    )
    return send_once(
        f"unassigned_buddy:{pairing.pk}", buddy.email, f"You are no longer {joiner.name}'s buddy",
        _email(buddy, body), kind="unassigned_buddy", joiner=joiner, buddy=buddy, pairing=pairing,
    )


# ---------- the buddy review after the 4 weeks ----------

def send_review_request(pairing) -> bool:
    joiner, buddy = pairing.joiner, pairing.buddy
    body = (
        f"You have finished your 4-week induction. Please tell us how {buddy.name} helped you: "
        "three quick questions and a comment box, under a minute.\n\n"
        f"{sign_in_line(joiner)}"
    )
    return send_once(
        f"review:{pairing.pk}", joiner.personal_email, "How was your COMPASS buddy?",
        _email(joiner, body), kind="review_request", joiner=joiner, buddy=buddy, pairing=pairing,
    )


# ---------- alerts to the Program admins ----------

def alert_admins(key, subject, body, joiner=None) -> bool:
    return send_once(key, admin_recipients(), subject, body, kind="admin_alert", joiner=joiner)


def alert_no_good_match(joiner, tier_reached: str, run_id: int) -> bool:
    if tier_reached == "MANUAL":
        detail = "No buddy reached 3 of 5. Please pair this joiner manually."
    else:
        detail = "Only Weaker matches (3 of 5) were found. Please review them."
    return alert_admins(
        f"no_good_match:{run_id}",
        f"No Strong or Good match for {joiner.name}",
        f"{joiner.name} joins on {joiner.date_of_joining:%d %b %Y}.\n"
        f"Search reached: {tier_reached}.\n{detail}\n\n"
        f"Open the match review: {frontend_url()}/hr/joiners/{joiner.pk}",
        joiner=joiner,
    )
