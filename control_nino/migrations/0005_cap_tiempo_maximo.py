from django.db import migrations

TIEMPO_MAXIMO = 90


def cap_tiempo(apps, schema_editor):
    Fiesta = apps.get_model('control_nino', 'Fiesta')
    ControlNino = apps.get_model('control_nino', 'ControlNino')
    Fiesta.objects.filter(tiempo__gt=TIEMPO_MAXIMO).update(tiempo=TIEMPO_MAXIMO)
    ControlNino.objects.filter(tiempo__gt=TIEMPO_MAXIMO).update(tiempo=TIEMPO_MAXIMO)


class Migration(migrations.Migration):

    dependencies = [
        ('control_nino', '0004_alter_controlnino_fecha_registro_and_more'),
    ]

    operations = [
        migrations.RunPython(cap_tiempo, migrations.RunPython.noop),
    ]
