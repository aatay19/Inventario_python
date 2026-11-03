from django.db import migrations


DEPARTAMENTOS = [
    # (nombre, slug, orden, cantidad_de_cajas)
    ("Supermercado", "supermercado", 1, 7),
    ("Cafetín", "cafetin", 2, 1),
    ("Parque", "parque", 3, 2),
]


def crear_estructura_inicial(apps, schema_editor):
    Departamento = apps.get_model("cuadre_caja", "Departamento")
    Caja = apps.get_model("cuadre_caja", "Caja")

    for nombre, slug, orden, cantidad in DEPARTAMENTOS:
        departamento, _ = Departamento.objects.get_or_create(
            slug=slug,
            defaults={"nombre": nombre, "orden": orden, "activo": True},
        )
        for numero in range(1, cantidad + 1):
            Caja.objects.get_or_create(
                departamento=departamento,
                numero=numero,
                defaults={"nombre": f"Caja {numero}", "activo": True},
            )


def eliminar_estructura_inicial(apps, schema_editor):
    Departamento = apps.get_model("cuadre_caja", "Departamento")
    Departamento.objects.filter(
        slug__in=[slug for _, slug, _, _ in DEPARTAMENTOS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cuadre_caja", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            crear_estructura_inicial,
            eliminar_estructura_inicial,
        ),
    ]
