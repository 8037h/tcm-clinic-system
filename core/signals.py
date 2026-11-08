from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .logging import log_operation


@receiver(user_logged_in)
def record_login(sender, request, user, **kwargs):
    log_operation(request, "用户", "登录", user.username, "用户登录系统", actor=user)
