from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("control_nino", "0018_controlnino_recargas"),
    ]

    operations = [
        migrations.AddField(
            model_name="fiesta",
            name="recargas",
            field=models.PositiveIntegerField(
                default=0, verbose_name="Recargas de la fiesta (+45 min)"
            ),
        ),
    ]
