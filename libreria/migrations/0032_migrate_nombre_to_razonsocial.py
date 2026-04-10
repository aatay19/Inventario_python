from django.db import migrations

def migrate_nombre_to_razonsocial(apps, schema_editor):
    Proveedor = apps.get_model('libreria', 'Proveedor')
    for p in Proveedor.objects.all():
        # Si la razon social esta vacia o tiene comillas literales
        if not p.razonsocial or p.razonsocial.strip() in ['', '""', '" "']:
            p.razonsocial = p.nombre
            p.save()

def reverse_migrate(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('libreria', '0031_alter_proveedor_nombre'),
    ]
    operations = [
        migrations.RunPython(migrate_nombre_to_razonsocial, reverse_migrate),
    ]
