"""The Django admin (/admin) is the developer's view of the raw data, and where the superuser adds
Program admins (Users, with "Staff status" ticked). Day-to-day work happens in COMPASS itself."""
from django.contrib import admin

from . import models


class QuestionInline(admin.TabularInline):
    model = models.Question
    extra = 0


@admin.register(models.QuestionSet)
class QuestionSetAdmin(admin.ModelAdmin):
    list_display = ("version", "is_locked", "created_at")
    inlines = [QuestionInline]


@admin.register(models.Buddy)
class BuddyAdmin(admin.ModelAdmin):
    list_display = ("name", "employee_id", "department", "location", "pool_status",
                    "total_joiners_buddied", "active_joiners")
    list_filter = ("pool_status", "department", "location", "brand", "designation_track")
    search_fields = ("name", "employee_id", "email")
    exclude = ("login_code",)
    readonly_fields = ("password",)  # sign-in checks login_code, so an edit here would not apply


@admin.register(models.Joiner)
class JoinerAdmin(admin.ModelAdmin):
    list_display = ("name", "candidate_id", "department", "location", "date_of_joining", "compass_status")
    list_filter = ("compass_status", "department", "location", "brand")
    search_fields = ("name", "candidate_id", "personal_email")
    exclude = ("login_code",)
    readonly_fields = ("password",)  # sign-in checks login_code, so an edit here would not apply


@admin.register(models.Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ("assessment_code", "buddy", "joiner", "question_set", "submitted_at")
    list_filter = ("assessment_code", "question_set")


@admin.register(models.MatchRun)
class MatchRunAdmin(admin.ModelAdmin):
    list_display = ("joiner", "run_time", "tier_reached")


@admin.register(models.Pairing)
class PairingAdmin(admin.ModelAdmin):
    list_display = ("joiner", "buddy", "source", "band", "status", "start_date", "end_date", "assigned_at")
    list_filter = ("source", "status", "band")


@admin.register(models.InductionItem)
class InductionItemAdmin(admin.ModelAdmin):
    list_display = ("week", "day", "activity", "owner", "position")


@admin.register(models.AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "object_type", "object_id")
    list_filter = ("action", "object_type")


admin.site.register(models.Settings)
