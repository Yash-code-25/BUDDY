"""The joiner's emails before joining. Every joiner gets the same five, from Team United:

    1 Welcome to United Group                    when added
    2 Your COMPASS login details                 when added (emails.send_login_details): username,
                                                 password, and the 5 questions and hobbies to answer
    3 Get to know United Group                   14 days before joining: our story, values, handbook
    4 Everything you need for Day 1              3 days before joining
    5 See you tomorrow                           1 day before joining

and after the 4-week induction, 6 How was your COMPASS buddy? (feedback/jobs.py).

A joiner added later than an email's day gets it the day after they are added (or that same day
if they join the next day), so everyone gets all five. Every email is sent once (its key), so
send_due() is safe to run as often as you like. Joiners added before this series existed (no
added_on) get none of it. A blank setting or Day 1 detail leaves its line out instead of a gap.
"""
from datetime import date, timedelta

from compass_app.induction import current_pairing
from compass_app.models import Joiner, Settings

from .emails import _email, day_date, frontend_url, long_date, send_once, username

COMPANY_DAYS_BEFORE = 14
DAY_ONE_DAYS_BEFORE = 3

VALUES = (
    "## What we stand for\n"
    "At United Group, five values guide how we work with each other and with our customers:\n"
    "1. **Staff Development.** We invest in your learning and help you grow into your full potential.\n"
    "2. **Building Trust.** We build strong bonds with everyone we work with, through respect, care and "
    "understanding.\n"
    "3. **Passion for Excellence.** Meeting expectations isn't enough. We keep looking for ways to do better.\n"
    "4. **Commitment.** We walk our talk, deliver what we've agreed, and own our actions and results.\n"
    "5. **One for All, All for Winning.** We value what each person brings and work as one team towards a "
    "shared goal.\n\n"
)


# ---------- the pieces the emails share ----------

def _where_and_when(joiner: Joiner, s: Settings) -> str:
    lines = [f"• Date: {day_date(joiner.date_of_joining)}"]
    if joiner.reporting_time:
        lines.append(f"• Time: please arrive by {joiner.reporting_time}")
    office = s.office_for(joiner.location)
    if office["address"]:
        where = office["address"] + (f" · [Map]({office['map_link']})" if office["map_link"] else "")
        lines.append(f"• Address: {where}")
    if joiner.contact_person:
        lines.append(f"• Ask for: {joiner.contact_person}, who'll be expecting you")
    if joiner.directions:
        lines.append(f"• Getting there: {joiner.directions}")
    return "## Where and when\n" + "\n".join(lines) + "\n\n"


def _buddy_name(joiner: Joiner):
    pairing = current_pairing(joiner)
    return pairing.buddy.name if pairing else None


def _send(joiner, kind, subject, body, closing=""):
    return send_once(f"{kind}:{joiner.pk}", joiner.personal_email, subject, _email(joiner, body, closing),
                     kind=kind, joiner=joiner)


# ---------- the emails ----------

def welcome(joiner, s, today):
    """1. When added."""
    body = (
        "Welcome to United Group! We're really glad you said yes, and we're looking forward to having you "
        f"with us from {long_date(joiner.date_of_joining)}.\n\n"
        "We'd like to stay in touch until you join. Here's what you'll hear from us:\n"
        "• Your COMPASS login details, with a few quick questions so we can pair you with the right buddy\n"
        "• Our story, what we stand for, and your pre-joining handbook\n"
        "• Everything you need for Day 1\n"
        "• A short note the day before you join\n\n"
        "Our HR team will also write to you separately about your joining documents.\n\n"
        "If you have any questions before you join, just reply to this email. We're happy to help.\n\n"
    )
    return _send(joiner, "welcome", f"Welcome to United Group, {joiner.name.split()[0]}!", body, "Welcome aboard,")


def company(joiner, s, today):
    """3. Our story, values and handbook: 14 days before joining."""
    story = (
        "## Our story\n"
        "This short video shows where we started, what we build today, and where we're headed.\n\n"
        f"[[Watch our story|{s.story_video_link}]]\n\n"
    ) if s.story_video_link else ""
    handbook = (
        "## Your pre-joining handbook\n"
        "We've put together a short handbook with the essentials: who we are, what we do, how we work, and "
        "who's who. Read it whenever suits you; there's no test.\n\n"
        f"[[Open the handbook|{s.handbook_link}]]\n\n"
    ) if s.handbook_link else ""
    links = [f"[{name}]({link})" for name, link in (("LinkedIn", s.linkedin_link), ("Instagram", s.instagram_link)) if link]
    social = f"You can also follow us on {' and '.join(links)} to see what we're up to.\n\n" if links else ""
    body = (
        "Before you join us, we'd love you to get to know the company you're becoming part of.\n\n"
        f"{story}{VALUES}"
        "You'll see these in action from your first week.\n\n"
        f"{handbook}{social}"
        "We look forward to meeting you soon.\n\n"
    )
    return _send(joiner, "our_story", "Get to know United Group before you join", body, "Warm regards,")


def day_one(joiner, s, today):
    """4. Where, when, what to bring and wear, who they'll meet: 3 days before joining."""
    manager = (f"{joiner.manager_name}, your manager, will meet you and walk you through your first few weeks"
               if joiner.manager_name else "You'll meet your manager")
    buddy = _buddy_name(joiner)
    buddy = f", and your buddy, {buddy}, will be around too" if buddy else ""
    wear = f"## What to wear\n{s.dress_code}\n\n" if s.dress_code else ""
    phone = (f"If anything changes, or you're running late on the day, call us on {s.contact_phone}.\n\n"
             if s.contact_phone else "")
    body = (
        "Almost there! Everyone here is looking forward to welcoming you. Here's everything you need for your "
        "first day.\n\n"
        + _where_and_when(joiner, s)
        + "## Please bring\n"
        "• The original documents listed in the email from our HR team, plus one set of photocopies\n\n"
        + wear
        + "## Who you'll meet\nYour day starts with a warm welcome and your joining kit. "
        f"{manager}{buddy}. We'll have lunch together.\n\n"
        f"[[Yes, I'll be there|{frontend_url()}/login]]\n\n"
        f"The button opens COMPASS: sign in with username **{username(joiner)}** and password "
        f"**{joiner.fixed_password()}**, then tap **Yes, I'll be there**.\n\n"
        + phone
    )
    return _send(joiner, "logistics", f"Everything you need for {day_date(joiner.date_of_joining)}", body,
                 f"See you on {joiner.date_of_joining:%A},")


def see_you_tomorrow(joiner, s, today):
    """5. The day before joining."""
    people = []
    if joiner.manager_name:
        people.append(f"{joiner.manager_name}, your manager, will meet you after your welcome session and "
                      "walk you through your first few weeks.")
    buddy = _buddy_name(joiner)
    if buddy:
        people.append(f"Your buddy, {buddy}, will be around too, so you'll have a friendly face to go to from "
                      "the start.")
    address = s.office_for(joiner.location)["address"]
    arrive = (f" by {joiner.reporting_time}" if joiner.reporting_time else "") + (f" at {address}" if address else "")
    reminder = f"please arrive{arrive}, and bring your documents" if arrive else "please bring your documents"
    body = (
        "Tomorrow's the day! Everyone here is looking forward to welcoming you.\n\n"
        + (" ".join(people) + "\n\n" if people else "")
        + f"A quick reminder: {reminder}.\n\n"
        "Get a good night's sleep, and we'll see you tomorrow.\n\n"
    )
    return _send(joiner, "see_you_tomorrow", f"See you tomorrow, {joiner.name.split()[0]}!", body)


# ---------- which emails are due ----------

def _day(joiner: Joiner, days_before: int) -> date:
    """`days_before` joining, or the day after they were added if that is later (and still before
    joining), or the day they were added if they join the next day."""
    day = max(joiner.date_of_joining - timedelta(days=days_before), joiner.added_on + timedelta(days=1))
    return day if day < joiner.date_of_joining else joiner.added_on


def due(joiner: Joiner, today: date) -> list:
    """The emails due for this joiner today, in the order they are sent. Already-sent ones are
    skipped by their key. (The login details go out from people.welcome, when they are added.)"""
    days = (joiner.date_of_joining - today).days
    if joiner.added_on is None or days < 0 or joiner.compass_status == Joiner.Status.CLOSED:
        return []
    return [fn for fn, ok in (
        (welcome, True),
        (company, today >= _day(joiner, COMPANY_DAYS_BEFORE)),
        (day_one, days >= 1 and today >= _day(joiner, DAY_ONE_DAYS_BEFORE)),
        (see_you_tomorrow, days == 1),
    ) if ok]


def send_due(joiner: Joiner, today: date) -> int:
    s = Settings.load()
    return sum(bool(fn(joiner, s, today)) for fn in due(joiner, today))


def send_all_due(today: date) -> int:
    count = 0
    for joiner in Joiner.objects.filter(added_on__isnull=False, date_of_joining__gte=today).exclude(
        compass_status=Joiner.Status.CLOSED
    ):
        count += send_due(joiner, today)
    return count
