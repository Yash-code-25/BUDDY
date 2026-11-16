"""The handbook, LinkedIn and Instagram links become lists, so each can hold several links with a name.
The one link each already set moves into its list."""
from django.db import migrations, models

MOVES = [("handbook_link", "handbook_links"), ("linkedin_link", "linkedin_links"),
         ("instagram_link", "instagram_links")]


def to_lists(apps, schema_editor):
    for s in apps.get_model("compass_app", "Settings").objects.all():
        for old, new in MOVES:
            url = (getattr(s, old) or "").strip()
            setattr(s, new, [{"label": "", "url": url}] if url else [])
        s.save()


def to_single(apps, schema_editor):
    for s in apps.get_model("compass_app", "Settings").objects.all():
        for old, new in MOVES:
            links = getattr(s, new) or []
            setattr(s, old, links[0]["url"] if links else "")
        s.save()


class Migration(migrations.Migration):

    dependencies = [
        ("compass_app", "0008_remove_day_one_end_time"),
    ]

    operations = [
        *[migrations.AddField(model_name="settings", name=new, field=models.JSONField(blank=True, default=list))
          for _, new in MOVES],
        migrations.RunPython(to_lists, to_single),
        *[migrations.RemoveField(model_name="settings", name=old) for old, _ in MOVES],
    ]
