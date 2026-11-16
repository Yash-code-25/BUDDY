"""The story video link becomes a list too, so the email can show several videos, each with a name.
The one link already set moves into the list."""
from django.db import migrations, models


def to_list(apps, schema_editor):
    for s in apps.get_model("compass_app", "Settings").objects.all():
        url = (s.story_video_link or "").strip()
        s.story_video_links = [{"label": "", "url": url}] if url else []
        s.save()


def to_single(apps, schema_editor):
    for s in apps.get_model("compass_app", "Settings").objects.all():
        s.story_video_link = s.story_video_links[0]["url"] if s.story_video_links else ""
        s.save()


class Migration(migrations.Migration):

    dependencies = [
        ("compass_app", "0009_settings_link_lists"),
    ]

    operations = [
        migrations.AddField(model_name="settings", name="story_video_links",
                            field=models.JSONField(blank=True, default=list)),
        migrations.RunPython(to_list, to_single),
        migrations.RemoveField(model_name="settings", name="story_video_link"),
    ]
