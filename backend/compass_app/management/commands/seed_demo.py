"""Development only: wipe the people data and start a clean demo of 100 buddies and 10 joiners. No buddy
is assigned to anyone: the Program admin does that. About half of the generated joiners have answered
their questions already, so there is someone to assign straight away; the named joiners have not."""
import random
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone

from compass_app.clubs import INTERESTS
from compass_app.matching import run_match_for_joiner
from compass_app.models import (
    DEFAULT_DEPARTMENTS, DEFAULT_LOCATIONS, AuditLog, Buddy, InductionItem, InductionTick, Joiner,
    MatchRun, Pairing, QuestionSet, Response, Settings, new_password,
)

from feedback.models import Feedback
from notifications.models import Notification

# A sample 4-week induction programme. The Program admin edits it on the Induction page.
INDUCTION = [
    (1, "Day 1", "Welcome, ID card, laptop and email set-up", "HR and IT"),
    (1, "Day 1", "Meet your buddy and walk around the office", "Buddy"),
    (1, "Day 2", "Company overview and values session", "L&D"),
    (1, "Days 3-5", "Meet your team and understand your role", "Manager"),
    (2, "Day 6", "Tools and systems training for your role", "Buddy"),
    (2, "Days 7-8", "Shadow a colleague on day-to-day work", "Buddy"),
    (2, "Day 9", "Policies: leave, travel, expenses, IT security", "HR"),
    (2, "Day 10", "Weekly check-in with your buddy", "Buddy"),
    (3, "Days 11-13", "Take on your first small task", "Manager"),
    (3, "Day 14", "Meet the teams you will work with most", "Buddy"),
    (3, "Day 15", "Weekly check-in with your buddy", "Buddy"),
    (4, "Days 16-18", "Work on a real piece of work end to end", "Manager"),
    (4, "Day 19", "Agree your goals for the next three months", "Manager"),
    (4, "Day 20", "Final buddy check-in and induction wrap-up", "Buddy"),
]

# Buddies have finished their profile, so the match can suggest them, but look after nobody yet.
# (employee id, name, designation, department, location, answers Q1..Q5)
BUDDIES = [
    ("E001", "Anita Desai", "Senior Executive", "Sales", "Mumbai", [3, 2, 4, 1, 3]),
    ("E002", "Bharat Mehta", "Manager", "Sales", "Mumbai", [4, 5, 4, 5, 4]),
    ("E003", "Chitra Nair", "Assistant Manager", "Sales", "Mumbai", [5, 4, 5, 2, 5]),
    ("E004", "Dev Malhotra", "Senior Executive", "Sales", "Mumbai", [5, 5, 4, 1, 5]),
    ("E005", "Esha Kapoor", "Team Lead", "Sales", "Mumbai", [4, 3, 3, 4, 4]),
    ("E006", "Farhan Sheikh", "Executive", "Sales", "Mumbai", [3, 3, 5, 4, 3]),
    ("E007", "Gauri Patil", "Manager", "Sales", "Pune", [5, 4, 5, 4, 4]),
    ("E008", "Hari Iyer", "Assistant Manager", "Finance", "Mumbai", [5, 4, 5, 4, 5]),
]

# Joiners who have not answered yet. (candidate id, name, department, location, joins in N days)
JOINERS = [
    ("C001", "Yash Chavan", "Sales", "Mumbai", 14),
    ("C002", "Nia Shah", "Sales", "Mumbai", 12),
    ("C003", "Rohan Mehta", "Sales", "Mumbai", 10),
    ("C004", "Zoya Khan", "Sales", "Mumbai", 10),
    ("C005", "Karan Joshi", "Sales", "Mumbai", 8),
    ("C006", "Isha Kulkarni", "Sales", "Pune", 8),
    ("C007", "Vikram Rao", "Finance", "Mumbai", 6),
    ("C008", "Meera Iyer", "Sales", "Mumbai", 5),
]


# The rest are generated from these, the same every run.
FIRST = ["Aarav", "Aditi", "Akash", "Amit", "Ananya", "Anjali", "Arjun", "Ayesha", "Deepak", "Diya", "Gaurav",
         "Ishaan", "Kabir", "Kavya", "Kiran", "Manish", "Meera", "Mohit", "Neha", "Nikhil", "Pooja", "Pranav",
         "Priya", "Rahul", "Riya", "Rohit", "Sahil", "Sana", "Shreya", "Siddharth", "Simran", "Sneha", "Tanvi",
         "Tarun", "Varun", "Vidya", "Vivek", "Yamini", "Zara", "Harsh"]
LAST = ["Agarwal", "Bhat", "Chopra", "Das", "Deshmukh", "Gupta", "Iyer", "Jain", "Joshi", "Kapoor", "Khan",
        "Kulkarni", "Menon", "Mishra", "Nair", "Pandey", "Patel", "Pillai", "Rao", "Reddy", "Saxena", "Shah",
        "Sharma", "Singh", "Verma"]
BUDDY_ROLES = ["Executive", "Senior Executive", "Assistant Manager", "Manager", "Team Lead"]
JOINER_ROLES = ["Analyst", "Associate", "Executive", "Trainee", "Engineer"]

def answers(rng):
    return [rng.randint(1, 5) for _ in range(5)]


def day_one(rng):
    """Day 1 details for the pre-joining emails. The office address comes from Settings."""
    return {
        "manager_name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
        "reporting_time": rng.choice(["9:00 am", "9:30 am", "10:00 am"]),
        "contact_person": "the HR desk at reception",
    }


def sample_interests(rng):
    """One to three hobbies, in the list's order, so the demo buddies fill the clubs."""
    picked = rng.sample(INTERESTS, rng.randint(1, 3))
    return [i for i in INTERESTS if i in picked]


class Command(BaseCommand):
    help = "Wipe all joiners, buddies and their history, then build a clean demo (100 buddies, 10 joiners)"

    def add_arguments(self, parser):
        parser.add_argument("--buddies", type=int, default=100,
                            help="How many buddies (at least the 8 named ones)")
        parser.add_argument("--joiners", type=int, default=10,
                            help="How many joiners (at least the 8 named ones)")

    @transaction.atomic
    def handle(self, *args, buddies, joiners, **options):
        for model in (Feedback, InductionTick, Pairing, MatchRun, Response, Joiner, Buddy,
                      InductionItem, Notification, AuditLog):
            model.objects.all().delete()
        call_command("seed_questions", stdout=self.stdout)
        qs = QuestionSet.active()
        now = timezone.now()
        today = timezone.localdate()

        # The demo people's departments and locations must be on the lists in Settings.
        s = Settings.load()
        s.departments += [d for d in DEFAULT_DEPARTMENTS if d not in s.departments]
        s.locations += [loc for loc in DEFAULT_LOCATIONS if loc not in s.locations]
        s.save()

        for i, (week, day, activity, owner) in enumerate(INDUCTION, start=1):
            InductionItem.objects.create(week=week, day=day, activity=activity, owner=owner, position=i)

        logins = []
        hobby_rng = random.Random(11)
        for emp_id, name, role, dept, loc, a in BUDDIES:
            code = new_password()
            buddy = Buddy(employee_id=emp_id, name=name, designation=role, email=f"{emp_id.lower()}@test.com",
                          department=dept, location=loc, pool_status=Buddy.PoolStatus.ACTIVE,
                          intro=f"Hi, I'm {name.split()[0]}. Happy to help you settle in.",
                          interests=sample_interests(hobby_rng))
            buddy.password = code
            buddy.set_login_code(code)
            buddy.save()
            Response.submitted(buddy, qs, a, now).save()
            logins.append(("Buddy", name, emp_id, code))
        QuestionSet.objects.filter(pk=qs.pk).update(is_locked=True)

        for cid, name, dept, loc, joins_in in JOINERS:
            code = new_password()
            joiner = Joiner(candidate_id=cid, name=name, personal_email=f"{cid.lower()}@test.com",
                            department=dept, location=loc, designation="Analyst",
                            date_of_joining=today + timedelta(days=joins_in), added_on=today,
                            interests=sample_interests(hobby_rng), **day_one(hobby_rng))
            joiner.password = code
            joiner.set_login_code(code)
            joiner.save()
            logins.append(("Joiner", name, cid, code))

        shared_code, made = self.generate(max(0, buddies - len(BUDDIES)), max(0, joiners - len(JOINERS)),
                                          qs, now, today)

        total_buddies, total_joiners = Buddy.objects.count(), Joiner.objects.count()
        answered = Joiner.objects.filter(compass_status__in=[Joiner.Status.AWAITING_PAIRING, Joiner.Status.MANUAL]).count()
        self.stdout.write(self.style.SUCCESS(
            f"\nClean demo: {total_buddies} buddies (none assigned yet), {total_joiners} joiners "
            f"({answered} have answered and wait for a buddy), {len(INDUCTION)} induction items."))
        self.stdout.write("Sign in at /login. Admins use their own account "
                          "(`python manage.py createsuperuser` makes one).\n")
        self.stdout.write(f"  {'':7} {'Name':16} {'Username':9} Password")
        for kind, name, username, code in logins:
            self.stdout.write(f"  {kind:7} {name:16} {username:9} {code}")
        if made:
            self.stdout.write(f"\nThe other {made} people (buddies from E{len(BUDDIES) + 1:03}, joiners from "
                              f"C{len(JOINERS) + 1:03}) all sign in with the password {shared_code}.")

    def generate(self, n_buddies, n_joiners, qs, now, today):
        """Add `n_buddies` more buddies and `n_joiners` more joiners."""
        if n_buddies + n_joiners == 0:
            return None, 0
        rng = random.Random(2026)
        shared_code = new_password()
        hashed = make_password(shared_code)
        name = lambda: f"{rng.choice(FIRST)} {rng.choice(LAST)}"

        buddies = Buddy.objects.bulk_create([
            Buddy(employee_id=f"E{len(BUDDIES) + i:03}", name=name(), designation=rng.choice(BUDDY_ROLES),
                  email=f"e{len(BUDDIES) + i:03}@test.com", department=rng.choice(DEFAULT_DEPARTMENTS),
                  location=rng.choice(DEFAULT_LOCATIONS), pool_status=Buddy.PoolStatus.ACTIVE, login_code=hashed,
                  password=shared_code, interests=sample_interests(rng))
            for i in range(1, n_buddies + 1)
        ])
        Response.objects.bulk_create([Response.submitted(b, qs, answers(rng), now) for b in buddies])

        joiners = Joiner.objects.bulk_create([
            Joiner(candidate_id=f"C{len(JOINERS) + i:03}", name=name(), designation=rng.choice(JOINER_ROLES),
                   personal_email=f"c{len(JOINERS) + i:03}@test.com", department=rng.choice(DEFAULT_DEPARTMENTS),
                   location=rng.choice(DEFAULT_LOCATIONS), date_of_joining=today + timedelta(days=rng.randint(5, 45)),
                   login_code=hashed, password=shared_code, added_on=today,
                   interests=sample_interests(rng), **day_one(rng))
            for i in range(1, n_joiners + 1)
        ])
        # Every other one has answered: their match has run, so the admin can assign a buddy right away.
        answered = joiners[::2]
        Response.objects.bulk_create([Response.submitted(j, qs, answers(rng), now) for j in answered])
        # The match emails the admins when nothing is close: not for demo data.
        with override_settings(MAILERS={"default": {"BACKEND": "django.core.mail.backends.dummy.EmailBackend"}}):
            for j in answered:
                run_match_for_joiner(j)
        Notification.objects.all().delete()
        return shared_code, n_buddies + n_joiners
