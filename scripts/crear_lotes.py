from libreria.models import Inventario, Lote
from datetime import date
from django.db import transaction

def crear_lotes_iniciales():
    with transaction.atomic():
        # 1. Actualizar lotes iniciales existentes
        lotes_iniciales = Lote.objects.filter(codigo_lote__startswith='LOTE-INICIAL-')
        for lote in lotes_iniciales:
            lote.fecha_vencimiento = date(2026, 11, 20)
            lote.save()
            print(f"Lote actualizado: {lote.codigo_lote}")

        # 2. Crear nuevos para productos que no tienen ninguno
        for p in Inventario.objects.all():
            if not Lote.objects.filter(producto=p).exists():
                Lote.objects.create(
                    producto=p, 
                    codigo_lote='LOTE-INICIAL-' + p.codigo_producto, 
                    fecha_vencimiento=date(2026, 11, 20), 
                    cantidad_actual=p.cantidad
                )
                print(f"Lote inicial creado para: {p.nombre_producto}")
            else:
                # Ya existía, pero se actualizó arriba
                pass

crear_lotes_iniciales()
