"""绩效专用入口。保持旧 core.views 接口不变。"""

from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from . import views
from .logging import log_operation
from .models import PerformanceRecord


def visible_records(user):
    records = PerformanceRecord.objects.all()
    return records if user.is_staff else records.filter(doctor__user=user)


def require_staff(user):
    if not user.is_staff:
        raise PermissionDenied


class PerformanceListView(views.PerformanceListView):
    def get_queryset(self):
        return super().get_queryset().filter(pk__in=visible_records(self.request.user).values("pk"))


class PerformanceCreateView(views.PerformanceCreateView):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            require_staff(request.user)
        return super().dispatch(request, *args, **kwargs)


class PerformanceUpdateView(views.PerformanceUpdateView):
    def get_queryset(self):
        require_staff(self.request.user)
        return PerformanceRecord.objects.filter(status__in=[PerformanceRecord.Status.DRAFT, PerformanceRecord.Status.REJECTED])


class PerformanceDeleteView(views.PerformanceDeleteView):
    def get_queryset(self):
        require_staff(self.request.user)
        return PerformanceRecord.objects.filter(status__in=[PerformanceRecord.Status.DRAFT, PerformanceRecord.Status.REJECTED])


class PerformanceDetailView(views.PerformanceDetailView):
    detail_fields = tuple(field for field in views.PerformanceDetailView.detail_fields if field != "attachment")

    def get_queryset(self):
        return visible_records(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["performance_history"] = self.object.operation_logs.select_related("user").order_by("created_at", "pk")
        context["can_manage_performance"] = self.request.user.is_staff and self.object.status in (
            PerformanceRecord.Status.DRAFT, PerformanceRecord.Status.REJECTED,
        )
        context["can_recalculate"] = self.request.user.is_staff and self.object.status in (
            PerformanceRecord.Status.DRAFT, PerformanceRecord.Status.REJECTED,
        )
        if not self.request.user.is_staff and self.object.doctor.user_id != self.request.user.pk:
            context["transitions"] = {}
        return context


@login_required
@require_POST
def recalculate(request, pk):
    require_staff(request.user)
    with transaction.atomic():
        record = get_object_or_404(PerformanceRecord.objects.select_for_update(), pk=pk)
        if record.status not in (record.Status.DRAFT, record.Status.REJECTED):
            raise PermissionDenied
        record.recalculate_counts()
        log_operation(request, "绩效记录", "重新统计", record, f"有效接诊 {record.reception_count}，完成 {record.completed_count}")
    messages.success(request, "接诊数量已重新统计。")
    return redirect("performances:detail", pk=pk)


@login_required
@require_POST
def action(request, pk, action):
    with transaction.atomic():
        record = get_object_or_404(visible_records(request.user).select_for_update(), pk=pk)
        if action != "submit":
            require_staff(request.user)
        if action == "submit" and record.status in (record.Status.DRAFT, record.Status.REJECTED):
            record.recalculate_counts()
        old_status = record.status
        try:
            record.apply_transition(action, request.user)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            log_operation(request, "绩效记录", dict(submit="提交审核", approve="审核通过", reject="审核驳回", confirm="确认绩效").get(action, action), record,
                          f"{old_status} → {record.status}；总分 {record.total_score}")
            messages.success(request, "绩效状态已更新。")
    return redirect("performances:detail", pk=pk)


@login_required
def attachment(request, pk):
    record = get_object_or_404(visible_records(request.user), pk=pk)
    if not record.attachment:
        raise Http404
    try:
        handle = record.attachment.open("rb")
    except FileNotFoundError:
        raise Http404 from None
    log_operation(request, "绩效记录", "查看附件", record)
    return FileResponse(handle, as_attachment=True, filename=f"performance-{pk}{Path(record.attachment.name).suffix}")


@login_required
def export(request):
    require_staff(request.user)
    return views.performance_export(request)
