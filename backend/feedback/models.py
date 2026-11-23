from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

SCORE = [MinValueValidator(1), MaxValueValidator(5)]


class LiveReviews(models.Manager):
    """Reviews by joiners who have not been deleted."""

    def get_queryset(self):
        return super().get_queryset().exclude(pairing__joiner__compass_status="DELETED")


class Feedback(models.Model):
    """The joiner's review of their buddy after the 4-week induction: three scores and a comment.
    Only the Program admin sees it, in Reports."""
    pairing = models.OneToOneField("compass_app.Pairing", on_delete=models.CASCADE, related_name="review")
    q1 = models.PositiveSmallIntegerField(validators=SCORE)
    q2 = models.PositiveSmallIntegerField(validators=SCORE)
    q3 = models.PositiveSmallIntegerField(validators=SCORE)
    comment = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    # The three questions as worded when the joiner answered, so a later rewording in Settings does not
    # change what an old score meant. Empty for reviews sent before the wording was kept.
    questions = models.JSONField(default=list, blank=True)

    objects = LiveReviews()
    all_objects = models.Manager()

    class Meta:
        verbose_name = "Buddy review"

    def scores(self) -> list:
        return [self.q1, self.q2, self.q3]

    def average(self):
        return round(sum(self.scores()) / 3, 2)

    def __str__(self):
        return f"Review of pairing {self.pairing_id}"
