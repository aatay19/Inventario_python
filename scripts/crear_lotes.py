from libreria.models import Inventario, Lote
from datetime import date
from django.db import transaction

# Nueva fecha de vencimiento para los lotes iniciales (enero 2027).
# Cambia este valor si necesitas mover los lotes a otra fecha.
NUEVA_FECHA = date(2027, 3, 19)


def crear_lotes_iniciales():
    with transaction.atomic():
        # 1. Si ya existen lotes iniciales, se actualizan a la nueva fecha.
        lotes_iniciales = Lote.objects.filter(codigo_lote__startswith='LOTE-INICIAL-')
        total_existentes = lotes_iniciales.count()
        actualizados = (
            lotes_iniciales
            .exclude(fecha_vencimiento=NUEVA_FECHA)
            .update(fecha_vencimiento=NUEVA_FECHA)
        )
        print(f"Lotes iniciales existentes: {total_existentes} | actualizados a {NUEVA_FECHA}: {actualizados}")

        # 2. Crear lotes únicamente para productos con stock >= 1 que no tengan ningún lote.
        creados = 0
        for p in Inventario.objects.filter(cantidad__gte=1):
            if not Lote.objects.filter(producto=p).exists():
                Lote.objects.create(
                    producto=p,
                    codigo_lote='LOTE-INICIAL-' + p.codigo_producto,
                    fecha_vencimiento=NUEVA_FECHA,
                    cantidad_actual=p.cantidad,
                )
                creados += 1
                print(f"Lote inicial creado para: {p.nombre_producto} (Stock: {p.cantidad})")
        print(f"Lotes iniciales nuevos creados: {creados}")


crear_lotes_iniciales()
