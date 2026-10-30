from django.core.exceptions import ValidationError


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
