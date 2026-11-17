from django.db import DataError, IntegrityError, OperationalError
from django.http import QueryDict
from django.test import SimpleTestCase

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
from .models import CierreCaja
from .views import (
    MAX_DECIMAL_14,
    _decimal,
    _describir_error_sistema,
    _formatear_errores_cierre,
    _mensaje_error_sistema,
    _normalizar_transacciones_post,
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
