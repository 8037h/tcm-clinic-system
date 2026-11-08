from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.exports import csv_response
from core.logging import log_operation
from core.models import Doctor, Schedule
from core.permissions import doctor_id_for, is_admin, require_access, scoped_queryset

from .forms import ReceptionRecordForm, ReceptionSearchForm
from .models import ReceptionRecord


@login_required
def reception_list(request):
    require_access(request.user, "receptions", "list")
    search_form = ReceptionSearchForm(request.GET or None)
    records = filtered_receptions(search_form, request.user)

    page_obj = Paginator(records, 10).get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return render(request, "receptions/reception_list.html", {
        "page_obj": page_obj,
        "search_form": search_form,
        "query_string": query_params.urlencode(),
    })


def filtered_receptions(search_form, user):
    records = scoped_queryset(user, "receptions", ReceptionRecord.objects.select_related("doctor__department", "schedule"))
    if search_form.is_valid():
        data = search_form.cleaned_data
        if data["patient_name"]:
            records = records.filter(patient_name__icontains=data["patient_name"])
        if data["doctor"]:
            records = records.filter(doctor__name__icontains=data["doctor"])
        if data["department"]:
            records = records.filter(doctor__department__name__icontains=data["department"])
        if data["status"]:
            records = records.filter(status=data["status"])
        if data["date_from"]:
            start = timezone.make_aware(datetime.combine(data["date_from"], time.min))
            records = records.filter(visit_time__gte=start)
        if data["date_to"]:
            # 半开区间避免时区转换和当天最后一秒精度问题。
            end = timezone.make_aware(datetime.combine(data["date_to"] + timedelta(days=1), time.min))
            records = records.filter(visit_time__lt=end)

    return records


@login_required
def reception_add(request):
    require_access(request.user, "receptions", "add")
    form = ReceptionRecordForm(request.POST or None)
    limit_form_relations(form, request.user)
    if request.method == "POST" and form.is_valid():
        try:
            record = form.save()
        except ValidationError as exc:
            form.add_error(None, "；".join(exc.messages))
        else:
            log_operation(request, "接诊记录", "新增", record)
            messages.success(request, "接诊记录新增成功。")
            return redirect("receptions:list")
    return render(request, "receptions/reception_form.html", {"form": form, "is_edit": False})


@login_required
def reception_detail(request, pk):
    require_access(request.user, "receptions", "detail")
    record = get_object_or_404(scoped_queryset(request.user, "receptions", ReceptionRecord.objects.select_related("doctor__department", "schedule")), pk=pk)
    return render(request, "receptions/reception_detail.html", {"record": record, "transitions": record.available_transitions()})


@login_required
def reception_edit(request, pk):
    require_access(request.user, "receptions", "edit")
    record = get_object_or_404(scoped_queryset(request.user, "receptions", ReceptionRecord.objects.all()), pk=pk)
    form = ReceptionRecordForm(request.POST or None, instance=record)
    limit_form_relations(form, request.user)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except ValidationError as exc:
            form.add_error(None, "；".join(exc.messages))
        else:
            log_operation(request, "接诊记录", "编辑", record)
            messages.success(request, "接诊记录已更新。")
            return redirect("receptions:detail", pk=record.pk)
    return render(request, "receptions/reception_form.html", {"form": form, "is_edit": True, "record": record})


@login_required
def reception_delete(request, pk):
    require_access(request.user, "receptions", "delete")
    record = get_object_or_404(scoped_queryset(request.user, "receptions", ReceptionRecord.objects.all()), pk=pk)
    if request.method == "POST":
        object_name = str(record)
        record.delete()
        log_operation(request, "接诊记录", "删除", object_name)
        messages.success(request, "接诊记录已删除。")
        return redirect("receptions:list")
    return render(request, "receptions/reception_confirm_delete.html", {"record": record})


@login_required
@require_POST
def reception_action(request, pk, action):
    require_access(request.user, "receptions", "action")
    with transaction.atomic():
        record = get_object_or_404(scoped_queryset(request.user, "receptions", ReceptionRecord.objects.select_for_update()), pk=pk)
        transitions = record.available_transitions()
        if action not in transitions:
            messages.error(request, "当前接诊状态不能执行此操作。")
        else:
            record.status = transitions[action][0]
            try:
                record.save()
            except ValidationError as exc:
                messages.error(request, "；".join(exc.messages))
            else:
                log_operation(request, "接诊记录", "状态修改", record, f"新状态：{record.get_status_display()}")
                messages.success(request, f"接诊状态已更新为{record.get_status_display()}。")
    return redirect("receptions:detail", pk=pk)


@login_required
def reception_export(request):
    require_access(request.user, "receptions", "export")
    records = filtered_receptions(ReceptionSearchForm(request.GET or None), request.user)
    rows = ((record.pk, record.patient_name, record.get_patient_gender_display(),
             record.patient_age, record.doctor.name, record.department.name,
             timezone.localtime(record.visit_time).strftime("%Y-%m-%d %H:%M"),
             record.diagnosis, record.treatment, record.get_status_display(),
             str(record.schedule) if record.schedule else "") for record in records)
    response = csv_response("receptions.csv", ["编号", "患者", "性别", "年龄", "医师", "科室",
                                                 "接诊时间", "诊断", "治疗", "状态", "排班"], rows)
    log_operation(request, "接诊记录", "数据导出", "接诊 CSV", f"筛选条件：{request.GET.urlencode()}")
    return response


def limit_form_relations(form, user):
    if is_admin(user):
        return
    doctor_id = doctor_id_for(user)
    form.fields["doctor"].queryset = Doctor.objects.filter(pk=doctor_id)
    form.fields["schedule"].queryset = Schedule.objects.filter(doctor_id=doctor_id)
    form.fields["doctor"].initial = doctor_id
