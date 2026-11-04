from collections import Counter
from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    BANCOS_CHOICES,
    CajaForm,
    CierreCajaForm,
    CierreHistorialFiltroForm,
    DepartamentoForm,
    EgresoCierreFormSet,
    CierreTransaccionFormSet,
    ImagenCierreFormSet,
    ReporteFiltroForm,
)
from .models import (
    Caja,
    CierreCaja,
    Departamento,
    DetalleCierre,
    MONEDA_BS,
    MONEDA_POR_METODO,
    MONEDA_USD,
    MetodoPagoChoices,
    EgresoCierre,
    CierreTransaccion,
    TurnoChoices,
)


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


@login_required
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


@login_required
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


@login_required
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


@login_required
def departamento_detalle(request, slug):
    """Muestra las cajas de un departamento y sus cierres del día."""
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


@login_required
def cerrar_caja(request, caja_id):
    """Registra el cierre diario de una caja."""
    caja = get_object_or_404(
        Caja.objects.select_related("departamento"), pk=caja_id, activo=True
    )

    if request.method == "POST":
        form = CierreCajaForm(request.POST, caja=caja)
        egresos_formset = EgresoCierreFormSet(
            request.POST, prefix="egresos", instance=CierreCaja()
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
            # First save the closure
            cierre = form.save(commit=False)
            cierre.caja = caja
            cierre.fecha = form.fecha
            cierre.usuario = request.user
            cierre.save()

            # Save egresos
            egresos_formset.instance = cierre
            egresos_formset.save()

            # Save imagenes
            imagenes_formset.instance = cierre
            imagenes_formset.save()

            # Save transacciones and calculate totals
            transacciones = transacciones_formset.save(commit=False)
            total_bs = Decimal("0.00")
            total_usd = Decimal("0.00")
            for t in transacciones:
                t.cierre = cierre
                t.save()
                total_bs += t.monto_bs
                total_usd += t.monto_usd

            # Update closure totals
            cierre.total_bs = total_bs
            cierre.total_usd = total_usd
            cierre.save()

            messages.success(
                request,
                f"Cierre registrado para {caja.nombre} "
                f"({cierre.get_turno_display()}).",
            )
            return redirect("cuadre_caja:cierre_detalle", cierre_id=cierre.id)

        messages.error(request, "Revisa los datos del cierre.")
    else:
        form = CierreCajaForm(caja=caja)
        egresos_formset = EgresoCierreFormSet(
            prefix="egresos", instance=CierreCaja()
        )
        transacciones_formset = CierreTransaccionFormSet(
            prefix="transacciones", instance=CierreCaja()
        )
        imagenes_formset = ImagenCierreFormSet(
            prefix="imagenes", instance=CierreCaja()
        )

    filas_bs, filas_usd = _filas_formulario(form)

    return render(
        request,
        "cuadre_caja/cerrar_caja.html",
        {
            "caja": caja,
            "form": form,
            "fecha": form.fecha,
            "filas_bs": filas_bs,
            "filas_usd": filas_usd,
            "egresos_formset": egresos_formset,
            "transacciones_formset": transacciones_formset,
            "imagenes_formset": imagenes_formset,
            "notas": form.data.get("notas", ""),
        },
    )


@login_required
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

    # Conteo de transacciones por método de pago (con respaldo en cierres antiguos).
    conteo = Counter(t.metodo_pago for t in transacciones)
    if not conteo and detalles:
        conteo = Counter(d.metodo_pago for d in detalles)
    conteo_metodos = [
        {
            "metodo": etiqueta,
            "cantidad": conteo[valor],
        }
        for valor, etiqueta in MetodoPagoChoices.choices
        if conteo.get(valor)
    ]

    # Conteo de transacciones por banco (agrupando variantes de mayúsculas).
    etiquetas_banco = {
        valor.lower(): etiqueta for valor, etiqueta in BANCOS_CHOICES if valor
    }
    conteo_por_banco = Counter()
    for transaccion in transacciones:
        banco = (transaccion.banco or "").strip()
        if not banco:
            continue
        nombre = etiquetas_banco.get(banco.lower(), banco)
        conteo_por_banco[nombre] += 1

    orden_bancos = [etiqueta for valor, etiqueta in BANCOS_CHOICES if valor]
    conteo_bancos = [
        {"banco": nombre, "cantidad": conteo_por_banco[nombre]}
        for nombre in orden_bancos
        if conteo_por_banco.get(nombre)
    ]
    for nombre in sorted(conteo_por_banco):
        if nombre not in orden_bancos:
            conteo_bancos.append(
                {"banco": nombre, "cantidad": conteo_por_banco[nombre]}
            )

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
            "conteo_metodos": conteo_metodos,
            "conteo_bancos": conteo_bancos,
        },
    )


@login_required
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


@login_required
def reportes(request):
    """Reportes por turno, caja y departamento para día, semana, mes o año."""
    hoy = timezone.localdate()
    form = ReporteFiltroForm(
        request.GET or None,
        initial={"fecha": hoy, "periodo": ReporteFiltroForm.PERIODO_DIA},
    )

    periodo = ReporteFiltroForm.PERIODO_DIA
    fecha_referencia = hoy
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
            "total_cierres": len(cierres),
        },
    )


@login_required
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


@login_required
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


@login_required
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


@login_required
def reporte_anual(request):
    """Reporte anual de cierres."""
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