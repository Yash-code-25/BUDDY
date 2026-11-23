"""The buddy review a joiner answers after their 4-week induction (each scored 1 to 5).
The three questions are worded on the Settings page; every review keeps the wording it was answered with."""
from compass_app.models import DEFAULT_REVIEW_QUESTIONS, Settings

TITLE = "Rate your buddy"

COUNT = len(DEFAULT_REVIEW_QUESTIONS)  # the review always has three questions (Feedback.q1-q3)

# The labels for scores 1 to 5, shown to the joiner: "Not at all" is 1, "Very much" is 5.
SCALE = ["Not at all", "A little", "Somewhat", "Mostly", "Very much"]


def questions(settings=None) -> list:
    """The three questions as worded in Settings now."""
    saved = (settings or Settings.load()).review_questions
    if isinstance(saved, list) and len(saved) == COUNT and all(isinstance(q, str) and q.strip() for q in saved):
        return list(saved)
    return list(DEFAULT_REVIEW_QUESTIONS)
