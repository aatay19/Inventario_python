from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuadre_caja", "0024_remove_cierretransaccion_formato_billetes_bs"),
    ]

    operations = [
        migrations.AddField(
            model_name="egresogeneral",
            name="confirmado_banco",
            field=models.CharField(
                blank=True,
                choices=[("SI", "Sí"), ("NO", "No")],
                default="",
                max_length=2,
                verbose_name="Confirmado por el banco",
            ),
        ),
    ]
