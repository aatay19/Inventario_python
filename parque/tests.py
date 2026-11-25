from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import DetalleEvento, Evento
from .views.estadisticas_views import _clave_periodo, _resumen_por_periodo
from .views.registros_views import _datos_item_detalle


class DatosItemDetalleTests(SimpleTestCase):
    def test_subtotal_es_precio_unitario_por_cantidad(self):
        datos = _datos_item_detalle({
            'tipo': 'PRODUCTO', 'id': 7, 'nombre': 'Refresco',
            'cantidad': 3, 'precio': '12.00', 'precio_unitario_original': '4.00',
        })
        self.assertEqual(datos['precio_unitario'], Decimal('4.00'))
        self.assertEqual(datos['subtotal'], Decimal('12.00'))
        self.assertEqual(datos['cantidad'], 3)

    def test_sin_unitario_se_calcula_desde_el_total(self):
        datos = _datos_item_detalle({
            'tipo': 'BRAZALETE', 'id': 1, 'nombre': 'Brazalete',
            'cantidad': 2, 'precio': '9.00',
        })
        self.assertEqual(datos['precio_unitario'], Decimal('4.50'))
        self.assertEqual(datos['subtotal'], Decimal('9.00'))

    def test_valores_invalidos_no_rompen_el_calculo(self):
        datos = _datos_item_detalle({'cantidad': 0, 'precio': 'abc'})
        self.assertEqual(datos['cantidad'], 1)
        self.assertEqual(datos['subtotal'], Decimal('0'))


class ResumenParqueTests(TestCase):
    def setUp(self):
        self.fecha = timezone.localdate()
        self.evento = Evento.objects.create(
            titulo='Fiesta de prueba', fecha_inicio=self.fecha, zona='PULPO',
            monto_abono1=Decimal('10.00'), tasa_dia=Decimal('2.00'),
            monto_abono2=Decimal('5.00'), tasa_dia2=Decimal('3.00'),
        )
        Evento.objects.create(
            titulo='Reserva sin abonos', fecha_inicio=self.fecha, zona='VENTANA'
        )
        DetalleEvento.objects.create(
            evento=self.evento, tipo_item='PRODUCTO', item_id=1,
            nombre_item='Refresco', cantidad=3,
            precio_unitario=Decimal('2.00'), subtotal=Decimal('6.00'),
        )
        DetalleEvento.objects.create(
            evento=self.evento, tipo_item='COMBO', item_id=2,
            nombre_item='Combo', cantidad=2,
            precio_unitario=Decimal('5.00'), subtotal=Decimal('10.00'),
        )
        DetalleEvento.objects.create(
            evento=self.evento, tipo_item='BRAZALETE', item_id=3,
            nombre_item='Brazalete', cantidad=4,
            precio_unitario=Decimal('4.00'), subtotal=Decimal('16.00'),
        )

    def test_resumen_diario_agrupa_eventos_zonas_items_y_abonos(self):
        resumen, anios = _resumen_por_periodo('dia')
        clave = _clave_periodo(self.fecha, 'dia')
        datos = resumen[clave]

        self.assertEqual(datos['eventos'], 2)
        self.assertEqual(datos['pulpo'], 1)
        self.assertEqual(datos['pared_blanca'], 0)
        self.assertEqual(datos['ventana'], 1)
        self.assertEqual(datos['productos'], 3)
        self.assertEqual(datos['combos'], 2)
        self.assertEqual(datos['recaudado'], Decimal('15.00'))
        self.assertEqual(datos['recaudado_bs'], Decimal('35.00'))
        self.assertIn(self.fecha.year, anios)

    def test_vista_muestra_las_metricas_del_periodo_filtrado(self):
        usuario = get_user_model().objects.create_user(
            username='parquero', password='clave123'
        )
        usuario.perfilusuario.rol = 'parque'
        usuario.perfilusuario.save()
        self.client.force_login(usuario)

        respuesta = self.client.get(
            reverse('parque:estadisticas_parque'),
            {'periodo': 'dia', 'fecha': self.fecha.isoformat()},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, 'parque/estadisticas.html')
        self.assertEqual(respuesta.context['total_eventos'], 2)
        self.assertEqual(respuesta.context['total_pulpo'], 1)
        self.assertEqual(respuesta.context['total_ventana'], 1)
        self.assertEqual(respuesta.context['total_productos'], 3)
        self.assertEqual(respuesta.context['total_combos'], 2)
        self.assertEqual(respuesta.context['total_recaudado'], Decimal('15.00'))
        self.assertEqual(respuesta.context['total_recaudado_bs'], Decimal('35.00'))

    def test_vista_sin_filtros_cuenta_el_mes_actual(self):
        usuario = get_user_model().objects.create_user(
            username='parquero-mensual', password='clave123'
        )
        usuario.perfilusuario.rol = 'parque'
        usuario.perfilusuario.save()
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse('parque:estadisticas_parque'))

        self.assertEqual(respuesta.context['periodo'], 'mensual')
        self.assertEqual(respuesta.context['total_eventos'], 2)
        self.assertEqual(respuesta.context['total_recaudado'], Decimal('15.00'))

    def test_usuario_sin_permiso_es_redirigido(self):
        usuario = get_user_model().objects.create_user(
            username='visitante', password='clave123'
        )
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse('parque:estadisticas_parque'))
        self.assertEqual(respuesta.status_code, 302)
