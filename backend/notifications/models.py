from django.db import models


class Notification(models.Model):
    """A record of every email COMPASS has sent. The unique key stops duplicates."""
    key = models.CharField(max_length=120, unique=True)
    kind = models.CharField(max_length=40)
    to_email = models.CharField(max_length=500)
    subject = models.CharField(max_length=255)
    joiner = models.ForeignKey("compass_app.Joiner", null=True, blank=True, on_delete=models.SET_NULL)
    buddy = models.ForeignKey("compass_app.Buddy", null=True, blank=True, on_delete=models.SET_NULL)
    pairing = models.ForeignKey("compass_app.Pairing", null=True, blank=True, on_delete=models.SET_NULL)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.kind} to {self.to_email}"
