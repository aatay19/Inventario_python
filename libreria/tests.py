from django import forms
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .forms import MovimientosInventarioForm
from .models import Inventario, MovimientosInventario, Proveedor


class BaseInventarioTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tester', password='x')
        self.user.perfilusuario.rol = 'admin'
        self.user.perfilusuario.save()
        self.client = Client()
        self.client.force_login(self.user)
        self.proveedor = Proveedor.objects.create(
            razonsocial='Proveedor Test', rif='J-11111111-1',
            telefono='0000', direccion='N/A',
        )

    def crear_producto(self, cantidad=0, vencido=0):
        return Inventario.objects.create(
            codigo_producto='P1', nombre_producto='Producto 1',
            cantidad=cantidad, cantidad_vencido=vencido, costo_actual=1,
            stock_minimo=0, stock_maximo=100,
        )


class SalidaViewTest(BaseInventarioTest):
    def _post_salida(self, producto, cantidad):
        return self.client.post(reverse('movimientos.salida_procesar'), {
            'producto_id[]': [producto.id_producto],
            'unidad_empaque[]': ['UNIDAD'],
            'cant_empaques[]': [cantidad],
            'total_unidades[]': [cantidad],
            'cant_por_empaque[]': [1],
        })

    def test_salida_descuenta_stock(self):
        p = self.crear_producto(cantidad=10)
        resp = self._post_salida(p, 5)
        self.assertRedirects(resp, reverse('movimientos.historial_salidas'))
        p.refresh_from_db()
        self.assertEqual(p.cantidad, 5)

    def test_salida_insuficiente_no_cambia_stock(self):
        p = self.crear_producto(cantidad=3)
        resp = self._post_salida(p, 5)
        self.assertRedirects(resp, reverse('movimientos.salida'))
        p.refresh_from_db()
        self.assertEqual(p.cantidad, 3)


class EliminarMovimientoTest(BaseInventarioTest):
    def test_eliminar_salida_repone_stock(self):
        p = self.crear_producto(cantidad=5)
        mov = MovimientosInventario.objects.create(
            producto=p, tipo_movimiento='SALIDA', cantidad=5,
        )
        self.client.post(reverse('movimientos.eliminar', args=[mov.id_movimiento]))
        p.refresh_from_db()
        self.assertEqual(p.cantidad, 10)


class AjusteCantidadExactaTest(BaseInventarioTest):
    def test_actualiza_cantidad_exacta(self):
        p = self.crear_producto(cantidad=10)
        resp = self.client.post(reverse('inventario.ajuste_cantidad_exacta'), {
            'producto_id': p.id_producto,
            'cantidad': 25,
        })
        self.assertRedirects(resp, reverse('inventario.ajuste_cantidad_exacta'))
        p.refresh_from_db()
        self.assertEqual(p.cantidad, 25)

    def test_rechaza_cantidad_negativa(self):
        p = self.crear_producto(cantidad=10)
        resp = self.client.post(reverse('inventario.ajuste_cantidad_exacta'), {
            'producto_id': p.id_producto,
            'cantidad': -5,
        })
        self.assertRedirects(resp, reverse('inventario.ajuste_cantidad_exacta'))
        p.refresh_from_db()
        self.assertEqual(p.cantidad, 10)
