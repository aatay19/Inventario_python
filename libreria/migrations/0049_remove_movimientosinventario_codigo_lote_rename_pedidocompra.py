# Generated migration
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("libreria", "0048_remove_movimientolote_lote_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="pedidocompra",
            old_name="codigo_lote",
            new_name="codigo_pedido",
        ),
        migrations.RemoveField(
            model_name="movimientosinventario",
            name="codigo_lote",
        ),
    ]
