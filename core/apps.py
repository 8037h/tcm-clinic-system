from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "基础管理"

    def ready(self):
        from . import signals  # noqa: F401
