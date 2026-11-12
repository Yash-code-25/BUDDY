from django.core.management.base import BaseCommand

from compass_app.models import Question, QuestionSet

QUESTIONS = [
    ("Pace", "When a new task lands, I usually…",
     ["Plan every step before starting", "Plan most of it, then start", "Plan a little, then start",
      "Start quickly with a rough idea", "Dive straight in and adjust as I go"]),
    ("Communication", "In work conversations, I prefer…",
     ["Only the key points", "Mostly brief, some detail", "A balance of both",
      "Mostly detail, some brevity", "Full detail and exploring ideas"]),
    ("Structure", "I do my best work when…",
     ["Every step is clearly defined", "There's a clear process with a little flexibility",
      "There's some structure, some freedom", "There's a loose guideline to follow",
      "I'm free to find my own way"]),
    ("Social energy", "At work, I get most energy from…",
     ["Being around people all day", "Mostly people, some quiet time", "An even mix",
      "Mostly quiet time, some people", "Quiet, focused time on my own"]),
    ("Learning", "To learn something new, I…",
     ["Read or watch everything first", "Mostly read or watch, then try", "Mix trying and reading",
      "Mostly try things, with a quick look first", "Jump in and learn by doing"]),
]


class Command(BaseCommand):
    help = "Create question set v1 with the five COMPASS questions"

    def handle(self, *args, **options):
        qs, created = QuestionSet.objects.get_or_create(version=1)
        if not created:
            self.stdout.write("v1 already exists, nothing changed.")
            return
        for number, (dimension, text, labels) in enumerate(QUESTIONS, start=1):
            Question.objects.create(
                question_set=qs, number=number, dimension=dimension, text=text,
                label_1=labels[0], label_2=labels[1], label_3=labels[2],
                label_4=labels[3], label_5=labels[4],
            )
        self.stdout.write(self.style.SUCCESS("Created question set v1 with 5 questions."))