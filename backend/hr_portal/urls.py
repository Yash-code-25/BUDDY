from django.urls import path

from . import admin_views, clubs, induction, pool, reports, views

urlpatterns = [
    # signed-in admin (signing in itself is /api/auth/login/, shared with joiners and buddies)
    path("auth/logout/", views.LogoutView.as_view()),
    path("auth/me/", views.MeView.as_view()),

    # home and filters
    path("home/", admin_views.HomeView.as_view()),
    path("filters/", admin_views.FilterOptionsView.as_view()),

    # joiners
    path("joiners/", views.JoinerQueueView.as_view()),
    path("joiners/import/", views.JoinerImportView.as_view()),
    path("joiners/<int:pk>/", views.JoinerDetailView.as_view()),
    path("joiners/<int:pk>/action/", views.JoinerActionView.as_view()),
    path("joiners/<int:pk>/day-one/", views.JoinerDayOneView.as_view()),
    path("joiners/<int:pk>/assign/", views.AssignBuddyView.as_view()),

    # buddy pool
    path("buddies/", pool.BuddyListView.as_view()),
    path("buddies/groups/", pool.BuddyGroupsView.as_view()),
    path("buddies/import/", pool.BuddyImportView.as_view()),
    path("buddies/<int:pk>/", pool.BuddyDetailView.as_view()),
    path("buddies/<int:pk>/action/", pool.BuddyActionView.as_view()),

    # the 4-week induction programme
    path("induction/", induction.InductionListView.as_view()),
    path("induction/<int:pk>/", induction.InductionItemView.as_view()),

    # reports, settings, audit
    path("reports/summary/", reports.ReportSummaryView.as_view()),
    path("clubs/", clubs.ClubsView.as_view()),
    path("reports/<slug:name>/", reports.ReportView.as_view()),
    path("settings/", admin_views.SettingsView.as_view()),
    path("audit/", admin_views.AuditLogView.as_view()),
]
