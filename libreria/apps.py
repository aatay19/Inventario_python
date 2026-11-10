from django.apps import AppConfig


class LibreriaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "libreria"

    def ready(self):
        """Bloquea el borrado en el admin de Django para el rol Administrador."""
        from django.contrib.admin import ModelAdmin

        if getattr(ModelAdmin, "_borrado_bloqueado_admin", False):
            return

        has_delete_permission_original = ModelAdmin.has_delete_permission

        def has_delete_permission(model_admin, request, obj=None):
            perfil = getattr(getattr(request, "user", None), "perfilusuario", None)
            if perfil is not None and perfil.rol.lower() == "admin":
                return False
            return has_delete_permission_original(model_admin, request, obj)

        ModelAdmin.has_delete_permission = has_delete_permission
        ModelAdmin._borrado_bloqueado_admin = True
