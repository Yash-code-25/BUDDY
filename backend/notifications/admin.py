from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("sent_at", "kind", "to_email", "subject")
    list_filter = ("kind",)
    search_fields = ("to_email", "subject", "key")
