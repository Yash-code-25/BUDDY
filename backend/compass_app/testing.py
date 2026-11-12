"""What the tests share: a question set, and the joiner and buddy answers from the design spec's worked
example."""
from .models import Question, QuestionSet

J = [5, 4, 5, 4, 5]  # the worked example's joiner
WORKED = {  # and its six buddies
    "A": [3, 2, 4, 1, 3], "B": [4, 5, 4, 5, 4], "C": [5, 4, 5, 2, 5],
    "D": [5, 5, 4, 1, 5], "E": [4, 3, 3, 4, 4], "F": [3, 3, 5, 4, 3],
}


def make_question_set():
    qs = QuestionSet.objects.create(version=1)
    for n in range(1, 6):
        Question.objects.create(
            question_set=qs, number=n, dimension=f"D{n}", text=f"Q{n}?",
            label_1="a", label_2="b", label_3="c", label_4="d", label_5="e",
        )
    return qs
