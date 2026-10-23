from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import MovimientosInventarioForm
from .models import Inventario, Lote, MovimientoLote, MovimientosInventario, Proveedor
from .servicios_lotes import consumir_lotes_fefo


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

    def crear_lote(self, producto, cantidad, dias, codigo):
        return Lote.objects.create(
            producto=producto, codigo_lote=codigo,
            fecha_vencimiento=timezone.now().date() + timedelta(days=dias),
            cantidad_actual=cantidad,
        )


class ConsumirLotesFefoTest(BaseInventarioTest):
    def test_consume_lote_mas_antiguo_primero(self):
        p = self.crear_producto(cantidad=10)
        viejo = self.crear_lote(p, 4, 10, 'L-VIEJO')
        nuevo = self.crear_lote(p, 6, 100, 'L-NUEVO')

        usados = consumir_lotes_fefo(p, 5)

        viejo.refresh_from_db()
        nuevo.refresh_from_db()
        self.assertEqual(usados, [(viejo, 4), (nuevo, 1)])
        self.assertEqual(viejo.cantidad_actual, 0)
        self.assertEqual(nuevo.cantidad_actual, 5)

    def test_insuficiente_lanza_error(self):
        p = self.crear_producto(cantidad=10)
        self.crear_lote(p, 3, 10, 'L1')

        with self.assertRaises(forms.ValidationError):
            consumir_lotes_fefo(p, 5)


class SalidaViewTest(BaseInventarioTest):
    def _post_salida(self, producto, cantidad):
        return self.client.post(reverse('movimientos.salida_procesar'), {
            'producto_id[]': [producto.id_producto],
            'unidad_empaque[]': ['UNIDAD'],
            'cant_empaques[]': [cantidad],
            'total_unidades[]': [cantidad],
        })

    def test_salida_consume_lotes_y_crea_detalle(self):
        p = self.crear_producto(cantidad=10)
        lote = self.crear_lote(p, 10, 30, 'L1')

        self._post_salida(p, 4)

        p.refresh_from_db()
        lote.refresh_from_db()
        self.assertEqual(p.cantidad, 6)
        self.assertEqual(lote.cantidad_actual, 6)
        mov = MovimientosInventario.objects.get(tipo_movimiento='SALIDA')
        self.assertEqual(mov.lotes_afectados.count(), 1)
        self.assertEqual(mov.lotes_afectados.first().cantidad, 4)

    def test_salida_sin_lotes_suficientes_no_cambia_nada(self):
        p = self.crear_producto(cantidad=10)
        self.crear_lote(p, 3, 30, 'L1')

        self._post_salida(p, 5)

        p.refresh_from_db()
        self.assertEqual(p.cantidad, 10)
        self.assertEqual(Lote.objects.get(codigo_lote='L1').cantidad_actual, 3)
        self.assertFalse(MovimientosInventario.objects.filter(tipo_movimiento='SALIDA').exists())


class EliminarMovimientoTest(BaseInventarioTest):
    def test_eliminar_entrada_revierte_lote(self):
        p = self.crear_producto(cantidad=10)
        mov = MovimientosInventario.objects.create(
            producto=p, tipo_movimiento='ENTRADA', cantidad=10)
        lote = self.crear_lote(p, 10, 30, 'L1')
        MovimientoLote.objects.create(movimiento=mov, lote=lote, cantidad=10)

        self.client.post(reverse('movimientos.eliminar', args=[mov.id_movimiento]))

        p.refresh_from_db()
        lote.refresh_from_db()
        self.assertEqual(p.cantidad, 0)
        self.assertEqual(lote.cantidad_actual, 0)
        self.assertFalse(MovimientosInventario.objects.filter(pk=mov.pk).exists())

    def test_eliminar_entrada_consumida_bloquea(self):
        p = self.crear_producto(cantidad=10)
        mov = MovimientosInventario.objects.create(
            producto=p, tipo_movimiento='ENTRADA', cantidad=10)
        lote = self.crear_lote(p, 5, 30, 'L1')
        MovimientoLote.objects.create(movimiento=mov, lote=lote, cantidad=10)

        self.client.post(reverse('movimientos.eliminar', args=[mov.id_movimiento]))

        p.refresh_from_db()
        lote.refresh_from_db()
        self.assertEqual(p.cantidad, 10)
        self.assertEqual(lote.cantidad_actual, 5)
        self.assertTrue(MovimientosInventario.objects.filter(pk=mov.pk).exists())

    def test_eliminar_salida_repone_lote(self):
        p = self.crear_producto(cantidad=6)
        lote = self.crear_lote(p, 6, 30, 'L1')
        mov = MovimientosInventario.objects.create(
            producto=p, tipo_movimiento='SALIDA', cantidad=4)
        MovimientoLote.objects.create(movimiento=mov, lote=lote, cantidad=4)

        self.client.post(reverse('movimientos.eliminar', args=[mov.id_movimiento]))

        p.refresh_from_db()
        lote.refresh_from_db()
        self.assertEqual(p.cantidad, 10)
        self.assertEqual(lote.cantidad_actual, 10)


class EditarMovimientoFormTest(BaseInventarioTest):
    def test_editar_salida_ajusta_lotes(self):
        p = self.crear_producto(cantidad=6)
        lote = self.crear_lote(p, 6, 30, 'L1')
        mov = MovimientosInventario.objects.create(
            producto=p, tipo_movimiento='SALIDA', cantidad=4)
        MovimientoLote.objects.create(movimiento=mov, lote=lote, cantidad=4)

        form = MovimientosInventarioForm(data={
            'producto': p.id_producto, 'tipo_movimiento': 'SALIDA',
            'unidad_empaque': 'UNIDAD', 'cantidad_empaques': 2, 'cantidad': 2,
        }, instance=mov)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        mov.refresh_from_db()
        p.refresh_from_db()
        lote.refresh_from_db()
        self.assertEqual(mov.cantidad, 2)
        self.assertEqual(p.cantidad, 8)
        self.assertEqual(lote.cantidad_actual, 8)
        self.assertEqual(mov.lotes_afectados.count(), 1)
        self.assertEqual(mov.lotes_afectados.first().cantidad, 2)

    def test_editar_entrada_ajusta_lote(self):
        p = self.crear_producto(cantidad=10)
        mov = MovimientosInventario.objects.create(
            producto=p, tipo_movimiento='ENTRADA', cantidad=10, proveedor=self.proveedor)
        lote = self.crear_lote(p, 10, 30, 'L1')
        MovimientoLote.objects.create(movimiento=mov, lote=lote, cantidad=10)

        form = MovimientosInventarioForm(data={
            'producto': p.id_producto, 'tipo_movimiento': 'ENTRADA',
            'unidad_empaque': 'UNIDAD', 'cantidad_empaques': 6, 'cantidad': 6,
            'proveedor': self.proveedor.id,
        }, instance=mov)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        mov.refresh_from_db()
        p.refresh_from_db()
        lote.refresh_from_db()
        self.assertEqual(mov.cantidad, 6)
        self.assertEqual(p.cantidad, 6)
        self.assertEqual(lote.cantidad_actual, 6)

    def test_no_permite_convertir_a_entrada(self):
        p = self.crear_producto(cantidad=10)
        mov = MovimientosInventario.objects.create(
            producto=p, tipo_movimiento='CARGA_VENCIDO', cantidad=2)

        form = MovimientosInventarioForm(data={
            'producto': p.id_producto, 'tipo_movimiento': 'ENTRADA',
            'unidad_empaque': 'UNIDAD', 'cantidad_empaques': 1, 'cantidad': 1,
            'proveedor': self.proveedor.id,
        }, instance=mov)
        self.assertFalse(form.is_valid())


class LoteEditarViewTest(BaseInventarioTest):
    def test_editar_lote_salida_ajusta_lotes(self):
        p = self.crear_producto(cantidad=6)
        lote = self.crear_lote(p, 6, 30, 'L1')
        mov = MovimientosInventario.objects.create(
            producto=p, tipo_movimiento='SALIDA', cantidad=4, codigo_lote='S1')
        MovimientoLote.objects.create(movimiento=mov, lote=lote, cantidad=4)

        self.client.post(reverse('movimientos.lote_editar', args=['S1']), {
            f'cantidad_{mov.id_movimiento}': 1,
            f'unidad_{mov.id_movimiento}': 'UNIDAD',
        })

        mov.refresh_from_db()
        p.refresh_from_db()
        lote.refresh_from_db()
        self.assertEqual(mov.cantidad, 1)
        self.assertEqual(p.cantidad, 9)
        self.assertEqual(lote.cantidad_actual, 9)

    def test_editar_lote_cero_elimina_y_revierte(self):
        p = self.crear_producto(cantidad=6)
        lote = self.crear_lote(p, 6, 30, 'L1')
        mov = MovimientosInventario.objects.create(
            producto=p, tipo_movimiento='SALIDA', cantidad=4, codigo_lote='S1')
        MovimientoLote.objects.create(movimiento=mov, lote=lote, cantidad=4)

        self.client.post(reverse('movimientos.lote_editar', args=['S1']), {
            f'cantidad_{mov.id_movimiento}': 0,
        })

        p.refresh_from_db()
        lote.refresh_from_db()
        self.assertFalse(MovimientosInventario.objects.filter(pk=mov.pk).exists())
        self.assertEqual(p.cantidad, 10)
        self.assertEqual(lote.cantidad_actual, 10)


class LoteEliminarViewTest(BaseInventarioTest):
    def test_eliminar_lote_entrada_revierte_todos(self):
        p = self.crear_producto(cantidad=15)
        mov1 = MovimientosInventario.objects.create(
            producto=p, tipo_movimiento='ENTRADA', cantidad=10, codigo_lote='E1')
        lote1 = self.crear_lote(p, 10, 30, 'L1')
        MovimientoLote.objects.create(movimiento=mov1, lote=lote1, cantidad=10)
        mov2 = MovimientosInventario.objects.create(
            producto=p, tipo_movimiento='ENTRADA', cantidad=5, codigo_lote='E1')
        lote2 = self.crear_lote(p, 5, 60, 'L2')
        MovimientoLote.objects.create(movimiento=mov2, lote=lote2, cantidad=5)

        self.client.post(reverse('movimientos.lote_eliminar'), {'lote_id': 'E1'})

        p.refresh_from_db()
        lote1.refresh_from_db()
        lote2.refresh_from_db()
        self.assertEqual(p.cantidad, 0)
        self.assertEqual(lote1.cantidad_actual, 0)
        self.assertEqual(lote2.cantidad_actual, 0)
        self.assertFalse(MovimientosInventario.objects.filter(codigo_lote='E1').exists())
