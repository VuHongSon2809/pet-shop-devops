from django.apps import AppConfig


class PetshopConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "petshop"
    verbose_name = "Cửa hàng thú cưng"

    def ready(self):
        from prometheus_client import REGISTRY

        from . import signals  # noqa: F401 – ghi log đăng nhập/đăng xuất

        from .metrics import PetshopCollector

        if not getattr(PetshopConfig, "_collector_registered", False):
            REGISTRY.register(PetshopCollector())
            PetshopConfig._collector_registered = True
