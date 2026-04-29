import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventario.settings')
django.setup()

from libreria.models import Inventario, MovimientosInventario, Proveedor
from django.db import transaction

def sync():
    print("Analizando movimientos de inventario para encontrar relaciones...")
    
    # Obtener todos los pares (producto_id, proveedor_id) de los movimientos de entrada
    relaciones = MovimientosInventario.objects.filter(
        tipo_movimiento='ENTRADA',
        proveedor__isnull=False
    ).values_list('producto_id', 'proveedor_id').distinct()
    
    print(f"Se encontraron {len(relaciones)} relaciones potenciales.")
    
    # Organizar en un diccionario: {producto_id: [proveedor_id1, proveedor_id2, ...]}
    mapeo = {}
    for p_id, prov_id in relaciones:
        if p_id not in mapeo:
            mapeo[p_id] = []
        mapeo[p_id].append(prov_id)
    
    print(f"Sincronizando {len(mapeo)} productos...")
    
    count = 0
    with transaction.atomic():
        for p_id, prov_ids in mapeo.items():
            try:
                producto = Inventario.objects.get(id_producto=p_id)
                producto.proveedores.add(*prov_ids)
                count += 1
                if count % 100 == 0:
                    print(f"Procesados {count} productos...")
            except Inventario.DoesNotExist:
                continue
                
    print(f"Proceso finalizado. Se actualizaron {count} productos.")

if __name__ == "__main__":
    sync()
