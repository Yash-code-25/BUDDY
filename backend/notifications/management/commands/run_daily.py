from datetime import date

from django.core.management.base import BaseCommand, CommandError

from notifications.jobs import run_all


class Command(BaseCommand):
    help = (
        "Run COMPASS's day-based rules: quiz emails, reminders, manual cut-off, buddy "
        "reviews, closing finished pairings. Safe to run repeatedly. Use --today YYYY-MM-DD to pretend it is another day."
    )

    def add_arguments(self, parser):
        parser.add_argument("--today", help="Pretend today is this date (YYYY-MM-DD)")

    def handle(self, *args, **options):
        today = None
        if options["today"]:
            try:
                today = date.fromisoformat(options["today"])
            except ValueError:
                raise CommandError("--today must look like 2026-11-09")
        result = run_all(today)
        for name, count in result.items():
            self.stdout.write(f"  {name.replace('_', ' ')}: {count}")
        self.stdout.write(self.style.SUCCESS("Daily run finished."))
