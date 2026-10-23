from django.core.exceptions import ValidationError

from .models import Lote, MovimientoLote


def consumir_lotes_fefo(producto, cantidad):
    """Descuenta 'cantidad' de los lotes del producto en orden FEFO.

    Devuelve una lista de tuplas (lote, cantidad_tomada).
    Lanza ValidationError si los lotes no alcanzan a cubrir la cantidad.
    """
    if cantidad <= 0:
        return []

    restante = cantidad
    usados = []
    lotes = (
        Lote.objects.select_for_update()
        .filter(producto=producto, cantidad_actual__gt=0)
        .order_by('fecha_vencimiento', 'id_lote')
    )
    for lote in lotes:
        if restante <= 0:
            break
        tomar = min(lote.cantidad_actual, restante)
        lote.cantidad_actual -= tomar
        lote.save(update_fields=['cantidad_actual'])
        usados.append((lote, tomar))
        restante -= tomar

    if restante > 0:
        raise ValidationError(
            f"Stock en lotes insuficiente para '{producto.nombre_producto}'. "
            f"Faltan {restante} unidades en lotes (stock total: {producto.cantidad}). "
            f"Revise los lotes antes de continuar."
        )
    return usados


def registrar_consumo(movimiento, usados):
    """Guarda el detalle de lotes consumidos por un movimiento."""
    if not usados:
        return
    MovimientoLote.objects.bulk_create([
        MovimientoLote(movimiento=movimiento, lote=lote, cantidad=tomada)
        for lote, tomada in usados
    ])


def registrar_entrada(movimiento, lote):
    """Registra el lote creado por un movimiento de entrada."""
    MovimientoLote.objects.create(
        movimiento=movimiento, lote=lote, cantidad=movimiento.cantidad
    )


def revertir_movimiento(movimiento):
    """Revierte el efecto en stock y lotes de un movimiento usando sus detalles."""
    producto = movimiento.producto
    producto.refresh_from_db()
    tipo = movimiento.tipo_movimiento
    cantidad = movimiento.cantidad
    detalles = list(movimiento.lotes_afectados.select_related('lote'))

    if tipo == 'ENTRADA':
        for detalle in detalles:
            if detalle.lote.cantidad_actual < detalle.cantidad:
                raise ValidationError(
                    f"No se puede revertir la entrada: el lote "
                    f"'{detalle.lote.codigo_lote}' ya fue consumido "
                    f"(disponible {detalle.lote.cantidad_actual}, se necesitan "
                    f"{detalle.cantidad})."
                )
        producto.cantidad -= cantidad
        for detalle in detalles:
            detalle.lote.cantidad_actual -= detalle.cantidad
            detalle.lote.save(update_fields=['cantidad_actual'])
    elif tipo == 'SALIDA':
        producto.cantidad += cantidad
        for detalle in detalles:
            detalle.lote.cantidad_actual += detalle.cantidad
            detalle.lote.save(update_fields=['cantidad_actual'])
    elif tipo == 'TRASLADO_VENCIDO':
        producto.cantidad += cantidad
        producto.cantidad_vencido -= cantidad
        for detalle in detalles:
            detalle.lote.cantidad_actual += detalle.cantidad
            detalle.lote.save(update_fields=['cantidad_actual'])
    elif tipo == 'CARGA_VENCIDO':
        producto.cantidad_vencido -= cantidad
    elif tipo == 'SALIDA_VENCIDO':
        producto.cantidad_vencido += cantidad

    producto.save()
    movimiento.lotes_afectados.all().delete()


def aplicar_movimiento(movimiento):
    """Aplica stock y lotes de un movimiento nuevo o editado.

    No se usa para ENTRADA: las entradas se registran desde su flujo propio
    porque requieren crear el lote con su fecha de vencimiento.
    """
    producto = movimiento.producto
    producto.refresh_from_db()
    tipo = movimiento.tipo_movimiento
    cantidad = movimiento.cantidad

    if tipo == 'ENTRADA':
        raise ValidationError(
            "Las entradas de inventario deben registrarse desde el flujo de "
            "Entrada para poder asociar el lote y su fecha de vencimiento."
        )

    if tipo in ('SALIDA', 'TRASLADO_VENCIDO') and producto.cantidad < cantidad:
        raise ValidationError(
            f"Stock insuficiente para '{producto.nombre_producto}'. "
            f"Disponible: {producto.cantidad}, solicitado: {cantidad}."
        )

    if tipo == 'SALIDA':
        usados = consumir_lotes_fefo(producto, cantidad)
        producto.cantidad -= cantidad
        producto.save(update_fields=['cantidad'])
        registrar_consumo(movimiento, usados)
    elif tipo == 'TRASLADO_VENCIDO':
        usados = consumir_lotes_fefo(producto, cantidad)
        producto.cantidad -= cantidad
        producto.cantidad_vencido += cantidad
        producto.save(update_fields=['cantidad', 'cantidad_vencido'])
        registrar_consumo(movimiento, usados)
    elif tipo == 'CARGA_VENCIDO':
        producto.cantidad_vencido += cantidad
        producto.save(update_fields=['cantidad_vencido'])
    elif tipo == 'SALIDA_VENCIDO':
        if producto.cantidad_vencido < cantidad:
            raise ValidationError(
                f"Stock vencido insuficiente para '{producto.nombre_producto}'. "
                f"Disponible: {producto.cantidad_vencido}, solicitado: {cantidad}."
            )
        producto.cantidad_vencido -= cantidad
        producto.save(update_fields=['cantidad_vencido'])


def aplicar_entrada_existente(movimiento, lote):
    """Reaplica una entrada reutilizando el lote que ya tenía asociado."""
    if lote.producto_id != movimiento.producto_id:
        raise ValidationError(
            "No se puede cambiar el producto de una entrada existente; "
            "registre la entrada mediante el flujo de Entrada."
        )
    lote.cantidad_actual += movimiento.cantidad
    lote.save(update_fields=['cantidad_actual'])
    movimiento.producto.cantidad += movimiento.cantidad
    movimiento.producto.save(update_fields=['cantidad'])
    registrar_entrada(movimiento, lote)
