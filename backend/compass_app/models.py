import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

ANSWER = [MinValueValidator(1), MaxValueValidator(5)]

# The starting lists. The Program admin keeps the real ones on the Settings page.
DEFAULT_DEPARTMENTS = ["Sales", "Finance", "Marketing", "Operations", "HR", "IT"]
DEFAULT_LOCATIONS = ["Mumbai", "Pune", "Delhi", "Bengaluru", "Chennai"]


def default_departments():
    return list(DEFAULT_DEPARTMENTS)


def default_locations():
    return list(DEFAULT_LOCATIONS)


# Easy to read and type: no 0/O, 1/l/I.
PASSWORD_LETTERS = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"


def new_password() -> str:
    return "".join(secrets.choice(PASSWORD_LETTERS) for _ in range(8))


class Settings(models.Model):
    """One row only. The Program admin edits these in COMPASS; no rebuild needed."""
    close_gap = models.PositiveSmallIntegerField(default=1)
    strong_threshold = models.PositiveSmallIntegerField(default=5)
    good_threshold = models.PositiveSmallIntegerField(default=4)
    weaker_threshold = models.PositiveSmallIntegerField(default=3)
    amber_gap = models.PositiveSmallIntegerField(default=2)
    red_gap = models.PositiveSmallIntegerField(default=3)
    candidates_per_tier = models.PositiveSmallIntegerField(default=3)
    # A joiner answers the questions (asked in their login email) by `manual_cutoff_day` days before
    # joining, or within 2 days if added 10 days or less before; then manual pairing.
    manual_cutoff_day = models.PositiveSmallIntegerField(default=7)
    old_answers_months = models.PositiveSmallIntegerField(default=12)
    joiner_intro = models.TextField(
        default="Every new joiner gets a buddy. These five questions help us find someone "
                "who works the way you do.")
    buddy_intro = models.TextField(
        default="These five questions help us pair you with new joiners who work in a "
                "similar way to you.")
    # Every joiner and buddy has one of these, spelt exactly so: the match compares them, so a
    # typed "sales" would never meet "Sales".
    departments = models.JSONField(default=default_departments)
    locations = models.JSONField(default=default_locations)

    # What the pre-joining emails show. A blank one leaves its line out of the email.
    story_video_link = models.CharField(max_length=500, blank=True)
    handbook_link = models.CharField(max_length=500, blank=True)
    linkedin_link = models.CharField(max_length=500, blank=True)
    instagram_link = models.CharField(max_length=500, blank=True)
    dress_code = models.CharField(
        max_length=300, blank=True, default="Business casual. Closed, comfortable footwear.")
    contact_phone = models.CharField(max_length=50, blank=True)
    # The office each location's joiners report to on Day 1: {"Pune": {"address": ..., "map_link": ...}}.
    office_details = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def office_for(self, location: str) -> dict:
        """The Day 1 address and map link for joiners at this location (blank if not set)."""
        office = self.office_details.get(location) or {}
        return {"address": office.get("address", ""), "map_link": office.get("map_link", "")}

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "COMPASS settings"


class QuestionSet(models.Model):
    version = models.PositiveSmallIntegerField(unique=True)
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Question set v{self.version}"

    @classmethod
    def active(cls):
        """The newest version, which everyone answers."""
        return cls.objects.order_by("-version").first()


class Question(models.Model):
    question_set = models.ForeignKey(QuestionSet, on_delete=models.CASCADE, related_name="questions")
    number = models.PositiveSmallIntegerField()
    dimension = models.CharField(max_length=50)
    text = models.CharField(max_length=255)
    label_1 = models.CharField(max_length=255)
    label_2 = models.CharField(max_length=255)
    label_3 = models.CharField(max_length=255)
    label_4 = models.CharField(max_length=255)
    label_5 = models.CharField(max_length=255)

    class Meta:
        unique_together = ("question_set", "number")
        ordering = ["question_set", "number"]

    def __str__(self):
        return f"v{self.question_set.version} Q{self.number} {self.dimension}"

    def label(self, value) -> str:
        return getattr(self, f"label_{value}")

    def payload(self) -> dict:
        """The question with every answer in words, as the screens show it."""
        return {
            "number": self.number, "dimension": self.dimension, "text": self.text,
            "options": [{"value": v, "label": self.label(v)} for v in range(1, 6)],
        }


class Employee(models.Model):
    """Fields that come from the HRMS feed, shared by Buddy and Joiner."""
    name = models.CharField(max_length=150)
    department = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    brand = models.CharField(max_length=100, blank=True)
    function = models.CharField(max_length=100, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    designation_track = models.CharField(
        max_length=1, blank=True, choices=[(c, c) for c in "ABCDE"]
    )
    # They sign in with their candidate or employee id and their password. The password is made
    # once and kept as it is, so every email can repeat it; login_code holds its hash for sign-in.
    login_code = models.CharField(max_length=128, blank=True)
    password = models.CharField(max_length=20, blank=True)
    # What they enjoy outside work, picked in their portal (from compass_app.clubs.INTERESTS).
    # Joiners and buddies who share one at a location form a club. Not used by the match.
    interests = models.JSONField(default=list, blank=True)
    interests_other = models.CharField(max_length=300, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

    def set_login_code(self, code):
        self.login_code = make_password(code)

    def check_login_code(self, code) -> bool:
        return bool(self.login_code) and check_password(code, self.login_code)

    def fixed_password(self) -> str:
        """Their one password, made the first time it is needed and never changed after."""
        if not self.password:
            self.password = new_password()
            self.set_login_code(self.password)
            self.save(update_fields=["password", "login_code"])
        return self.password


class Buddy(Employee):
    class PoolStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PAUSED = "PAUSED", "Paused"
        ON_LEAVE = "ON_LEAVE", "On leave"
        REMOVED = "REMOVED", "Removed"

    employee_id = models.CharField(max_length=50, unique=True)
    email = models.EmailField()
    manager_id = models.CharField(max_length=50, blank=True)
    pool_status = models.CharField(max_length=10, choices=PoolStatus.choices, default=PoolStatus.PAUSED)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    total_joiners_buddied = models.PositiveIntegerField(default=0)
    active_joiners = models.PositiveIntegerField(default=0)
    date_added_to_pool = models.DateField(auto_now_add=True)
    intro = models.TextField(blank=True)  # short introduction shown to the joiner
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)  # their quiz page address

    class Meta:
        verbose_name_plural = "Buddies"


class Joiner(Employee):
    class Status(models.TextChoices):
        AWAITING_ASSESSMENT = "AWAITING_ASSESSMENT", "Awaiting assessment"
        AWAITING_PAIRING = "AWAITING_PAIRING", "Awaiting pairing"
        PAIRED = "PAIRED", "Paired"
        MANUAL = "MANUAL", "Manual"
        ON_HOLD = "ON_HOLD", "On hold"
        CLOSED = "CLOSED", "Closed"

    candidate_id = models.CharField(max_length=50, unique=True)
    personal_email = models.EmailField()
    reporting_manager_id = models.CharField(max_length=50, blank=True)
    date_of_joining = models.DateField()
    compass_status = models.CharField(max_length=25, choices=Status.choices, default=Status.AWAITING_ASSESSMENT)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)  # their quiz page address
    # The day the "time to answer" email went out (or the admin re-sent it). The quiz stays open
    # for one week from then.
    quiz_link_sent_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    # The day the Program admin added them. Their pre-joining emails follow from it; joiners added
    # before those emails existed have none and get only the quiz emails.
    added_on = models.DateField(null=True, blank=True)

    # Day 1, for the pre-joining emails. A blank one leaves its line out. The office address and
    # map link come from Settings, by the joiner's location.
    manager_name = models.CharField(max_length=150, blank=True)
    reporting_time = models.CharField(max_length=50, blank=True)
    contact_person = models.CharField(max_length=150, blank=True)
    directions = models.CharField(max_length=300, blank=True)
    attendance_confirmed_at = models.DateTimeField(null=True, blank=True)  # "Yes, I'll be there"

    QUIZ_LINK_VALID_DAYS = 7
    SHORT_NOTICE_DAYS = 10  # added this close to joining: the short-notice emails
    SHORT_NOTICE_QUIZ_DAYS = 2  # and the quiz is due this many days after its email

    def notice_days(self):
        """Days from being added to joining, or None for joiners added before it was recorded."""
        return None if self.added_on is None else (self.date_of_joining - self.added_on).days

    def short_notice(self) -> bool:
        days = self.notice_days()
        return days is not None and days <= self.SHORT_NOTICE_DAYS

    def quiz_due(self, cutoff_days: int):
        """The last day to answer: `cutoff_days` before joining, or 2 days after the quiz email
        for a short-notice joiner."""
        if self.short_notice():
            sent = self.quiz_link_sent_on or self.added_on
            return min(sent + timedelta(days=self.SHORT_NOTICE_QUIZ_DAYS), self.date_of_joining)
        return self.date_of_joining - timedelta(days=cutoff_days)

    def submitted_response(self):
        """Their latest submitted answers, or None."""
        return (
            Response.objects.filter(joiner=self, assessment_code=Response.Code.JOINER, submitted_at__isnull=False)
            .select_related("question_set").order_by("-submitted_at").first()
        )

    def quiz_link_expired(self, today) -> bool:
        if self.quiz_link_sent_on is None:
            return False
        return today > self.quiz_link_sent_on + timedelta(days=self.QUIZ_LINK_VALID_DAYS)


class Response(models.Model):
    """One person's answers to the five questions. Numbers 1-5, never shown to them."""
    class Code(models.TextChoices):
        BUDDY = "CMP-BD", "CMP-BD"
        JOINER = "CMP-NJ", "CMP-NJ"

    assessment_code = models.CharField(max_length=6, choices=Code.choices)
    buddy = models.ForeignKey(Buddy, null=True, blank=True, on_delete=models.CASCADE, related_name="responses")
    joiner = models.ForeignKey(Joiner, null=True, blank=True, on_delete=models.CASCADE, related_name="responses")
    question_set = models.ForeignKey(QuestionSet, on_delete=models.PROTECT)
    q1 = models.PositiveSmallIntegerField(null=True, blank=True, validators=ANSWER)
    q2 = models.PositiveSmallIntegerField(null=True, blank=True, validators=ANSWER)
    q3 = models.PositiveSmallIntegerField(null=True, blank=True, validators=ANSWER)
    q4 = models.PositiveSmallIntegerField(null=True, blank=True, validators=ANSWER)
    q5 = models.PositiveSmallIntegerField(null=True, blank=True, validators=ANSWER)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    def answers(self):
        return [self.q1, self.q2, self.q3, self.q4, self.q5]

    @staticmethod
    def answer_fields(answers) -> dict:
        """{"q1": ..., "q5": ...} from a list of five answers."""
        return {f"q{n}": a for n, a in enumerate(answers, start=1)}

    @classmethod
    def submitted(cls, person, question_set, answers, when=None):
        """A joiner's or buddy's finished answers, not yet saved."""
        kind, code = ("joiner", cls.Code.JOINER) if isinstance(person, Joiner) else ("buddy", cls.Code.BUDDY)
        return cls(**{kind: person}, assessment_code=code, question_set=question_set,
                   submitted_at=when or timezone.now(), **cls.answer_fields(answers))

    def __str__(self):
        who = self.buddy or self.joiner
        return f"{self.assessment_code} {who}"


class MatchRun(models.Model):
    joiner = models.ForeignKey(Joiner, on_delete=models.CASCADE, related_name="match_runs")
    run_time = models.DateTimeField(auto_now_add=True)
    tier_reached = models.CharField(max_length=20, blank=True)
    results = models.JSONField(default=list)  # full snapshot: every candidate, scores, band, flags, rank

    def __str__(self):
        return f"Run {self.pk} for {self.joiner}"


class Pairing(models.Model):
    """A buddy assigned to a joiner by the Program admin. It is active at once (the buddy is told,
    not asked) and runs for the joiner's first 30 days, the 4-week induction."""

    LENGTH_DAYS = 30
    REVIEW_AFTER_DAYS = 28  # the buddy review opens once the 4 weeks are over
    CHANGE_WITHIN_DAYS = 2  # the buddy can be changed for this long after assigning

    class Source(models.TextChoices):
        SYSTEM = "SYSTEM", "System"
        MANUAL = "MANUAL", "Manual"
        SYSTEM_OVERRIDE = "SYSTEM_OVERRIDE", "System override"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        CLOSED = "CLOSED", "Finished"
        CANCELLED = "CANCELLED", "Changed"  # the admin picked a different buddy

    joiner = models.ForeignKey(Joiner, on_delete=models.CASCADE, related_name="pairings")
    buddy = models.ForeignKey(Buddy, on_delete=models.PROTECT, related_name="pairings")
    source = models.CharField(max_length=20, choices=Source.choices)
    system_top_pick = models.ForeignKey(
        Buddy, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    band = models.CharField(max_length=10, blank=True)
    flags = models.JSONField(default=list, blank=True)
    close_count = models.PositiveSmallIntegerField(null=True, blank=True)  # of 5, when assigned
    override_reason = models.CharField(max_length=255, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    start_date = models.DateField()  # Day 1, the date of joining
    end_date = models.DateField()  # Day 30
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    def __str__(self):
        return f"{self.joiner} -> {self.buddy}"

    @staticmethod
    def dates_for(joiner):
        start = joiner.date_of_joining
        return start, start + timedelta(days=Pairing.LENGTH_DAYS - 1)

    def can_change(self, now=None) -> bool:
        now = now or timezone.now()
        return self.status == self.Status.ACTIVE and now - self.assigned_at <= timedelta(days=self.CHANGE_WITHIN_DAYS)

    def review_opens_on(self):
        return self.start_date + timedelta(days=self.REVIEW_AFTER_DAYS)


class InductionItem(models.Model):
    """One row of the 4-week induction programme. Every joiner follows the same programme from their
    joining date; the Program admin writes and edits it in COMPASS."""
    week = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)])
    day = models.CharField(max_length=40)  # e.g. "Day 1" or "Days 2-3"
    activity = models.CharField(max_length=200)
    owner = models.CharField(max_length=100, blank=True)  # who it is with: buddy, manager, HR, IT
    position = models.PositiveIntegerField(default=0)  # order within the week

    class Meta:
        ordering = ["week", "position", "pk"]

    def __str__(self):
        return f"Week {self.week}, {self.day}: {self.activity}"


class InductionTick(models.Model):
    """A joiner marked an induction item as done."""
    joiner = models.ForeignKey(Joiner, on_delete=models.CASCADE, related_name="induction_ticks")
    item = models.ForeignKey(InductionItem, on_delete=models.CASCADE, related_name="ticks")
    done_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("joiner", "item")


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=50)
    object_id = models.CharField(max_length=50, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action}"

    @classmethod
    def record(cls, action, obj=None, *, user=None, before=None, after=None, object_type=None):
        """Log one change. The record is named by its model and id unless `object_type` says otherwise;
        `user` is None for what COMPASS does on its own (the daily job, a joiner submitting)."""
        return cls.objects.create(
            user=user, action=action, object_type=object_type or type(obj).__name__,
            object_id=str(obj.pk) if obj is not None else "", before=before, after=after,
        )
