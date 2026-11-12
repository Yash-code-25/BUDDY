from django.core.management.base import BaseCommand, CommandError

from compass_app.matching import run_match_for_joiner
from compass_app.models import Joiner


class Command(BaseCommand):
    help = "Re-run the match for a joiner and print the result: python manage.py rematch C001"

    def add_arguments(self, parser):
        parser.add_argument("candidate_id")

    def handle(self, *args, **options):
        try:
            joiner = Joiner.objects.get(candidate_id=options["candidate_id"])
        except Joiner.DoesNotExist:
            raise CommandError("No joiner with that candidate id.")
        try:
            run = run_match_for_joiner(joiner)
        except ValueError as e:
            raise CommandError(str(e))

        r = run.results

        def line(c):
            flags = "; ".join(f"{f['level']}: {f['text']}" for f in c["flags"]) or "none"
            return (f"{c['name']}  {c['band']} {c['close_count']}/5  "
                    f"total gap {c['total_gap']}  flags: {flags}")

        self.stdout.write(self.style.SUCCESS(f"{joiner.name}: tier reached = {r['tier_reached']}"))
        for i, c in enumerate(r["shown"], 1):
            self.stdout.write(f"  {i}. {line(c)}")
        for c in r["more"]:
            self.stdout.write(f"  + {line(c)}")
        if not r["shown"]:
            self.stdout.write("  No suggestions. Route to manual pairing.")