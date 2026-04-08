import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventario.settings')
django.setup()

from libreria.models import Inventario, MovimientosInventario

print("Iniciando sincronización retroactiva...")
count = 0
for p in Inventario.objects.all():
    p_ids = list(MovimientosInventario.objects.filter(
        producto=p, 
        tipo_movimiento='ENTRADA', 
        proveedor__isnull=False
    ).values_list('proveedor_id', flat=True).distinct())
    
    if p_ids:
        p.proveedores.add(*p_ids)
        print(f"Sincronizado {p.nombre_producto}: {len(p_ids)} proveedores")
        count += 1

print(f"Proceso finalizado. Se actualizaron {count} productos.")
