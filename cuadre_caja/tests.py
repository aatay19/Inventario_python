import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import DataError, IntegrityError, OperationalError
from django.http import QueryDict
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import (
    CierreCajaForm,
    CierreTransaccionForm,
    CierreTransaccionFormSet,
    EgresoCierreForm,
    EgresoCierreFormSet,
    EgresoGeneralForm,
    ImagenCierreForm,
    ImagenCierreFormSet,
)
from .models import (
    BorradorCierre,
    Caja,
    CierreCaja,
    CierreTransaccion,
    Departamento,
    EgresoCierre,
    MONEDA_BS,
    NovedadCierre,
)
from .views import (
    MAX_DECIMAL_14,
    _decimal,
    _describir_error_sistema,
    _formatear_errores_cierre,
    _mensaje_error_sistema,
    _normalizar_novedades,
    _normalizar_transacciones_post,
    _novedades_desde_post,
    _reconstruir_borrador_desde_post,
)


def _post(pares):
    """QueryDict equivalente al POST real (las claves repetidas se acumulan)."""
    datos = QueryDict("", mutable=True)
    for clave, valor in pares:
        datos.appendlist(clave, valor)
    return datos


def _gestion(total):
    return [
        ("transacciones-TOTAL_FORMS", str(total)),
        ("transacciones-INITIAL_FORMS", "0"),
        ("transacciones-MIN_NUM_FORMS", "0"),
        ("transacciones-MAX_NUM_FORMS", "1000"),
    ]


class NormalizacionTransaccionesTests(SimpleTestCase):
    """El cuadre nunca debe perder filas por un prefijo inconsistente.

    Django solo lee las claves ``transacciones-<n>-<campo>`` con ``n`` dentro
    de ``TOTAL_FORMS``; cualquier otra se descarta en silencio, de modo que el
    cierre se guardaría incompleto y sin errores.
    """

    def test_filas_con_indices_normales_se_conservan(self):
        post = _normalizar_transacciones_post(_post(_gestion(2) + [
            ("transacciones-0-metodo_pago", "EFECTIVO_BS"),
            ("transacciones-0-banco", "Banesco"),
            ("transacciones-0-monto", "150.00"),
            ("transacciones-0-ref", ""),
            ("transacciones-0-notas", ""),
            ("transacciones-1-metodo_pago", "PAGO_MOVIL"),
            ("transacciones-1-banco", "Mercantil"),
            ("transacciones-1-monto", "80.00"),
            ("transacciones-1-ref", "1234"),
            ("transacciones-1-notas", ""),
        ]))

        self.assertEqual(post["transacciones-TOTAL_FORMS"], "2")
        formset = CierreTransaccionFormSet(
            post, prefix="transacciones", instance=CierreCaja()
        )
        self.assertTrue(formset.is_valid())
        filas = formset.save(commit=False)
        self.assertEqual(
            [(f.metodo_pago, f.banco, str(f.monto)) for f in filas],
            [
                ("EFECTIVO_BS", "Banesco", "150.00"),
                ("PAGO_MOVIL", "Mercantil", "80.00"),
            ],
        )

    def test_prefijo_no_numerico_se_renumera_y_no_se_pierde(self):
        # Fila insertada por el navegador con el marcador "TEMP".
        post = _normalizar_transacciones_post(_post(_gestion(2) + [
            ("transacciones-0-metodo_pago", "EFECTIVO_BS"),
            ("transacciones-0-banco", ""),
            ("transacciones-0-monto", ""),
            ("transacciones-0-ref", ""),
            ("transacciones-0-notas", ""),
            ("transacciones-TEMP-metodo_pago", "ZELLE"),
            ("transacciones-TEMP-banco", ""),
            ("transacciones-TEMP-monto", "25.00"),
            ("transacciones-TEMP-ref", "999"),
            ("transacciones-TEMP-notas", ""),
        ]))

        formset = CierreTransaccionFormSet(
            post, prefix="transacciones", instance=CierreCaja()
        )
        self.assertTrue(formset.is_valid())
        filas = formset.save(commit=False)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0].metodo_pago, "ZELLE")
        self.assertEqual(str(filas[0].monto), "25.00")

    def test_varias_filas_con_el_mismo_prefijo_se_separan(self):
        post = _normalizar_transacciones_post(_post(_gestion(2) + [
            ("transacciones-TEMP-metodo_pago", "EFECTIVO_BS"),
            ("transacciones-TEMP-banco", "Banesco"),
            ("transacciones-TEMP-monto", "100.00"),
            ("transacciones-TEMP-ref", "111"),
            ("transacciones-TEMP-notas", ""),
            ("transacciones-TEMP-metodo_pago", "EFECTIVO_USD"),
            ("transacciones-TEMP-banco", ""),
            ("transacciones-TEMP-monto", "20.00"),
            ("transacciones-TEMP-ref", "222"),
            ("transacciones-TEMP-notas", ""),
        ]))

        formset = CierreTransaccionFormSet(
            post, prefix="transacciones", instance=CierreCaja()
        )
        self.assertTrue(formset.is_valid())
        filas = formset.save(commit=False)
        self.assertEqual(
            [(f.metodo_pago, str(f.monto), f.ref) for f in filas],
            [
                ("EFECTIVO_BS", "100.00", "111"),
                ("EFECTIVO_USD", "20.00", "222"),
            ],
        )

    def test_indices_fuera_de_total_forms_se_recuperan(self):
        post = _normalizar_transacciones_post(_post(_gestion(1) + [
            ("transacciones-0-metodo_pago", "EFECTIVO_BS"),
            ("transacciones-0-banco", ""),
            ("transacciones-0-monto", "10.00"),
            ("transacciones-0-ref", ""),
            ("transacciones-0-notas", ""),
            ("transacciones-7-metodo_pago", "TRANSFERENCIA"),
            ("transacciones-7-banco", "Venezuela"),
            ("transacciones-7-monto", "300.00"),
            ("transacciones-7-ref", "888"),
            ("transacciones-7-notas", ""),
        ]))

        self.assertEqual(post["transacciones-TOTAL_FORMS"], "2")
        formset = CierreTransaccionFormSet(
            post, prefix="transacciones", instance=CierreCaja()
        )
        self.assertTrue(formset.is_valid())
        self.assertEqual(len(formset.save(commit=False)), 2)

    def test_filas_vacias_siguen_ignorandose(self):
        post = _normalizar_transacciones_post(_post(_gestion(1) + [
            ("transacciones-0-metodo_pago", "BIO_PAGO"),
            ("transacciones-0-banco", ""),
            ("transacciones-0-monto", ""),
            ("transacciones-0-ref", ""),
            ("transacciones-0-notas", ""),
        ]))

        formset = CierreTransaccionFormSet(
            post, prefix="transacciones", instance=CierreCaja()
        )
        self.assertTrue(formset.is_valid())
        self.assertEqual(len(formset.save(commit=False)), 0)

    def test_management_form_no_se_altera(self):
        post = _normalizar_transacciones_post(_post(_gestion(1) + [
            ("transacciones-0-metodo_pago", "EFECTIVO_BS"),
            ("transacciones-0-monto", "1.00"),
        ]))

        self.assertEqual(post["transacciones-INITIAL_FORMS"], "0")
        self.assertEqual(post["transacciones-MIN_NUM_FORMS"], "0")
        self.assertGreaterEqual(int(post["transacciones-MAX_NUM_FORMS"]), 1000)


class BancosHeredadosTests(SimpleTestCase):
    """Un banco fuera de BANCOS_CHOICES no debe bloquear ni perderse.

    El modelo guarda el banco como texto libre y los cierres históricos pueden
    tener entidades que ya no están en la lista. Si el ``<select>`` no puede
    mostrar el valor, al recuperar un borrador se pierde el banco; si el valor
    se reenvía, Django invalida el formulario y el cierre no se guarda.
    """

    def test_banco_heredado_se_muestra_en_el_select(self):
        form = CierreTransaccionForm(
            initial={
                "metodo_pago": "PAGO_MOVIL",
                "banco": "Bancamiga",
                "monto": "10.00",
            }
        )
        self.assertIn("Bancamiga", [v for v, _ in form.fields["banco"].choices])
        self.assertIn('value="Bancamiga" selected', str(form["banco"]))

    def test_banco_heredado_enviado_no_invalida_el_formulario(self):
        form = CierreTransaccionForm(
            data={
                "metodo_pago": "PAGO_MOVIL",
                "banco": "Bancamiga",
                "monto": "10.00",
                "ref": "",
                "notas": "",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["banco"], "Bancamiga")

    def test_formset_conserva_el_banco_heredado(self):
        post = _post(
            _gestion(1)
            + [
                ("transacciones-0-metodo_pago", "TRANSFERENCIA"),
                ("transacciones-0-banco", "Banco Nacional de Crédito"),
                ("transacciones-0-monto", "500.00"),
                ("transacciones-0-ref", "123"),
                ("transacciones-0-notas", ""),
            ]
        )
        formset = CierreTransaccionFormSet(
            post, prefix="transacciones", instance=CierreCaja()
        )
        self.assertTrue(formset.is_valid(), formset.errors)
        filas = formset.save(commit=False)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0].banco, "Banco Nacional de Crédito")


class LongitudesFormulariosTests(SimpleTestCase):
    """Los textos largos deben dar un error claro, no un DataError de MySQL.

    La base de datos usa STRICT_TRANS_TABLES: un valor que excede el
    ``max_length`` del modelo aborta el guardado con un error críptico.
    """

    def test_referencia_de_transaccion_maxima(self):
        form = CierreTransaccionForm(
            data={
                "metodo_pago": "PAGO_MOVIL",
                "banco": "",
                "monto": "10.00",
                "ref": "1" * 101,
                "notas": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("ref", form.errors)

    def test_salida_respeta_longitudes_del_modelo(self):
        form = EgresoCierreForm(
            data={
                "tipo": "EGRESO",
                "cedula": "1" * 21,
                "telefono": "1" * 31,
                "banco": "Banesco",
                "moneda": "BS",
                "monto": "10.00",
                "referencia": "1" * 101,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("cedula", form.errors)
        self.assertIn("telefono", form.errors)
        self.assertIn("referencia", form.errors)

    def test_motivo_del_egreso_general_maximo(self):
        form = EgresoGeneralForm(
            data={
                "tipo": "EGRESO",
                "cedula": "",
                "telefono": "",
                "banco": "",
                "moneda": "BS",
                "monto": "10.00",
                "referencia": "",
                "motivo": "x" * 201,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("motivo", form.errors)

    def test_titulo_de_imagen_maximo(self):
        form = ImagenCierreForm(data={"titulo": "x" * 151})
        self.assertFalse(form.is_valid())
        self.assertIn("titulo", form.errors)


class TotalesCierreTests(SimpleTestCase):
    """Los montos solo-lectura no deben invalidar un cierre válido."""

    def test_total_grande_no_bloquea_el_cierre(self):
        form = CierreCajaForm(
            data={
                "turno": "AM",
                "nombre_cajera": "Ana",
                "tasa": "36.50",
                "observaciones": "",
                "monto_EFECTIVO_BS": "1234567890123.45",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_tasa_negativa_se_rechaza(self):
        form = CierreCajaForm(
            data={
                "turno": "AM",
                "nombre_cajera": "Ana",
                "tasa": "-1",
                "observaciones": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("tasa", form.errors)


class DecimalBorradorTests(SimpleTestCase):
    """El borrador nunca debe romper el guardado por un número inválido."""

    def test_valor_excesivo_se_acota_al_maximo_del_campo(self):
        self.assertEqual(
            _decimal("9" * 18, limite=MAX_DECIMAL_14), MAX_DECIMAL_14
        )
        self.assertEqual(
            _decimal("-" + "9" * 18, limite=MAX_DECIMAL_14), -MAX_DECIMAL_14
        )

    def test_nan_e_infinito_no_llegan_a_la_base_de_datos(self):
        for valor in ("NaN", "Infinity", "-Infinity", "no-es-numero", None, ""):
            numero = _decimal(valor, limite=MAX_DECIMAL_14)
            self.assertTrue(numero.is_finite())
            self.assertEqual(numero, 0)

    def test_valor_normal_se_conserva(self):
        self.assertEqual(str(_decimal("1234.567")), "1234.57")


def _gestion_formset(prefix, total=1):
    """QueryDict con solo el management form de un formset."""
    datos = QueryDict("", mutable=True)
    datos[f"{prefix}-TOTAL_FORMS"] = str(total)
    datos[f"{prefix}-INITIAL_FORMS"] = "0"
    datos[f"{prefix}-MIN_NUM_FORMS"] = "0"
    datos[f"{prefix}-MAX_NUM_FORMS"] = "1000"
    return datos


class ErroresDetalladosTests(SimpleTestCase):
    """La alerta debe decir qué falló y no dar por perdido ningún dato."""

    def _formulario_invalido(self):
        return CierreCajaForm(
            {
                "turno": "AM",
                "nombre_cajera": "<b>" + "x" * 120,
                "tasa": "-5",
                "observaciones": "",
            },
            caja=None,
            turno=None,
        )

    def _formset_transacciones(self):
        datos = _gestion_formset("transacciones")
        datos["transacciones-0-metodo_pago"] = "PAGO_MOVIL"
        datos["transacciones-0-banco"] = "Banesco"
        datos["transacciones-0-monto"] = "0"
        datos["transacciones-0-ref"] = "<script>alert(1)</script>"
        datos["transacciones-0-notas"] = ""
        formset = CierreTransaccionFormSet(
            datos, prefix="transacciones", instance=CierreCaja()
        )
        formset.is_valid()
        return formset

    def _formset_vacio(self, factory, prefix):
        formset = factory(
            _gestion_formset(prefix), prefix=prefix, instance=CierreCaja()
        )
        formset.is_valid()
        return formset

    def _html(self, borrador_actualizado=True):
        form = self._formulario_invalido()
        form.is_valid()
        return _formatear_errores_cierre(
            form,
            self._formset_vacio(EgresoCierreFormSet, "egresos"),
            self._formset_transacciones(),
            self._formset_vacio(ImagenCierreFormSet, "imagenes"),
            borrador_actualizado,
        )

    def test_avisa_que_no_se_guardo_nada(self):
        html = self._html()
        self.assertIn("No se guardó el cierre", html)
        self.assertIn("no se registró ningún cuadre", html)

    def test_identifica_campo_valor_y_fila(self):
        html = self._html()
        self.assertIn("Nombre de la cajera", html)
        self.assertIn("Tasa del día", html)
        self.assertIn("La tasa no puede ser negativa.", html)
        # La fila se identifica por su método y posición, no por un índice global.
        self.assertIn("Pago Móvil, fila 1", html)
        self.assertIn("El monto debe ser mayor a cero.", html)

    def test_escapa_los_valores_del_usuario(self):
        html = self._html()
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;b&gt;", html)
        self.assertNotIn("<b>" + "x" * 10, html)

    def test_indica_si_el_borrador_se_actualizo(self):
        self.assertIn("el borrador se actualizó", self._html(True))
        self.assertIn("no recargues la página", self._html(False))

    def test_fila_sin_metodo_se_identifica(self):
        form = CierreCajaForm(
            {
                "turno": "AM",
                "nombre_cajera": "Ana",
                "tasa": "36.50",
                "observaciones": "",
            },
            caja=None,
            turno=None,
        )
        form.is_valid()
        datos = _gestion_formset("transacciones")
        datos["transacciones-0-metodo_pago"] = ""
        datos["transacciones-0-banco"] = "Banesco"
        datos["transacciones-0-monto"] = "10.00"
        datos["transacciones-0-ref"] = ""
        datos["transacciones-0-notas"] = ""
        formset = CierreTransaccionFormSet(
            datos, prefix="transacciones", instance=CierreCaja()
        )
        formset.is_valid()
        html = _formatear_errores_cierre(
            form,
            self._formset_vacio(EgresoCierreFormSet, "egresos"),
            formset,
            self._formset_vacio(ImagenCierreFormSet, "imagenes"),
            True,
        )
        self.assertIn("Fila sin método de pago, fila 1", html)
        self.assertIn("Selecciona un método de pago", html)


class ErrorSistemaTests(SimpleTestCase):
    """Un fallo al guardar debe hablar de rollback y de la causa concreta."""

    def test_cierre_duplicado_se_explica(self):
        detalle, _ = _describir_error_sistema(IntegrityError("Duplicate entry"))
        self.assertIn("Ya existe un cierre", detalle)

    def test_error_de_datos_apunta_a_texto_o_monto(self):
        detalle, _ = _describir_error_sistema(DataError("Data too long"))
        self.assertIn("texto demasiado largo o monto fuera de rango", detalle)

    def test_error_de_conexion_se_explica(self):
        detalle, _ = _describir_error_sistema(OperationalError("down"))
        self.assertIn("base de datos", detalle)

    def test_alerta_menciona_el_rollback(self):
        html = _mensaje_error_sistema(RuntimeError("boom"), True)
        self.assertIn("No se guardó el cierre", html)
        self.assertIn("Se revirtió todo (rollback)", html)
        self.assertIn("Tus datos están a salvo", html)

    def test_detalle_tecnico_se_escapa(self):
        html = _mensaje_error_sistema(RuntimeError("<img src=x onerror=alert(1)>"), True)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;img src=x", html)

    def test_sin_turno_no_toca_la_base_de_datos(self):
        self.assertIsNone(
            _reconstruir_borrador_desde_post(None, None, "", None, QueryDict())
        )


class MetodoHeredadoTests(SimpleTestCase):
    """Una fila con método desconocido se muestra y se puede corregir."""

    def test_metodo_desconocido_se_muestra_en_el_select(self):
        form = CierreTransaccionForm(
            data={
                "metodo_pago": "METODO_VIEJO",
                "banco": "",
                "monto": "10.00",
                "ref": "",
                "notas": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("metodo_pago", form.errors)
        self.assertIn(
            "METODO_VIEJO", [valor for valor, _ in form.fields["metodo_pago"].choices]
        )
        self.assertIn('value="METODO_VIEJO"', str(form["metodo_pago"]))


class NovedadesTests(SimpleTestCase):
    """Las novedades conservan solo lo eliminado con monto y/o referencia."""

    def test_solo_conserva_con_monto_o_referencia(self):
        novedades = _normalizar_novedades(
            [
                {"metodo_pago": "EFECTIVO_BS", "monto": "10.50", "ref": ""},
                {"metodo_pago": "PAGO_MOVIL", "monto": "0", "ref": "123"},
                {"metodo_pago": "ZELLE", "monto": "0", "ref": ""},
                {"metodo_pago": "METODO_INVALIDO", "monto": "5", "ref": "1"},
            ]
        )
        self.assertEqual(
            [n["metodo_pago"] for n in novedades], ["EFECTIVO_BS", "PAGO_MOVIL"]
        )

    def test_json_invalido_no_rompe_el_cierre(self):
        self.assertEqual(
            _novedades_desde_post({"novedades_json": "no-es-json"}), []
        )
        self.assertEqual(
            _novedades_desde_post({"novedades_json": '{"no": "es lista"}'}), []
        )


class NovedadesGuardadoTests(TestCase):
    """Las novedades eliminadas se conservan junto con el cierre."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_superuser(
            username="novedades_test", email="", password="clave123"
        )
        departamento = Departamento.objects.create(
            nombre="Prueba novedades", slug="prueba-novedades"
        )
        self.caja = Caja.objects.create(
            departamento=departamento, nombre="Caja novedades", numero=99
        )
        self.client.force_login(self.usuario)

    def test_novedades_se_guardan_con_el_cierre(self):
        datos = {
            "turno": "AM",
            "nombre_cajera": "Cajera de prueba",
            "tasa": "0.00",
            "observaciones": "",
            "novedades_json": json.dumps(
                [
                    {
                        "metodo_pago": "EFECTIVO_BS",
                        "banco": "Banesco",
                        "monto": "50.00",
                        "ref": "",
                        "notas": "Monto eliminado",
                    },
                    {
                        "metodo_pago": "ZELLE",
                        "banco": "",
                        "monto": "0",
                        "ref": "ABC123",
                        "notas": "",
                    },
                    # Sin monto ni referencia: no debe registrarse.
                    {
                        "metodo_pago": "PUNTO_VENTA",
                        "banco": "",
                        "monto": "0",
                        "ref": "",
                        "notas": "",
                    },
                ]
            ),
        }
        datos.update(dict(_gestion(0)))
        datos.update(
            {
                "egresos-TOTAL_FORMS": "0",
                "egresos-INITIAL_FORMS": "0",
                "egresos-MIN_NUM_FORMS": "0",
                "egresos-MAX_NUM_FORMS": "1000",
                "imagenes-TOTAL_FORMS": "0",
                "imagenes-INITIAL_FORMS": "0",
                "imagenes-MIN_NUM_FORMS": "0",
                "imagenes-MAX_NUM_FORMS": "1000",
            }
        )

        respuesta = self.client.post(
            reverse("cuadre_caja:cerrar_caja", args=[self.caja.id]), datos
        )
        self.assertEqual(respuesta.status_code, 302)

        cierre = CierreCaja.objects.get(caja=self.caja, turno="AM")
        novedades = list(NovedadCierre.objects.filter(cierre=cierre).order_by("id"))
        self.assertEqual(
            [(n.metodo_pago, str(n.monto), n.ref) for n in novedades],
            [("EFECTIVO_BS", "50.00", ""), ("ZELLE", "0.00", "ABC123")],
        )
        self.assertEqual(novedades[0].usuario, self.usuario)

        detalle = self.client.get(
            reverse("cuadre_caja:cierre_detalle", args=[cierre.id])
        )
        self.assertContains(detalle, "Novedades")
        self.assertContains(detalle, "ABC123")

        inicio = self.client.get(reverse("cuadre_caja:index"))
        self.assertContains(inicio, reverse("cuadre_caja:novedades"))

        listado = self.client.get(reverse("cuadre_caja:novedades"))
        self.assertContains(listado, "ABC123")

    def test_ajuste_que_quita_transaccion_crea_novedad(self):
        cierre = CierreCaja.objects.create(
            caja=self.caja,
            fecha=timezone.localdate(),
            turno="PM",
            nombre_cajera="Cajera de prueba",
            usuario=self.usuario,
        )
        transaccion = CierreTransaccion.objects.create(
            cierre=cierre,
            metodo_pago="PAGO_MOVIL",
            banco="Mercantil",
            monto=Decimal("75.00"),
            ref="REF9",
        )
        datos = {
            "transacciones-TOTAL_FORMS": "1",
            "transacciones-INITIAL_FORMS": "1",
            "transacciones-MIN_NUM_FORMS": "0",
            "transacciones-MAX_NUM_FORMS": "5000",
            "transacciones-0-id": str(transaccion.id),
            "transacciones-0-metodo_pago": "PAGO_MOVIL",
            "transacciones-0-banco": "Mercantil",
            "transacciones-0-monto": "75.00",
            "transacciones-0-ref": "REF9",
            "transacciones-0-notas": "",
            "transacciones-0-confirmado_banco": "",
            "transacciones-0-DELETE": "on",
        }

        respuesta = self.client.post(
            reverse("cuadre_caja:cierre_ajustar", args=[cierre.id]), datos
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(CierreTransaccion.objects.filter(pk=transaccion.pk).exists())

        novedad = NovedadCierre.objects.get(cierre=cierre)
        self.assertEqual(
            (novedad.metodo_pago, str(novedad.monto), novedad.ref, novedad.usuario),
            ("PAGO_MOVIL", "75.00", "REF9", self.usuario),
        )

        ajuste = self.client.get(
            reverse("cuadre_caja:cierre_ajustar", args=[cierre.id])
        )
        self.assertContains(ajuste, "Novedades")
        self.assertContains(ajuste, "REF9")

    def test_detalle_funciona_sin_usuario_registrado(self):
        cierre = CierreCaja.objects.create(
            caja=self.caja,
            fecha=timezone.localdate(),
            turno="PM",
            nombre_cajera="Cajera de prueba",
            usuario=None,
        )
        respuesta = self.client.get(
            reverse("cuadre_caja:cierre_detalle", args=[cierre.id])
        )
        self.assertEqual(respuesta.status_code, 200)


class MovimientosCajaTests(TestCase):
    """Los abonos históricos del cuadre siguen contando como ingresos adicionales."""

    def test_abono_suma_al_total_del_cierre(self):
        usuario = get_user_model().objects.create_superuser(
            username="abono_test", email="", password="clave123"
        )
        departamento = Departamento.objects.create(
            nombre="Prueba abono", slug="prueba-abono"
        )
        caja = Caja.objects.create(
            departamento=departamento, nombre="Caja abono", numero=98
        )
        cierre = CierreCaja.objects.create(
            caja=caja,
            fecha=timezone.localdate(),
            turno="AM",
            nombre_cajera="Cajera de prueba",
            tasa=Decimal("1.00"),
            total_bs=Decimal("100.00"),
            total_usd=Decimal("0.00"),
            usuario=usuario,
        )
        abono = EgresoCierre.objects.create(
            cierre=cierre,
            tipo="ABONO",
            moneda=MONEDA_BS,
            monto=Decimal("25.00"),
        )

        self.assertTrue(abono.es_ingreso_adicional)
        self.assertFalse(abono.es_vuelto)
        self.assertEqual(cierre.total_ingresos_adicionales_bs, Decimal("25.00"))
        self.assertEqual(cierre.total_equivalente_bs, Decimal("125.00"))

    def test_filas_vacias_no_crean_movimientos(self):
        usuario = get_user_model().objects.create_superuser(
            username="movimientos_vacios_test", email="", password="clave123"
        )
        departamento = Departamento.objects.create(
            nombre="Prueba vacíos", slug="prueba-vacios"
        )
        caja = Caja.objects.create(
            departamento=departamento, nombre="Caja vacíos", numero=97
        )
        cierre = CierreCaja.objects.create(
            caja=caja,
            fecha=timezone.localdate(),
            turno="PM",
            nombre_cajera="Cajera de prueba",
            usuario=usuario,
        )
        datos = {
            "egresos-TOTAL_FORMS": "2",
            "egresos-INITIAL_FORMS": "0",
            "egresos-MIN_NUM_FORMS": "0",
            "egresos-MAX_NUM_FORMS": "1000",
            "egresos-0-tipo": "EGRESO",
            "egresos-0-moneda": MONEDA_BS,
            "egresos-1-tipo": "EGRESO",
            "egresos-1-moneda": MONEDA_BS,
        }
        formset = EgresoCierreFormSet(datos, instance=cierre)
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        self.assertEqual(EgresoCierre.objects.filter(cierre=cierre).count(), 0)

    def test_movimientos_del_borrador_se_restauran_al_recargar(self):
        usuario = get_user_model().objects.create_superuser(
            username="movimientos_borrador_test", email="", password="clave123"
        )
        departamento = Departamento.objects.create(
            nombre="Prueba borrador movimientos", slug="prueba-borrador-movimientos"
        )
        caja = Caja.objects.create(
            departamento=departamento, nombre="Caja borrador", numero=96
        )
        self.client.force_login(usuario)
        payload = {
            "nombre_cajera": "Ana",
            "tasa": "1.00",
            "observaciones": "",
            "transacciones": [],
            "novedades": [],
            "movimientos": [
                {
                    "tipo": "EGRESO",
                    "moneda": MONEDA_BS,
                    "cedula": "V-123",
                    "telefono": "04140000000",
                    "banco": "Banesco",
                    "monto": "25.00",
                    "referencia": "12345",
                }
            ],
        }
        respuesta = self.client.post(
            reverse("cuadre_caja:borrador_guardar", args=[caja.id, "AM"]),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 200)

        borrador = BorradorCierre.objects.get(
            caja=caja, fecha=timezone.localdate(), turno="AM"
        )
        self.assertEqual(borrador.movimientos[0]["monto"], "25.00")
        self.assertEqual(borrador.movimientos[0]["referencia"], "12345")

        recarga = self.client.get(
            reverse("cuadre_caja:cerrar_caja_turno", args=[caja.id, "AM"])
        )
        self.assertEqual(recarga.status_code, 200)
        contenido = recarga.content.decode()
        self.assertIn('value="25.00"', contenido)
        self.assertIn('value="12345"', contenido)


class CreditoInsumosComoTransaccionTests(TestCase):
    """Crédito e insumos son transacciones en Bs; el vuelto es el único movimiento."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_superuser(
            username="transacciones_bs_test", email="", password="clave123"
        )
        self.departamento = Departamento.objects.create(
            nombre="Prueba transacciones Bs", slug="prueba-transacciones-bs"
        )
        self.caja = Caja.objects.create(
            departamento=self.departamento, nombre="Caja Bs", numero=95
        )
        self.client.force_login(self.usuario)

    def test_credito_e_insumos_aparecen_en_transacciones_y_no_en_movimientos(self):
        respuesta = self.client.get(
            reverse("cuadre_caja:cerrar_caja", args=[self.caja.id])
        )

        self.assertEqual(respuesta.status_code, 200)
        metodos = {
            tarjeta["valor"]: tarjeta for tarjeta in respuesta.context["tarjetas_metodo"]
        }
        for valor in ("CREDITO", "INSUMOS"):
            self.assertEqual(metodos[valor]["moneda"], MONEDA_BS)
            self.assertFalse(metodos[valor]["corregir"])
        metodos_bs = [
            tarjeta["valor"]
            for tarjeta in respuesta.context["tarjetas_metodo"]
            if tarjeta["moneda"] == MONEDA_BS
        ]
        self.assertEqual(
            metodos_bs[:4], ["EFECTIVO_BS", "CREDITO", "INSUMOS", "PUNTO_VENTA"]
        )
        tipos = [tipo[0] for tipo in respuesta.context["tipos_movimiento"]]
        self.assertEqual(tipos, ["EGRESO"])
        self.assertContains(respuesta, 'id="cuerpo-CREDITO"')
        self.assertContains(respuesta, 'id="cuerpo-INSUMOS"')
        self.assertNotContains(respuesta, 'id="suma-egreso-BS-CREDITO"')

    def test_transaccion_de_credito_suma_al_total_del_cierre(self):
        datos = {
            "turno": "AM",
            "nombre_cajera": "Cajera de prueba",
            "tasa": "1.00",
            "observaciones": "",
            "novedades_json": "[]",
        }
        datos.update(dict(_gestion(1)))
        datos.update(
            {
                "transacciones-0-metodo_pago": "CREDITO",
                "transacciones-0-banco": "Banesco",
                "transacciones-0-monto": "100.00",
                "transacciones-0-ref": "",
                "transacciones-0-notas": "",
                "egresos-TOTAL_FORMS": "0",
                "egresos-INITIAL_FORMS": "0",
                "egresos-MIN_NUM_FORMS": "0",
                "egresos-MAX_NUM_FORMS": "1000",
                "imagenes-TOTAL_FORMS": "0",
                "imagenes-INITIAL_FORMS": "0",
                "imagenes-MIN_NUM_FORMS": "0",
                "imagenes-MAX_NUM_FORMS": "1000",
            }
        )

        respuesta = self.client.post(
            reverse("cuadre_caja:cerrar_caja", args=[self.caja.id]), datos
        )

        self.assertEqual(respuesta.status_code, 302)
        cierre = CierreCaja.objects.get(caja=self.caja, turno="AM")
        self.assertEqual(cierre.total_bs, Decimal("100.00"))
        self.assertEqual(cierre.total_equivalente_bs, Decimal("100.00"))


class CuadreSiNoTests(TestCase):
    """El cuadre Sí/No solo lo edita soporte/admin y lo ve supervisora."""

    def setUp(self):
        self.departamento = Departamento.objects.create(
            nombre="Prueba cuadre", slug="prueba-cuadre"
        )
        self.caja = Caja.objects.create(
            departamento=self.departamento, nombre="Caja cuadre", numero=96
        )
        self.cierre = CierreCaja.objects.create(
            caja=self.caja,
            fecha=timezone.localdate(),
            turno="AM",
            nombre_cajera="Cajera prueba",
            tasa=Decimal("1.00"),
        )
        self.url_detalle = reverse("cuadre_caja:cierre_detalle", args=[self.cierre.id])
        self.url_actualizar = reverse(
            "cuadre_caja:cierre_cuadre_actualizar", args=[self.cierre.id]
        )

    def _login(self, rol, superuser=False):
        usuario = get_user_model().objects.create_user(
            username=f"cuadre_{rol}", password="clave123"
        )
        perfil = usuario.perfilusuario
        perfil.rol = rol
        perfil.save()
        if superuser:
            usuario.is_superuser = True
            usuario.save()
        self.client.force_login(usuario)

    def test_no_muestra_firmas_y_muestra_cuadre_para_supervisora(self):
        self._login("supervisor_cuadre_caja")
        respuesta = self.client.get(self.url_detalle)

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "Firma de la cajera")
        self.assertNotContains(respuesta, "Firma de supervisión")
        self.assertContains(respuesta, "Cuadre: Sin definir")

    def test_supervisora_no_puede_modificar_cuadre(self):
        self._login("supervisor_cuadre_caja")
        respuesta = self.client.post(self.url_actualizar, {"cuadre": "SI"})

        self.assertEqual(respuesta.status_code, 302)
        self.cierre.refresh_from_db()
        self.assertEqual(self.cierre.cuadre_si_no, "")

    def test_admin_puede_modificar_cuadre(self):
        self._login("admin", superuser=True)
        respuesta = self.client.post(self.url_actualizar, {"cuadre": "SI"})

        self.assertEqual(respuesta.status_code, 302)
        self.cierre.refresh_from_db()
        self.assertEqual(self.cierre.cuadre_si_no, "SI")
        respuesta = self.client.get(self.url_detalle)
        self.assertContains(respuesta, "CUADRE: SI")

    def test_soporte_puede_modificar_cuadre(self):
        self._login("soporte")
        respuesta = self.client.post(self.url_actualizar, {"cuadre": "NO"})

        self.assertEqual(respuesta.status_code, 302)
        self.cierre.refresh_from_db()
        self.assertEqual(self.cierre.cuadre_si_no, "NO")

    def test_historial_muestra_cuadre_de_caja_segun_si_no(self):
        self._login("supervisor_cuadre_caja")
        self.cierre.cuadre_si_no = "SI"
        self.cierre.save(update_fields=["cuadre_si_no"])

        respuesta = self.client.get(reverse("cuadre_caja:historial"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Cuadre de caja")
        self.assertContains(respuesta, '<span class="badge bg-success">SÍ</span>')

        self.cierre.cuadre_si_no = "NO"
        self.cierre.save(update_fields=["cuadre_si_no"])
        respuesta = self.client.get(reverse("cuadre_caja:historial"))
        self.assertContains(respuesta, '<span class="badge bg-danger">NO</span>')


class ConteoMetodosReporteTests(TestCase):
    """El conteo por método del reporte muestra los totales en dólares."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="reporte_conteo_test", password="clave123"
        )
        self.usuario.perfilusuario.rol = "supervisor_cuadre_caja"
        self.usuario.perfilusuario.save()
        departamento = Departamento.objects.create(
            nombre="Prueba reporte", slug="prueba-reporte"
        )
        caja = Caja.objects.create(
            departamento=departamento, nombre="Caja reporte", numero=94
        )
        self.client.force_login(self.usuario)
        cierre = CierreCaja.objects.create(
            caja=caja,
            fecha=timezone.localdate(),
            turno="AM",
            nombre_cajera="Cajera prueba",
            tasa=Decimal("40.00"),
        )
        CierreTransaccion.objects.create(
            cierre=cierre, metodo_pago="EFECTIVO_BS", monto=Decimal("200.00")
        )
        CierreTransaccion.objects.create(
            cierre=cierre, metodo_pago="EFECTIVO_USD", monto=Decimal("10.00")
        )

    def test_conteo_por_metodo_usa_dolares(self):
        respuesta = self.client.get(reverse("cuadre_caja:reportes"))

        self.assertEqual(respuesta.status_code, 200)
        metodos = {item["metodo"]: item for item in respuesta.context["conteo_metodos"]}
        self.assertEqual(metodos["Efectivo Bs"]["total_usd"], Decimal("5.00"))
        self.assertEqual(metodos["Efectivo USD"]["total_usd"], Decimal("10.00"))
        self.assertEqual(metodos["Efectivo Bs"]["total_bs"], Decimal("200.00"))
        self.assertEqual(metodos["Efectivo USD"]["total_bs"], Decimal("400.00"))
        self.assertContains(respuesta, "Bs 200,00")
        self.assertContains(respuesta, "$ 5,00")
        self.assertContains(respuesta, "$ 10,00")


class TotalesPorRolTests(TestCase):
    """Sin totales en el resumen de cajas; visibles en el formulario de cuadre."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="cuadre_totales_test", password="clave123"
        )
        self.usuario.perfilusuario.rol = "cuadre_caja"
        self.usuario.perfilusuario.save()
        departamento = Departamento.objects.create(
            nombre="Prueba totales", slug="prueba-totales"
        )
        self.caja = Caja.objects.create(
            departamento=departamento, nombre="Caja totales", numero=97
        )
        self.client.force_login(self.usuario)

    def test_rol_cuadre_caja_ve_los_totales_del_formulario(self):
        respuesta = self.client.get(
            reverse("cuadre_caja:cerrar_caja", args=[self.caja.id])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'id="total-bs"')
        self.assertContains(respuesta, 'id="total-usd"')
        self.assertContains(respuesta, 'id="total-equivalente"')
        self.assertContains(respuesta, "Resumen del cierre")

    def test_supervisor_tambien_ve_los_totales_del_formulario(self):
        self.usuario.perfilusuario.rol = "supervisor_cuadre_caja"
        self.usuario.perfilusuario.save()

        respuesta = self.client.get(
            reverse("cuadre_caja:cerrar_caja", args=[self.caja.id])
        )

        self.assertContains(respuesta, 'id="total-equivalente"')

    def test_cierre_se_guarda_con_el_formulario_visible(self):
        datos = {
            "turno": "AM",
            "nombre_cajera": "Cajera de prueba",
            "tasa": "1.00",
            "observaciones": "",
            "novedades_json": "[]",
        }
        datos.update(dict(_gestion(0)))
        datos.update(
            {
                "egresos-TOTAL_FORMS": "0",
                "egresos-INITIAL_FORMS": "0",
                "egresos-MIN_NUM_FORMS": "0",
                "egresos-MAX_NUM_FORMS": "1000",
                "imagenes-TOTAL_FORMS": "0",
                "imagenes-INITIAL_FORMS": "0",
                "imagenes-MIN_NUM_FORMS": "0",
                "imagenes-MAX_NUM_FORMS": "1000",
            }
        )

        respuesta = self.client.post(
            reverse("cuadre_caja:cerrar_caja", args=[self.caja.id]), datos
        )

        self.assertEqual(respuesta.status_code, 302)
        cierre = CierreCaja.objects.get(caja=self.caja, turno="AM")
        self.assertEqual(cierre.usuario, self.usuario)

    def _crear_cierre_con_montos(self):
        return CierreCaja.objects.create(
            caja=self.caja,
            fecha=timezone.localdate(),
            turno="AM",
            nombre_cajera="Cajera de prueba",
            usuario=self.usuario,
            tasa=Decimal("100.00"),
            total_bs=Decimal("123.45"),
            total_usd=Decimal("9.50"),
        )

    def test_resumen_de_cajas_oculta_los_totales_al_rol_cuadre_caja(self):
        self._crear_cierre_con_montos()

        respuesta = self.client.get(
            reverse(
                "cuadre_caja:departamento_detalle",
                args=[self.caja.departamento.slug],
            )
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["ocultar_totales"])
        self.assertNotContains(respuesta, '<th class="text-end">Total Bs</th>')
        self.assertNotContains(respuesta, 'data-campo="bs"')
        self.assertNotContains(respuesta, "123.45")
        self.assertContains(respuesta, "Cerrado")

    def test_estado_json_oculta_los_totales_al_rol_cuadre_caja(self):
        self._crear_cierre_con_montos()

        respuesta = self.client.get(
            reverse(
                "cuadre_caja:departamento_estado",
                args=[self.caja.departamento.slug],
            )
        )

        self.assertEqual(respuesta.status_code, 200)
        caja = respuesta.json()["cajas"][str(self.caja.id)]
        self.assertTrue(caja["turnos"]["AM"]["registrado"])
        self.assertEqual(caja["turnos"]["AM"]["total_bs"], "")
        self.assertEqual(caja["turnos"]["AM"]["total_usd"], "")
        self.assertEqual(caja["total_bs"], "")
        self.assertEqual(caja["total_usd"], "")

    def test_resumen_de_cajas_muestra_totales_al_supervisor(self):
        self._crear_cierre_con_montos()
        self.usuario.perfilusuario.rol = "supervisor_cuadre_caja"
        self.usuario.perfilusuario.save()

        respuesta = self.client.get(
            reverse(
                "cuadre_caja:departamento_detalle",
                args=[self.caja.departamento.slug],
            )
        )

        self.assertFalse(respuesta.context["ocultar_totales"])
        self.assertContains(respuesta, '<th class="text-end">Total Bs</th>')
        self.assertContains(respuesta, 'data-campo="bs"')
        self.assertEqual(respuesta.context["cajas"][0]["total_bs"], Decimal("123.45"))
