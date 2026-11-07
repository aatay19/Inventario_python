from collections import Counter
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .forms import (
    BANCOS_CHOICES,
    CajaForm,
    CierreCajaForm,
    CierreHistorialFiltroForm,
    DepartamentoForm,
    EgresoGeneralForm,
    EgresoCierreFormSet,
    CierreTransaccionForm,
    CierreTransaccionFormSet,
    ImagenCierreFormSet,
    ReporteFiltroForm,
)
from .models import (
    BorradorCierre,
    BorradorTransaccion,
    Caja,
    CierreCaja,
    Departamento,
    DetalleCierre,
    EgresoGeneral,
    MONEDA_BS,
    MONEDA_POR_METODO,
    MONEDA_USD,
    MetodoPagoChoices,
    EgresoCierre,
    CierreTransaccion,
    TurnoChoices,
)
from .permissions import (
    cuadre_caja_required,
    supervisor_required,
)

# Tiempo durante el cual se considera activo un borrador de cuadre.
BORRADOR_VIGENCIA = timedelta(minutes=10)


def _filas_formulario(form):
    """Agrupa los campos de monto por moneda (Bs / USD)."""
    filas_bs = []
    filas_usd = []

    for valor, etiqueta in MetodoPagoChoices.choices:
        fila = {
            "valor": valor,
            "etiqueta": etiqueta,
            "campo": form[f"monto_{valor}"],
        }
        if MONEDA_POR_METODO[valor] == MONEDA_USD:
            filas_usd.append(fila)
        else:
            filas_bs.append(fila)

    return filas_bs, filas_usd


def _rango_periodo(periodo, fecha):
    """Devuelve el rango de fechas (inicio, fin) para el periodo indicado."""
    from calendar import monthrange
    from datetime import timedelta

    if periodo == ReporteFiltroForm.PERIODO_SEMANA:
        inicio = fecha - timedelta(days=fecha.weekday())
        fin = inicio + timedelta(days=6)
    elif periodo == ReporteFiltroForm.PERIODO_MES:
        inicio = fecha.replace(day=1)
        fin = fecha.replace(day=monthrange(fecha.year, fecha.month)[1])
    elif periodo == ReporteFiltroForm.PERIODO_ANIO:
        inicio = fecha.replace(month=1, day=1)
        fin = fecha.replace(month=12, day=31)
    else:
        inicio = fecha
        fin = fecha
    return inicio, fin


def _montos_por_metodo(transacciones, detalles, moneda):
    """Montos por cada método de pago de una moneda, en el orden del formulario."""
    metodos = [
        (valor, etiqueta)
        for valor, etiqueta in MetodoPagoChoices.choices
        if MONEDA_POR_METODO.get(valor) == moneda
    ]
    montos = {valor: Decimal("0.00") for valor, _ in metodos}
    bancos = {valor: {} for valor, _ in metodos}

    transacciones_moneda = [
        transaccion
        for transaccion in transacciones
        if MONEDA_POR_METODO.get(transaccion.metodo_pago) == moneda
    ]

    if transacciones_moneda:
        for transaccion in transacciones_moneda:
            if transaccion.metodo_pago not in montos:
                continue
            if not transaccion.monto or transaccion.monto <= 0:
                continue
            montos[transaccion.metodo_pago] += transaccion.monto
            nombre_banco = (transaccion.banco or "").strip()
            if nombre_banco:
                bancos[transaccion.metodo_pago][nombre_banco] = (
                    bancos[transaccion.metodo_pago].get(nombre_banco, Decimal("0.00"))
                    + transaccion.monto
                )
    else:
        for detalle in detalles:
            if detalle.metodo_pago not in montos:
                continue
            monto = detalle.monto_bs if moneda == MONEDA_BS else detalle.monto_usd
            if monto and monto > 0:
                montos[detalle.metodo_pago] += monto

    filas = []
    for valor, etiqueta in metodos:
        filas.append(
            {
                "metodo": etiqueta,
                "monto": montos[valor],
                "bancos": [
                    {"banco": nombre, "monto": monto}
                    for nombre, monto in sorted(
                        bancos[valor].items(), key=lambda item: item[1], reverse=True
                    )
                ],
            }
        )

    total = sum(montos.values(), Decimal("0.00"))
    return filas, total


def _resumen_cierres(cierres):
    """Agrupa los cierres por departamento, caja y turno, con subtotales."""
    cero = Decimal("0.00")
    departamentos = {}
    total_general = {
        "cantidad": 0,
        "total_bs": cero,
        "total_usd": cero,
        "total_equivalente_bs": cero,
    }
    resumen_turnos = {
        valor: {
            "turno": etiqueta,
            "cantidad": 0,
            "total_bs": cero,
            "total_usd": cero,
            "total_equivalente_bs": cero,
        }
        for valor, etiqueta in TurnoChoices.choices
    }

    for cierre in cierres:
        departamento = cierre.caja.departamento
        grupo_departamento = departamentos.setdefault(
            departamento.id,
            {
                "departamento": departamento,
                "cajas": {},
                "cantidad": 0,
                "total_bs": cero,
                "total_usd": cero,
                "total_equivalente_bs": cero,
            },
        )
        grupo_caja = grupo_departamento["cajas"].setdefault(
            cierre.caja_id,
            {
                "caja": cierre.caja,
                "turnos": {},
                "cantidad": 0,
                "total_bs": cero,
                "total_usd": cero,
                "total_equivalente_bs": cero,
            },
        )
        grupo_turno = grupo_caja["turnos"].setdefault(
            cierre.turno,
            {
                "turno": cierre.get_turno_display(),
                "cantidad": 0,
                "total_bs": cero,
                "total_usd": cero,
                "total_equivalente_bs": cero,
            },
        )

        valores = {
            "cantidad": 1,
            "total_bs": cierre.total_bs,
            "total_usd": cierre.total_usd,
            "total_equivalente_bs": cierre.total_equivalente_bs,
        }
        for grupo in (
            grupo_turno,
            grupo_caja,
            grupo_departamento,
            total_general,
            resumen_turnos[cierre.turno],
        ):
            for campo, valor in valores.items():
                grupo[campo] += valor

    lista_departamentos = []
    for grupo_departamento in departamentos.values():
        grupo_departamento["lista_cajas"] = sorted(
            grupo_departamento["cajas"].values(), key=lambda item: item["caja"].numero
        )
        for grupo_caja in grupo_departamento["lista_cajas"]:
            grupo_caja["lista_turnos"] = [
                grupo_caja["turnos"][turno]
                for turno, _ in TurnoChoices.choices
                if turno in grupo_caja["turnos"]
            ]
        lista_departamentos.append(grupo_departamento)

    return lista_departamentos, total_general, list(resumen_turnos.values())


@cuadre_caja_required
def index(request):
    """Panel principal: muestra los departamentos disponibles."""
    hoy = timezone.localdate()
    departamentos = Departamento.objects.filter(activo=True).prefetch_related(
        Prefetch("cajas", queryset=Caja.objects.filter(activo=True))
    )
    conteo_cierres = Counter(
        CierreCaja.objects.filter(fecha=hoy).values_list(
            "caja__departamento_id", flat=True
        )
    )

    datos = []
    total_cajas = 0
    total_cierres_hoy = 0

    for departamento in departamentos:
        cajas = list(departamento.cajas.all())
        cierres_hoy = conteo_cierres.get(departamento.id, 0)
        datos.append(
            {
                "departamento": departamento,
                "total_cajas": len(cajas),
                "cierres_hoy": cierres_hoy,
            }
        )
        total_cajas += len(cajas)
        total_cierres_hoy += cierres_hoy

    return render(
        request,
        "cuadre_caja/index.html",
        {
            "departamentos": datos,
            "total_cajas": total_cajas,
            "cierres_hoy": total_cierres_hoy,
            "hoy": hoy,
        },
    )


@supervisor_required
def departamento_crear(request):
    """Registra un nuevo departamento."""
    if request.method == "POST":
        form = DepartamentoForm(request.POST)
        if form.is_valid():
            departamento = form.save()
            messages.success(
                request, f"Departamento “{departamento.nombre}” registrado."
            )
            return redirect("cuadre_caja:index")
    else:
        form = DepartamentoForm()

    return render(
        request,
        "cuadre_caja/departamento_form.html",
        {"form": form},
    )


@supervisor_required
def caja_crear(request, slug):
    """Registra una nueva caja dentro de un departamento."""
    departamento = get_object_or_404(Departamento, slug=slug, activo=True)

    if request.method == "POST":
        form = CajaForm(request.POST, departamento=departamento)
        if form.is_valid():
            caja = form.save(commit=False)
            caja.departamento = departamento
            caja.save()
            messages.success(
                request,
                f"Caja “{caja.nombre}” registrada en {departamento.nombre}.",
            )
            return redirect(
                "cuadre_caja:departamento_detalle", slug=departamento.slug
            )
    else:
        form = CajaForm(departamento=departamento)

    return render(
        request,
        "cuadre_caja/caja_form.html",
        {
            "form": form,
            "departamento": departamento,
        },
    )


def _decimal(valor, cuantia="0.01"):
    """Convierte un valor de formulario/JSON a Decimal de forma segura."""
    try:
        return Decimal(str(valor if valor not in (None, "") else "0")).quantize(
            Decimal(cuantia)
        )
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


def _borrador_vigente(caja, fecha, turno):
    """Borrador activo para una caja, fecha y turno."""
    limite = timezone.now() - BORRADOR_VIGENCIA
    return (
        BorradorCierre.objects.select_related("usuario")
        .prefetch_related("transacciones")
        .filter(
            caja=caja,
            fecha=fecha,
            turno=turno,
            actualizado_en__gte=limite,
        )
        .first()
    )


def _limpiar_borradores_vencidos():
    """Elimina los borradores que superaron los 10 minutos de vigencia."""
    limite = timezone.now() - BORRADOR_VIGENCIA
    BorradorCierre.objects.filter(actualizado_en__lt=limite).delete()


def _resumen_borrador(borrador):
    """Datos del borrador listos para el template o el JSON del estado."""
    if not borrador:
        return None
    return {
        "turno": borrador.turno,
        "usuario": borrador.usuario.get_username() if borrador.usuario else "",
        "actualizado": timezone.localtime(borrador.actualizado_en).strftime("%H:%M"),
        "transacciones": borrador.cantidad_transacciones,
        "total_bs": f"{borrador.total_bs:.2f}",
        "total_usd": f"{borrador.total_usd:.2f}",
        "total_equivalente_bs": f"{borrador.total_equivalente_bs:.2f}",
    }


@cuadre_caja_required
@never_cache
def departamento_detalle(request, slug):
    """Muestra las cajas de un departamento y sus cierres del día."""
    _limpiar_borradores_vencidos()
    departamento = get_object_or_404(Departamento, slug=slug, activo=True)
    hoy = timezone.localdate()
    cajas = list(departamento.cajas.filter(activo=True).order_by("numero"))

    cierres_por_caja = {}
    for cierre in CierreCaja.objects.filter(caja__in=cajas, fecha=hoy):
        cierres_por_caja.setdefault(cierre.caja_id, {})[cierre.turno] = cierre

    ultimos_cierres = {}
    for cierre in CierreCaja.objects.filter(caja__in=cajas).order_by(
        "caja_id", "-fecha", "-fecha_registro"
    ):
        ultimos_cierres.setdefault(cierre.caja_id, cierre)

    limite_borradores = timezone.now() - BORRADOR_VIGENCIA
    borradores_hoy = {
        (borrador.caja_id, borrador.turno): borrador
        for borrador in BorradorCierre.objects.filter(
            caja__in=cajas,
            fecha=hoy,
            actualizado_en__gte=limite_borradores,
        )
        .select_related("usuario")
        .prefetch_related("transacciones")
        if borrador.turno not in cierres_por_caja.get(borrador.caja_id, {})
    }

    datos = []
    for caja in cajas:
        cierres_hoy = cierres_por_caja.get(caja.id, {})
        total_bs = sum(
            (cierre.total_bs for cierre in cierres_hoy.values()),
            Decimal("0.00"),
        )
        total_usd = sum(
            (cierre.total_usd for cierre in cierres_hoy.values()),
            Decimal("0.00"),
        )
        total_equivalente_bs = sum(
            (cierre.total_equivalente_bs for cierre in cierres_hoy.values()),
            Decimal("0.00"),
        )
        datos.append(
            {
                "caja": caja,
                "cierres_hoy": cierres_hoy,
                "ultimo_cierre": ultimos_cierres.get(caja.id),
                "total_bs": total_bs,
                "total_usd": total_usd,
                "total_equivalente_bs": total_equivalente_bs,
                "borradores": {
                    turno: _resumen_borrador(
                        borradores_hoy.get((caja.id, turno))
                    )
                    for turno in (TurnoChoices.AM, TurnoChoices.PM)
                },
            }
        )

    return render(
        request,
        "cuadre_caja/departamento_detalle.html",
        {
            "departamento": departamento,
            "cajas": datos,
            "hoy": hoy,
            "total_cajas": len(datos),
            "cierres_hoy": sum(len(item["cierres_hoy"]) for item in datos),
        },
    )


@cuadre_caja_required
@never_cache
def departamento_estado(request, slug):
    """Estado en vivo de las cajas de un departamento (JSON para auto-refresh)."""
    departamento = get_object_or_404(Departamento, slug=slug, activo=True)
    hoy = timezone.localdate()
    cajas = list(departamento.cajas.filter(activo=True).order_by("numero"))

    cierres_por_caja = {}
    for cierre in CierreCaja.objects.filter(caja__in=cajas, fecha=hoy):
        cierres_por_caja.setdefault(cierre.caja_id, {})[cierre.turno] = cierre

    limite_borradores = timezone.now() - BORRADOR_VIGENCIA
    borradores_hoy = {
        (borrador.caja_id, borrador.turno): borrador
        for borrador in BorradorCierre.objects.filter(
            caja__in=cajas,
            fecha=hoy,
            actualizado_en__gte=limite_borradores,
        )
        .select_related("usuario")
        .prefetch_related("transacciones")
        if borrador.turno not in cierres_por_caja.get(borrador.caja_id, {})
    }

    datos = {}
    total_cierres = 0
    for caja in cajas:
        cierres_hoy = cierres_por_caja.get(caja.id, {})
        turnos = {}
        for turno in (TurnoChoices.AM, TurnoChoices.PM):
            cierre = cierres_hoy.get(turno)
            if cierre:
                turnos[turno] = {
                    "registrado": True,
                    "cajera": cierre.nombre_cajera,
                    "total_bs": f"{cierre.total_bs:.2f}",
                    "total_usd": f"{cierre.total_usd:.2f}",
                    "total_equivalente_bs": f"{cierre.total_equivalente_bs:.2f}",
                }
            else:
                turnos[turno] = {"registrado": False}

        total_cierres += len(cierres_hoy)
        datos[str(caja.id)] = {
            "turnos": turnos,
            "total_bs": f"{sum((c.total_bs for c in cierres_hoy.values()), Decimal('0.00')):.2f}",
            "total_usd": f"{sum((c.total_usd for c in cierres_hoy.values()), Decimal('0.00')):.2f}",
            "total_equivalente_bs": f"{sum((c.total_equivalente_bs for c in cierres_hoy.values()), Decimal('0.00')):.2f}",
            "borradores": {
                turno: _resumen_borrador(borradores_hoy.get((caja.id, turno)))
                for turno in (TurnoChoices.AM, TurnoChoices.PM)
            },
        }

    return JsonResponse({"cajas": datos, "cierres_hoy": total_cierres})


@cuadre_caja_required
def borrador_guardar(request, caja_id, turno):
    """Guarda (sin registrar el cierre) el avance de un cuadre en curso."""
    if request.method != "POST":
        return JsonResponse(
            {"ok": False, "error": "Método no permitido."}, status=405
        )

    _limpiar_borradores_vencidos()

    caja = get_object_or_404(
        Caja.objects.select_related("departamento"), pk=caja_id, activo=True
    )
    turnos_validos = {valor for valor, _ in TurnoChoices.choices}
    if turno not in turnos_validos:
        return JsonResponse(
            {"ok": False, "error": "El turno indicado no es válido."}, status=400
        )

    hoy = timezone.localdate()
    if CierreCaja.objects.filter(caja=caja, fecha=hoy, turno=turno).exists():
        return JsonResponse(
            {"ok": False, "error": "El turno ya fue registrado."}, status=409
        )

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"ok": False, "error": "Datos inválidos."}, status=400
        )
    if not isinstance(payload, dict):
        return JsonResponse(
            {"ok": False, "error": "Datos inválidos."}, status=400
        )

    transacciones = payload.get("transacciones") or []
    if not isinstance(transacciones, list):
        transacciones = []

    metodos_validos = {valor for valor, _ in MetodoPagoChoices.choices}

    with transaction.atomic():
        borrador, _ = BorradorCierre.objects.select_for_update().get_or_create(
            caja=caja,
            fecha=hoy,
            turno=turno,
            defaults={"usuario": request.user},
        )
        borrador.usuario = request.user
        borrador.nombre_cajera = str(payload.get("nombre_cajera") or "")[:100]
        borrador.tasa = _decimal(payload.get("tasa"), "0.01")
        borrador.observaciones = str(payload.get("observaciones") or "")
        borrador.save()

        borrador.transacciones.all().delete()
        nuevas = []
        for orden, item in enumerate(transacciones):
            if not isinstance(item, dict):
                continue
            metodo = item.get("metodo_pago") or ""
            monto = _decimal(item.get("monto"))
            if metodo not in metodos_validos or monto <= 0:
                continue
            nuevas.append(
                BorradorTransaccion(
                    borrador=borrador,
                    metodo_pago=metodo,
                    banco=str(item.get("banco") or "")[:100],
                    monto=monto,
                    ref=str(item.get("ref") or "")[:100],
                    notas=str(item.get("notas") or "")[:255],
                    orden=orden,
                )
            )
        BorradorTransaccion.objects.bulk_create(nuevas)

    borrador = (
        BorradorCierre.objects.select_related("usuario")
        .prefetch_related("transacciones")
        .get(pk=borrador.pk)
    )
    return JsonResponse({"ok": True, "borrador": _resumen_borrador(borrador)})


@cuadre_caja_required
def egresos(request):
    """Registra egresos o devoluciones independientes de los cuadres de caja."""
    if request.method == "POST":
        form = EgresoGeneralForm(request.POST, request.FILES)
        if form.is_valid():
            egreso = form.save(commit=False)
            egreso.usuario = request.user
            egreso.save()
            messages.success(
                request,
                f"{egreso.get_tipo_display()} registrado correctamente.",
            )
            return redirect("cuadre_caja:egresos")
        messages.error(request, "Revisa los datos del egreso o devolución.")
    else:
        form = EgresoGeneralForm()

    registros = EgresoGeneral.objects.select_related("usuario")
    totales = registros.aggregate(
        cantidad=Count("id"),
        total_bs=Sum("monto", filter=Q(moneda=MONEDA_BS)),
        total_usd=Sum("monto", filter=Q(moneda=MONEDA_USD)),
    )
    totales["total_bs"] = totales["total_bs"] or Decimal("0.00")
    totales["total_usd"] = totales["total_usd"] or Decimal("0.00")

    paginator = Paginator(registros, 20)
    pagina = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "cuadre_caja/egresos.html",
        {
            "form": form,
            "egresos": pagina,
            "totales": totales,
            "total_registros": paginator.count,
        },
    )


@cuadre_caja_required
@never_cache
def cerrar_caja(request, caja_id, turno=None):
    """Registra el cierre diario de una caja (turno fijo AM/PM si se indica)."""
    caja = get_object_or_404(
        Caja.objects.select_related("departamento"), pk=caja_id, activo=True
    )

    turnos_validos = {valor for valor, _ in TurnoChoices.choices}
    if turno is not None and turno not in turnos_validos:
        messages.error(request, "El turno indicado no es válido.")
        return redirect("cuadre_caja:departamento_detalle", caja.departamento.slug)

    hoy = timezone.localdate()
    turnos_registrados = set(
        CierreCaja.objects.filter(caja=caja, fecha=hoy).values_list("turno", flat=True)
    )

    # Si el turno específico ya está registrado hoy, no se permite repetirlo.
    if turno and turno in turnos_registrados:
        messages.error(
            request,
            f"La caja “{caja.nombre}” ya tiene registrado el turno {turno} para hoy "
            f"({hoy:%d/%m/%Y}).",
        )
        return redirect("cuadre_caja:departamento_detalle", caja.departamento.slug)

    # Si ya existen ambos turnos (AM y PM) para esta caja hoy, no se permite registrar otro cuadre.
    if TurnoChoices.AM in turnos_registrados and TurnoChoices.PM in turnos_registrados:
        messages.error(
            request,
            f"La caja “{caja.nombre}” ya tiene los turnos AM y PM registrados para hoy "
            f"({hoy:%d/%m/%Y}). No se puede registrar otro cuadre.",
        )
        return redirect("cuadre_caja:departamento_detalle", caja.departamento.slug)

    if request.method == "POST":
        form = CierreCajaForm(request.POST, caja=caja, turno=turno)
        egresos_formset = EgresoCierreFormSet(
            request.POST, request.FILES, prefix="egresos", instance=CierreCaja()
        )
        transacciones_formset = CierreTransaccionFormSet(
            request.POST, prefix="transacciones", instance=CierreCaja()
        )
        imagenes_formset = ImagenCierreFormSet(
            request.POST, request.FILES, prefix="imagenes", instance=CierreCaja()
        )
        if (
            form.is_valid()
            and egresos_formset.is_valid()
            and transacciones_formset.is_valid()
            and imagenes_formset.is_valid()
        ):
            cierre = form.save(commit=False)
            cierre.caja = caja
            cierre.fecha = form.fecha
            cierre.usuario = request.user
            cierre.save()

            egresos_formset.instance = cierre
            egresos_formset.save()

            imagenes_formset.instance = cierre
            imagenes_formset.save()

            transacciones_guardadas = transacciones_formset.save(commit=False)
            total_bs = Decimal("0.00")
            total_usd = Decimal("0.00")
            for t in transacciones_guardadas:
                t.cierre = cierre
                t.save()
                if MONEDA_POR_METODO.get(t.metodo_pago) == MONEDA_USD:
                    total_usd += t.monto or Decimal("0.00")
                else:
                    total_bs += t.monto or Decimal("0.00")

            cierre.total_bs = total_bs
            cierre.total_usd = total_usd
            cierre.save()

            # El cuadre ya quedó registrado: se descarta el borrador compartido.
            BorradorCierre.objects.filter(
                caja=caja, fecha=hoy, turno=cierre.turno
            ).delete()

            messages.success(
                request,
                f"Cierre registrado para {caja.nombre} "
                f"({cierre.get_turno_display()}).",
            )
            return redirect(
                "cuadre_caja:departamento_detalle", caja.departamento.slug
            )

        messages.error(request, "Revisa los datos del cierre.")
    else:
        borrador = _borrador_vigente(caja, hoy, turno) if turno else None
        datos_iniciales = {}
        # Filas del borrador agrupadas por método (múltiples por método)
        metodo_filas = {}
        if borrador:
            datos_iniciales = {
                "nombre_cajera": borrador.nombre_cajera,
                "tasa": borrador.tasa or None,
                "observaciones": borrador.observaciones,
            }
            for t in borrador.transacciones.all():
                metodo_filas.setdefault(t.metodo_pago, []).append({
                    "banco": t.banco,
                    "monto": t.monto,
                    "ref": t.ref,
                    "notas": t.notas,
                })
            if borrador.usuario_id and borrador.usuario_id != request.user.id:
                messages.warning(
                    request,
                    f"Hay un borrador en curso de "
                    f"{borrador.usuario.get_username()} para esta caja y turno. "
                    f"Se continuará ese borrador compartido.",
                )
            else:
                messages.info(
                    request,
                    "Se restauró el borrador en curso. Se conserva 10 minutos "
                    "sin actividad.",
                )

        form = CierreCajaForm(caja=caja, turno=turno, initial=datos_iniciales)
        egresos_formset = EgresoCierreFormSet(
            prefix="egresos", instance=CierreCaja()
        )
        imagenes_formset = ImagenCierreFormSet(
            prefix="imagenes", instance=CierreCaja()
        )

        # Construir tarjetas con múltiples filas por método.
        # Se usa índice global para los prefijos (transacciones-0, -1, -2...)
        # de forma que el formset del POST los recoja todos sin conflictos.
        global_index = 0
        tarjetas_metodo = []
        for valor, etiqueta in MetodoPagoChoices.choices:
            # Al menos 1 fila vacía por método (aunque no haya borrador)
            filas_datos = metodo_filas.get(valor, [{}])
            forms_fila = []
            for datos in filas_datos:
                forms_fila.append(
                    CierreTransaccionForm(
                        initial={
                            "metodo_pago": valor,
                            "banco": datos.get("banco", ""),
                            "monto": datos.get("monto", ""),
                            "ref": datos.get("ref", ""),
                            "notas": datos.get("notas", ""),
                        },
                        prefix=f"transacciones-{global_index}",
                    )
                )
                global_index += 1
            tarjetas_metodo.append({
                "valor": valor,
                "etiqueta": etiqueta,
                "moneda": MONEDA_POR_METODO.get(valor, MONEDA_BS),
                "forms": forms_fila,
            })

        transacciones_total_forms = global_index
        transacciones_initial_forms = 0

        # Formset vacío sólo para el management_form
        transacciones_formset = CierreTransaccionFormSet(
            prefix="transacciones",
            instance=CierreCaja(),
        )

    filas_bs, filas_usd = _filas_formulario(form)

    if request.method == "POST":
        # Reconstruir tarjetas agrupando los forms bound por método de pago.
        metodo_forms = {valor: [] for valor, _ in MetodoPagoChoices.choices}
        for f in transacciones_formset.forms:
            metodo = request.POST.get(f"{f.prefix}-metodo_pago", "")
            if metodo in metodo_forms:
                metodo_forms[metodo].append(f)

        tarjetas_metodo = [
            {
                "valor": valor,
                "etiqueta": etiqueta,
                "moneda": MONEDA_POR_METODO.get(valor, MONEDA_BS),
                "forms": metodo_forms.get(valor, []),
            }
            for valor, etiqueta in MetodoPagoChoices.choices
        ]
        transacciones_total_forms = transacciones_formset.total_form_count()
        transacciones_initial_forms = transacciones_formset.initial_form_count()

    return render(
        request,
        "cuadre_caja/cerrar_caja.html",
        {
            "caja": caja,
            "form": form,
            "fecha": form.fecha,
            "turno_fijo": turno,
            "filas_bs": filas_bs,
            "filas_usd": filas_usd,
            "egresos_formset": egresos_formset,
            "transacciones_formset": transacciones_formset,
            "tarjetas_metodo": tarjetas_metodo,
            "transacciones_total_forms": transacciones_total_forms,
            "transacciones_initial_forms": transacciones_initial_forms,
            "imagenes_formset": imagenes_formset,
            "MONEDA_BS": MONEDA_BS,
            "MONEDA_USD": MONEDA_USD,
            "bancos_choices": BANCOS_CHOICES,
        },
    )


@cuadre_caja_required
def cierre_detalle(request, cierre_id):
    """Comprobante de un cierre registrado."""
    cierre = get_object_or_404(
        CierreCaja.objects.select_related(
            "caja__departamento", "usuario"
        ).prefetch_related("detalles", "transacciones", "egresos", "imagenes"),
        pk=cierre_id,
    )

    orden_metodos = {
        valor: indice for indice, (valor, _) in enumerate(MetodoPagoChoices.choices)
    }
    detalles = sorted(
        cierre.detalles.all(),
        key=lambda detalle: orden_metodos.get(detalle.metodo_pago, 99),
    )

    egresos = list(cierre.egresos.all())
    total_egresos_bs = sum(
        (egreso.monto for egreso in egresos if egreso.moneda == MONEDA_BS),
        Decimal("0.00"),
    )
    total_egresos_usd = sum(
        (egreso.monto for egreso in egresos if egreso.moneda == MONEDA_USD),
        Decimal("0.00"),
    )

    transacciones = list(cierre.transacciones.all())
    imagenes = list(cierre.imagenes.all())

    distribucion_bs, total_distribucion_bs = _montos_por_metodo(
        transacciones, detalles, MONEDA_BS
    )
    distribucion_usd, total_distribucion_usd = _montos_por_metodo(
        transacciones, detalles, MONEDA_USD
    )

    # Compatibilidad con cierres antiguos que solo tienen el total registrado.
    if total_distribucion_bs == 0 and cierre.total_bs:
        distribucion_bs.append(
            {
                "metodo": "Total registrado",
                "monto": cierre.total_bs,
                "bancos": [],
            }
        )
        total_distribucion_bs = cierre.total_bs
    if total_distribucion_usd == 0 and cierre.total_usd:
        distribucion_usd.append(
            {
                "metodo": "Total registrado",
                "monto": cierre.total_usd,
                "bancos": [],
            }
        )
        total_distribucion_usd = cierre.total_usd

    return render(
        request,
        "cuadre_caja/cierre_detalle.html",
        {
            "cierre": cierre,
            "caja": cierre.caja,
            "distribucion_bs": distribucion_bs,
            "distribucion_usd": distribucion_usd,
            "total_distribucion_bs": total_distribucion_bs,
            "total_distribucion_usd": total_distribucion_usd,
            "egresos": egresos,
            "total_egresos_bs": total_egresos_bs,
            "total_egresos_usd": total_egresos_usd,
            "transacciones": transacciones,
            "imagenes": imagenes,
        },
    )


@supervisor_required
def historial(request):
    """Listado de cierres con filtros por departamento, turno, cajera y fecha."""
    form = CierreHistorialFiltroForm(request.GET or None)
    cierres = CierreCaja.objects.select_related(
        "caja__departamento", "usuario"
    ).order_by("-fecha", "-fecha_registro")

    if form.is_valid():
        departamento = form.cleaned_data.get("departamento")
        turno = form.cleaned_data.get("turno")
        cajera = form.cleaned_data.get("cajera")
        desde = form.cleaned_data.get("desde")
        hasta = form.cleaned_data.get("hasta")

        if departamento:
            cierres = cierres.filter(caja__departamento=departamento)
        if turno:
            cierres = cierres.filter(turno=turno)
        if cajera:
            cierres = cierres.filter(nombre_cajera__icontains=cajera)
        if desde:
            cierres = cierres.filter(fecha__gte=desde)
        if hasta:
            cierres = cierres.filter(fecha__lte=hasta)

    totales = cierres.aggregate(
        total_bs=Sum("total_bs"),
        total_usd=Sum("total_usd"),
    )

    paginator = Paginator(cierres, 25)
    pagina = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "cuadre_caja/historial.html",
        {
            "form": form,
            "cierres": pagina,
            "totales": totales,
            "total_registros": paginator.count,
        },
    )


@supervisor_required
def reportes(request):
    """Reportes por turno, caja y departamento para día, semana, mes o año."""
    hoy = timezone.localdate()

    # Al abrir el reporte sin filtros, mostrar el último día con cierres
    # registrados para que el reporte no aparezca vacío.
    fecha_inicial = hoy
    if not request.GET:
        ultima_fecha = (
            CierreCaja.objects.order_by("-fecha")
            .values_list("fecha", flat=True)
            .first()
        )
        if ultima_fecha:
            fecha_inicial = ultima_fecha

    form = ReporteFiltroForm(
        request.GET or None,
        initial={"fecha": fecha_inicial, "periodo": ReporteFiltroForm.PERIODO_DIA},
    )

    periodo = ReporteFiltroForm.PERIODO_DIA
    fecha_referencia = fecha_inicial
    departamento = None
    caja = None
    turno = None

    if form.is_valid():
        periodo = form.cleaned_data.get("periodo") or ReporteFiltroForm.PERIODO_DIA
        fecha_referencia = form.cleaned_data.get("fecha") or hoy
        departamento = form.cleaned_data.get("departamento")
        caja = form.cleaned_data.get("caja")
        turno = form.cleaned_data.get("turno")

    fecha_inicio, fecha_fin = _rango_periodo(periodo, fecha_referencia)

    cierres = CierreCaja.objects.select_related(
        "caja__departamento"
    ).filter(fecha__gte=fecha_inicio, fecha__lte=fecha_fin)

    if departamento:
        cierres = cierres.filter(caja__departamento=departamento)
    if caja:
        cierres = cierres.filter(caja=caja)
    if turno:
        cierres = cierres.filter(turno=turno)

    cierres = list(
        cierres.order_by(
            "caja__departamento__orden",
            "caja__departamento__nombre",
            "caja__numero",
            "fecha",
            "turno",
        )
    )

    grupos, total_general, resumen_turnos = _resumen_cierres(cierres)

    # Egresos y devoluciones registrados dentro de los cuadres filtrados.
    salidas = EgresoCierre.objects.filter(cierre__in=cierres)
    totales_salidas = salidas.aggregate(
        cantidad=Count("id"),
        total_bs=Sum("monto", filter=Q(moneda=MONEDA_BS)),
        total_usd=Sum("monto", filter=Q(moneda=MONEDA_USD)),
    )
    totales_salidas["total_bs"] = totales_salidas["total_bs"] or Decimal("0.00")
    totales_salidas["total_usd"] = totales_salidas["total_usd"] or Decimal("0.00")

    # Egresos y devoluciones independientes (no pertenecen a ningún cuadre).
    inicio_dt = timezone.make_aware(datetime.combine(fecha_inicio, time.min))
    fin_dt = timezone.make_aware(
        datetime.combine(fecha_fin + timedelta(days=1), time.min)
    )
    independientes = EgresoGeneral.objects.filter(
        fecha_registro__gte=inicio_dt,
        fecha_registro__lt=fin_dt,
    ).select_related("usuario")
    totales_independientes = independientes.aggregate(
        cantidad=Count("id"),
        total_bs=Sum("monto", filter=Q(moneda=MONEDA_BS)),
        total_usd=Sum("monto", filter=Q(moneda=MONEDA_USD)),
    )
    totales_independientes["total_bs"] = (
        totales_independientes["total_bs"] or Decimal("0.00")
    )
    totales_independientes["total_usd"] = (
        totales_independientes["total_usd"] or Decimal("0.00")
    )
    egresos_independientes = independientes.order_by("-fecha_registro")[:10]

    # Conteo por método de pago y por banco de los cierres filtrados.
    cierres_ids = [cierre.id for cierre in cierres]
    transacciones = list(
        CierreTransaccion.objects.filter(cierre_id__in=cierres_ids)
    )
    detalles = list(
        DetalleCierre.objects.filter(cierre_id__in=cierres_ids)
    )

    conteo = Counter()
    transacciones_por_cierre = {}
    for transaccion in transacciones:
        transacciones_por_cierre.setdefault(
            transaccion.cierre_id, []
        ).append(transaccion)
    detalles_por_cierre = {}
    for detalle in detalles:
        detalles_por_cierre.setdefault(detalle.cierre_id, []).append(detalle)

    for cierre in cierres:
        registros = transacciones_por_cierre.get(cierre.id)
        if not registros:
            registros = detalles_por_cierre.get(cierre.id, [])
        conteo.update(registro.metodo_pago for registro in registros)

    conteo_metodos = [
        {"metodo": etiqueta, "cantidad": conteo[valor]}
        for valor, etiqueta in MetodoPagoChoices.choices
        if conteo.get(valor)
    ]

    etiquetas_banco = {
        valor.lower(): etiqueta for valor, etiqueta in BANCOS_CHOICES if valor
    }
    monto_por_banco = Counter()
    for transaccion in transacciones:
        banco = (transaccion.banco or "").strip()
        if not banco:
            continue
        nombre = etiquetas_banco.get(banco.lower(), banco)
        monto_por_banco[nombre] += transaccion.monto or Decimal("0.00")

    orden_bancos = [etiqueta for valor, etiqueta in BANCOS_CHOICES if valor]
    conteo_bancos = [
        {"banco": nombre, "monto": monto_por_banco[nombre]}
        for nombre in orden_bancos
        if monto_por_banco.get(nombre)
    ]
    for nombre in sorted(monto_por_banco):
        if nombre not in orden_bancos:
            conteo_bancos.append(
                {"banco": nombre, "monto": monto_por_banco[nombre]}
            )

    etiquetas_periodo = {
        ReporteFiltroForm.PERIODO_DIA: "Día",
        ReporteFiltroForm.PERIODO_SEMANA: "Semana",
        ReporteFiltroForm.PERIODO_MES: "Mensual",
        ReporteFiltroForm.PERIODO_ANIO: "Anual",
    }

    return render(
        request,
        "cuadre_caja/reportes.html",
        {
            "form": form,
            "periodo": periodo,
            "periodo_etiqueta": etiquetas_periodo.get(periodo, "Día"),
            "fecha_referencia": fecha_referencia,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "departamento": departamento,
            "caja": caja,
            "turno": turno,
            "grupos": grupos,
            "total_general": total_general,
            "resumen_turnos": resumen_turnos,
            "totales_salidas": totales_salidas,
            "totales_independientes": totales_independientes,
            "egresos_independientes": egresos_independientes,
            "total_cierres": len(cierres),
            "conteo_metodos": conteo_metodos,
            "conteo_bancos": conteo_bancos,
        },
    )


@supervisor_required
def reporte_dia(request, fecha_str):
    """Reporte de cierres por día."""
    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        from django.shortcuts import redirect
        return redirect("cuadre_caja:historial")

    cierres = CierreCaja.objects.select_related(
        "caja__departamento", "usuario"
    ).filter(fecha=fecha).order_by("turno", "caja__numero")

    totales_turno = cierres.values("turno").annotate(
        total_bs=Sum("total_bs"),
        total_usd=Sum("total_usd"),
        cantidad=Count("id"),
    ).order_by("turno")

    # Totales generales
    totales_generales = cierres.aggregate(
        total_bs=Sum("total_bs"),
        total_usd=Sum("total_usd"),
    )

    # Conteo por turno
    conteo_turno = cierres.values("turno").annotate(
        count=Count("id")
    ).order_by("turno")

    return render(
        request,
        "cuadre_caja/reporte_dia.html",
        {
            "fecha": fecha,
            "cierres": cierres,
            "totales_turno": totales_turno,
            "totales_generales": totales_generales,
            "conteo_turno": conteo_turno,
        },
    )


@supervisor_required
def reporte_semanal(request):
    """Reporte semanal de cierres."""
    from datetime import timedelta
    hoy = timezone.localdate()
    # Lunes de la semana actual
    lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)

    cierres = CierreCaja.objects.select_related(
        "caja__departamento", "usuario"
    ).filter(fecha__gte=lunes, fecha__lte=domingo).order_by("fecha", "turno")

    totales_turno = cierres.values("turno", "fecha").annotate(
        total_bs=Sum("total_bs"),
        total_usd=Sum("total_usd"),
        cantidad=Count("id"),
    ).order_by("fecha", "turno")

    totales_generales = cierres.aggregate(
        total_bs=Sum("total_bs"),
        total_usd=Sum("total_usd"),
    )

    conteo_turno = cierres.values("turno").annotate(
        count=Count("id")
    ).order_by("turno")

    return render(
        request,
        "cuadre_caja/reporte_semanal.html",
        {
            "lunes": lunes,
            "domingo": domingo,
            "cierres": cierres,
            "totales_turno": totales_turno,
            "totales_generales": totales_generales,
            "conteo_turno": conteo_turno,
        },
    )


@supervisor_required
def reporte_mensual(request):
    """Reporte mensual de cierres."""
    from calendar import monthrange
    hoy = timezone.localdate()
    primer_dia = hoy.replace(day=1)
    ultimo_dia_num = monthrange(hoy.year, hoy.month)[1]
    ultimo_dia = hoy.replace(day=ultimo_dia_num)

    cierres = CierreCaja.objects.select_related(
        "caja__departamento", "usuario"
    ).filter(fecha__gte=primer_dia, fecha__lte=ultimo_dia).order_by("fecha", "turno")

    totales_turno = cierres.values("turno", "fecha").annotate(
        total_bs=Sum("total_bs"),
        total_usd=Sum("total_usd"),
        cantidad=Count("id"),
    ).order_by("fecha", "turno")

    totales_generales = cierres.aggregate(
        total_bs=Sum("total_bs"),
        total_usd=Sum("total_usd"),
    )

    conteo_turno = cierres.values("turno").annotate(
        count=Count("id")
    ).order_by("turno")

    return render(
        request,
        "cuadre_caja/reporte_mensual.html",
        {
            "fecha_inicio": primer_dia,
            "fecha_fin": ultimo_dia,
            "cierres": cierres,
            "totales_turno": totales_turno,
            "totales_generales": totales_generales,
            "conteo_turno": conteo_turno,
        },
    )


@supervisor_required
def reporte_anual(request):
    """Annual report of closures."""
    hoy = timezone.localdate()
    primer_dia = hoy.replace(month=1, day=1)
    ultimo_dia = hoy.replace(month=12, day=31)

    cierres = CierreCaja.objects.select_related(
        "caja__departamento", "usuario"
    ).filter(fecha__gte=primer_dia, fecha__lte=ultimo_dia).order_by("fecha", "turno")

    totales_turno = cierres.values("turno", "fecha").annotate(
        total_bs=Sum("total_bs"),
        total_usd=Sum("total_usd"),
        cantidad=Count("id"),
    ).order_by("fecha", "turno")

    totales_generales = cierres.aggregate(
        total_bs=Sum("total_bs"),
        total_usd=Sum("total_usd"),
    )

    conteo_turno = cierres.values("turno").annotate(
        count=Count("id")
    ).order_by("turno")

    return render(
        request,
        "cuadre_caja/reporte_anual.html",
        {
            "fecha_inicio": primer_dia,
            "fecha_fin": ultimo_dia,
            "cierres": cierres,
            "totales_turno": totales_turno,
            "totales_generales": totales_generales,
            "conteo_turno": conteo_turno,
        },
    )