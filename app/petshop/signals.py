"""Ghi log sự kiện đăng nhập để giám sát bảo mật bằng Loki (vd: dò mật khẩu)."""
import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

log = logging.getLogger("petshop")


def _ip(request):
    if request is None:
        return "-"
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "-")


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    log.info("event=login_success user=%s ip=%s", user.username, _ip(request))


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    log.info("event=logout user=%s ip=%s", getattr(user, "username", "-"), _ip(request))


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    username = str(credentials.get("username", "-")).replace(" ", "_")[:50]
    log.warning("event=login_failed user=%s ip=%s", username, _ip(request))
