from .models import OperationLog, PerformanceRecord


def log_operation(request, module, operation_type, object_name="", description="", actor=None):
    """Record a meaningful write action; command-line jobs may pass request=None."""
    request_user = getattr(request, "user", None)
    user = actor or (request_user if request_user is not None and request_user.is_authenticated else None)
    ip = request.META.get("REMOTE_ADDR") if request is not None else None
    return OperationLog.objects.create(
        user=user,
        performance_record=object_name if isinstance(object_name, PerformanceRecord) and object_name.pk else None,
        module=module[:100],
        operation_type=operation_type[:50],
        object_name=str(object_name)[:200],
        description=str(description),
        ip_address=ip or None,
    )
