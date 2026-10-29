from django.core.exceptions import ValidationError


def consumir_lotes_fefo(producto, cantidad):
    """Función de compatibilidad: en el nuevo esquema sin lotes,
    valida que el producto tenga stock suficiente y no realiza operaciones en lotes."""
    if cantidad <= 0:
        return []
    if producto.cantidad < cantidad:
        raise ValidationError(
            f"Stock insuficiente para '{producto.nombre_producto}'. "
            f"Disponible: {producto.cantidad}, solicitado: {cantidad}."
        )
    return []


def registrar_consumo(movimiento, usados):
    """Función de compatibilidad: sin lotes no se requiere detalle de consumo."""
    pass


def registrar_entrada(movimiento, lote=None):
    """Función de compatibilidad: sin lotes no se requiere registrar lote de entrada."""
    pass


def revertir_movimiento(movimiento):
    """Revierte el efecto en el stock del producto de un movimiento."""
    producto = movimiento.producto
    producto.refresh_from_db()
    tipo = movimiento.tipo_movimiento
    cantidad = movimiento.cantidad

    if tipo == 'ENTRADA':
        if producto.cantidad < cantidad:
            raise ValidationError(
                f"No se puede revertir la entrada de '{producto.nombre_producto}': "
                f"el stock actual ({producto.cantidad}) es menor a la cantidad a revertir ({cantidad})."
            )
        producto.cantidad -= cantidad
    elif tipo == 'SALIDA':
        producto.cantidad += cantidad
    elif tipo == 'TRASLADO_VENCIDO':
        producto.cantidad += cantidad
        producto.cantidad_vencido -= cantidad
    elif tipo == 'CARGA_VENCIDO':
        producto.cantidad_vencido -= cantidad
    elif tipo == 'SALIDA_VENCIDO':
        producto.cantidad_vencido += cantidad

    producto.save()


def aplicar_movimiento(movimiento):
    """Aplica el efecto de un movimiento directamente sobre el stock del producto."""
    producto = movimiento.producto
    producto.refresh_from_db()
    tipo = movimiento.tipo_movimiento
    cantidad = movimiento.cantidad

    if tipo in ('SALIDA', 'TRASLADO_VENCIDO') and producto.cantidad < cantidad:
        raise ValidationError(
            f"Stock insuficiente para '{producto.nombre_producto}'. "
            f"Disponible: {producto.cantidad}, solicitado: {cantidad}."
        )

    if tipo == 'ENTRADA':
        producto.cantidad += cantidad
        producto.save(update_fields=['cantidad'])
    elif tipo == 'SALIDA':
        producto.cantidad -= cantidad
        producto.save(update_fields=['cantidad'])
    elif tipo == 'TRASLADO_VENCIDO':
        producto.cantidad -= cantidad
        producto.cantidad_vencido += cantidad
        producto.save(update_fields=['cantidad', 'cantidad_vencido'])
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


def aplicar_entrada_existente(movimiento, lote=None):
    """Reaplica una entrada directamente sobre el stock."""
    movimiento.producto.refresh_from_db()
    movimiento.producto.cantidad += movimiento.cantidad
    movimiento.producto.save(update_fields=['cantidad'])
