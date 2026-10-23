from datetime import date, timedelta

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


class AjusteLoteInicialTest(BaseInventarioTest):
    def _post_data(self, producto, lote, cantidad, lote_nuevo='AJ-TEST', fecha='2027-06-30'):
        return {
            'producto_id[]': [producto.id_producto],
            'lote_inicial_id[]': [lote.id_lote],
            'cantidad[]': [cantidad],
            'lote_nuevo[]': [lote_nuevo],
            'fecha_vencimiento[]': [fecha],
        }

    def test_form_solo_muestra_productos_con_lote_inicial(self):
        p_inicial = self.crear_producto(cantidad=10)
        self.crear_lote(p_inicial, 10, 365, 'LOTE-INICIAL-P1')

        p_otro = Inventario.objects.create(
            codigo_producto='P2', nombre_producto='Producto 2',
            cantidad=10, cantidad_vencido=0, costo_actual=1,
            stock_minimo=0, stock_maximo=100,
        )
        self.crear_lote(p_otro, 10, 30, 'LOTE-NORMAL-P2')

        p_vacio = Inventario.objects.create(
            codigo_producto='P3', nombre_producto='Producto 3',
            cantidad=5, cantidad_vencido=0, costo_actual=1,
            stock_minimo=0, stock_maximo=100,
        )
        self.crear_lote(p_vacio, 0, 30, 'LOTE-INICIAL-P3')

        response = self.client.get(reverse('inventario.ajuste_lote_inicial'))

        self.assertEqual(response.status_code, 200)
        codigos = [p['codigo'] for p in response.context['productos_json']]
        self.assertEqual(codigos, ['P1'])

    def test_ajuste_mueve_cantidad_y_conserva_stock_total(self):
        p = self.crear_producto(cantidad=20)
        lote = self.crear_lote(p, 20, 365, 'LOTE-INICIAL-P1')
        data = self._post_data(p, lote, 8)

        confirmacion = self.client.post(reverse('inventario.ajuste_lote_inicial_confirmar'), data)
        self.assertEqual(confirmacion.status_code, 200)
        self.assertEqual(len(confirmacion.context['items']), 1)

        respuesta = self.client.post(reverse('inventario.ajuste_lote_inicial_procesar'), data)

        self.assertRedirects(respuesta, reverse('lotes.index'))
        p.refresh_from_db()
        lote.refresh_from_db()
        nuevo = Lote.objects.get(codigo_lote='AJ-TEST')
        self.assertEqual(p.cantidad, 20)
        self.assertEqual(lote.cantidad_actual, 12)
        self.assertEqual(nuevo.cantidad_actual, 8)
        self.assertEqual(nuevo.producto_id, p.id_producto)
        self.assertEqual(nuevo.fecha_vencimiento, date(2027, 6, 30))
        self.assertEqual(nuevo.fecha_llegada, timezone.now().date())
        self.assertEqual(MovimientosInventario.objects.count(), 0)

    def test_ajuste_rechaza_cantidad_mayor_al_lote(self):
        p = self.crear_producto(cantidad=10)
        lote = self.crear_lote(p, 10, 365, 'LOTE-INICIAL-P1')

        confirmacion = self.client.post(
            reverse('inventario.ajuste_lote_inicial_confirmar'),
            self._post_data(p, lote, 11),
        )

        self.assertRedirects(confirmacion, reverse('inventario.ajuste_lote_inicial'))
        self.assertFalse(Lote.objects.filter(codigo_lote='AJ-TEST').exists())

    def test_ajuste_rechaza_lote_que_no_es_inicial(self):
        p = self.crear_producto(cantidad=10)
        lote = self.crear_lote(p, 10, 30, 'LOTE-NORMAL-P1')

        confirmacion = self.client.post(
            reverse('inventario.ajuste_lote_inicial_confirmar'),
            self._post_data(p, lote, 5),
        )

        self.assertRedirects(confirmacion, reverse('inventario.ajuste_lote_inicial'))
        self.assertFalse(Lote.objects.filter(codigo_lote='AJ-TEST').exists())


class AjusteCantidadExactaTest(BaseInventarioTest):
    def _post_cantidad(self, producto, cantidad):
        return self.client.post(reverse('inventario.ajuste_cantidad_exacta'), {
            'producto_id': producto.id_producto,
            'cantidad': cantidad,
        })

    def test_actualiza_cantidad_exacta_y_ajusta_lotes_fefo(self):
        p = self.crear_producto(cantidad=10)
        viejo = self.crear_lote(p, 6, 10, 'L-VIEJO')
        nuevo = self.crear_lote(p, 4, 100, 'L-NUEVO')

        respuesta = self._post_cantidad(p, 7)

        self.assertRedirects(respuesta, reverse('inventario.ajuste_cantidad_exacta'))
        p.refresh_from_db()
        viejo.refresh_from_db()
        nuevo.refresh_from_db()
        self.assertEqual(p.cantidad, 7)
        self.assertEqual(viejo.cantidad_actual, 3)
        self.assertEqual(nuevo.cantidad_actual, 4)

    def test_aumenta_cantidad_en_lote_inicial(self):
        p = self.crear_producto(cantidad=5)
        lote = self.crear_lote(p, 5, 365, 'LOTE-INICIAL-P1')

        self._post_cantidad(p, 8)

        p.refresh_from_db()
        lote.refresh_from_db()
        self.assertEqual(p.cantidad, 8)
        self.assertEqual(lote.cantidad_actual, 8)

    def test_crea_lote_ajuste_si_no_hay_lotes(self):
        p = self.crear_producto(cantidad=0)

        self._post_cantidad(p, 4)

        p.refresh_from_db()
        lotes = list(Lote.objects.filter(producto=p))
        self.assertEqual(p.cantidad, 4)
        self.assertEqual(len(lotes), 1)
        self.assertTrue(lotes[0].codigo_lote.startswith('AJUSTE-'))
        self.assertEqual(lotes[0].cantidad_actual, 4)

    def test_reconcilia_lotes_con_total_desincronizado(self):
        p = self.crear_producto(cantidad=10)
        lote = self.crear_lote(p, 6, 30, 'L-UNICO')

        self._post_cantidad(p, 10)

        p.refresh_from_db()
        lote.refresh_from_db()
        self.assertEqual(p.cantidad, 10)
        self.assertEqual(lote.cantidad_actual, 10)

    def test_rechaza_cantidad_negativa(self):
        p = self.crear_producto(cantidad=10)
        lote = self.crear_lote(p, 10, 30, 'L1')

        respuesta = self._post_cantidad(p, -1)

        self.assertRedirects(respuesta, reverse('inventario.ajuste_cantidad_exacta'))
        p.refresh_from_db()
        lote.refresh_from_db()
        self.assertEqual(p.cantidad, 10)
        self.assertEqual(lote.cantidad_actual, 10)


class ProximoVencimientoIndexTest(BaseInventarioTest):
    def _producto_index(self):
        response = self.client.get(reverse('inventario.index'))
        self.assertEqual(response.status_code, 200)
        return response.context['page_obj'].object_list[0]

    def test_ignora_lote_que_fue_trasladado_a_vencido(self):
        p = self.crear_producto(cantidad=5)
        self.crear_lote(p, 0, 10, 'L-TRASLADADO')
        vigente = self.crear_lote(p, 5, 100, 'L-VIGENTE')

        producto = self._producto_index()

        self.assertEqual(producto.fecha_vencimiento_min, vigente.fecha_vencimiento)

    def test_lote_con_existencia_parcial_sigue_siendo_el_proximo(self):
        p = self.crear_producto(cantidad=6)
        parcial = self.crear_lote(p, 1, 10, 'L-PARCIAL')
        self.crear_lote(p, 5, 100, 'L-VIGENTE')

        producto = self._producto_index()

        self.assertEqual(producto.fecha_vencimiento_min, parcial.fecha_vencimiento)

    def test_sin_lotes_con_existencia_no_muestra_fecha(self):
        p = self.crear_producto(cantidad=0)
        self.crear_lote(p, 0, 10, 'L-TRASLADADO')

        producto = self._producto_index()

        self.assertIsNone(producto.fecha_vencimiento_min)


class LotesIndexBusquedaTest(BaseInventarioTest):
    def test_busca_por_nombre_de_producto(self):
        p = self.crear_producto(cantidad=5)
        lote = self.crear_lote(p, 5, 30, 'LOTE-ABC')

        response = self.client.get(reverse('lotes.index'), {'lote_q': 'Producto 1'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item.id_lote for item in response.context['page_obj'].object_list],
            [lote.id_lote],
        )

    def test_busca_por_codigo_de_lote(self):
        p = self.crear_producto(cantidad=5)
        lote = self.crear_lote(p, 5, 30, 'LOTE-ABC')

        response = self.client.get(reverse('lotes.index'), {'lote_q': 'ABC'})

        self.assertEqual(
            [item.id_lote for item in response.context['page_obj'].object_list],
            [lote.id_lote],
        )
