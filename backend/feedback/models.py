from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

SCORE = [MinValueValidator(1), MaxValueValidator(5)]


class Feedback(models.Model):
    """The joiner's review of their buddy after the 4-week induction: three scores and a comment.
    Only the Program admin sees it, in Reports."""
    pairing = models.OneToOneField("compass_app.Pairing", on_delete=models.CASCADE, related_name="review")
    q1 = models.PositiveSmallIntegerField(validators=SCORE)
    q2 = models.PositiveSmallIntegerField(validators=SCORE)
    q3 = models.PositiveSmallIntegerField(validators=SCORE)
    comment = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Buddy review"

    def scores(self) -> list:
        return [self.q1, self.q2, self.q3]

    def average(self):
        return round(sum(self.scores()) / 3, 2)

    def __str__(self):
        return f"Review of pairing {self.pairing_id}"
