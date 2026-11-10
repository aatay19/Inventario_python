def roles_cuadre_caja(request):
    """Expone banderas de rol para el menú de Cuadre de Caja."""
    puede_gestionar = False
    es_supervisor = False
    es_rol_cuadre_caja = False

    if request.user.is_authenticated:
        if request.user.is_superuser:
            puede_gestionar = True
            es_supervisor = True
        else:
            perfil = getattr(request.user, "perfilusuario", None)
            rol = getattr(perfil, "rol", None) if perfil else None
<<<<<<< HEAD
<<<<<<< HEAD
            if rol in {"admin", "soporte", "supervisor", "cuadre_caja", "supervisor_cuadre_caja"}:
                puede_gestionar = True
            if rol in {"admin", "soporte", "supervisor", "supervisor_cuadre_caja"}:
=======
            if rol in {"admin", "soporte", "supervisor_caja", "cuadre_caja"}:
                puede_gestionar = True
            if rol in {"admin", "soporte", "supervisor_caja"}:
>>>>>>> a8d7d7342fe65edf6d01a7fbee7f40316e1cdfa9
=======
            if rol in {"admin", "soporte", "supervisor_caja", "cuadre_caja"}:
                puede_gestionar = True
            if rol in {"admin", "soporte", "supervisor_caja"}:
>>>>>>> a8d7d7342fe65edf6d01a7fbee7f40316e1cdfa9
                es_supervisor = True
            if rol in {"cuadre_caja", "supervisor_cuadre_caja"}:
                es_rol_cuadre_caja = True

    return {
        "cuadre_puede_gestionar": puede_gestionar,
        "cuadre_es_supervisor": es_supervisor,
        "cuadre_es_rol_cuadre_caja": es_rol_cuadre_caja,
    }
