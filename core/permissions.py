"""Business-page roles and row ownership, based on Django auth and Doctor.user."""

from django.core.exceptions import PermissionDenied

from .models import Doctor


def is_admin(user):
    return user.is_authenticated and user.is_active and user.is_staff


def doctor_id_for(user):
    if not user.is_authenticated or not user.is_active:
        return None
    return Doctor.objects.filter(user_id=user.pk).values_list("pk", flat=True).first()


def can_access(user, section, action):
    if not user.is_authenticated or not user.is_active:
        return False
    if is_admin(user):
        return True
    if section in ("departments", "crawled_data"):
        return action in ("list", "detail")
    if section in ("analysis", "operation_logs"):
        return False
    if doctor_id_for(user) is None:
        return False
    if section in ("doctors", "schedules"):
        return action in ("list", "detail")
    if section == "performances":
        return action in ("list", "detail", "submit")
    if section == "receptions":
        return action in ("list", "detail", "add", "edit", "delete", "export", "action")
    return False


def require_access(user, section, action):
    if not can_access(user, section, action):
        raise PermissionDenied("当前账号无权执行此操作。")


def scoped_queryset(user, section, queryset):
    """Keep foreign rows out of lists, detail pages, exports and mutations."""
    if is_admin(user) or section == "departments":
        return queryset
    doctor_id = doctor_id_for(user)
    if doctor_id is None:
        return queryset.none()
    if section == "doctors":
        return queryset.filter(pk=doctor_id)
    if section in ("schedules", "performances", "receptions"):
        return queryset.filter(doctor_id=doctor_id)
    return queryset.none()
