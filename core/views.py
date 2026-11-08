from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import FieldDoesNotExist, PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import (
    CrawledDataSearchForm, DepartmentForm, DepartmentSearchForm, DoctorForm, DoctorSearchForm,
    OperationLogSearchForm,
    PerformanceRecordForm, PerformanceSearchForm, RegistrationForm,
    ScheduleForm, ScheduleSearchForm,
)
from .analytics import analysis_snapshot, dashboard_metrics
from .exports import csv_response
from .logging import log_operation
from .models import CrawledMedicalData, Department, Doctor, OperationLog, PerformanceRecord, Schedule
from .permissions import can_access, doctor_id_for, is_admin, require_access, scoped_queryset


@login_required
def dashboard(request):
    if is_admin(request.user):
        return render(request, "dashboard.html", {"metrics": dashboard_metrics(), "charts": analysis_snapshot()["charts"]})
    return render(request, "dashboard.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("dashboard")
    return render(request, "registration/register.html", {"form": form})


class SectionMixin(LoginRequiredMixin):
    section = ""
    section_title = ""
    action = ""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            require_access(request.user, self.section, self.action)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return scoped_queryset(self.request.user, self.section, super().get_queryset())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            section=self.section,
            section_title=self.section_title,
            object_title=self.model._meta.verbose_name,
            list_url=f"{self.section}:list",
            add_url=f"{self.section}:add",
            detail_url=f"{self.section}:detail",
            edit_url=f"{self.section}:edit",
            delete_url=f"{self.section}:delete",
            can_add=can_access(self.request.user, self.section, "add"),
            can_edit=can_access(self.request.user, self.section, "edit"),
            can_delete=can_access(self.request.user, self.section, "delete"),
            can_export=can_access(self.request.user, self.section, "export"),
        )
        return context

    def get_success_url(self):
        return reverse(f"{self.section}:list")


class SectionListView(SectionMixin, ListView):
    action = "list"
    template_name = "core/object_list.html"
    context_object_name = "items"
    paginate_by = 10
    search_form_class = None

    def get_search_form(self):
        if not hasattr(self, "search_form"):
            self.search_form = self.search_form_class(self.request.GET or None)
            if self.section in ("schedules", "performances") and not is_admin(self.request.user):
                self.search_form.fields["doctor"].queryset = scoped_queryset(
                    self.request.user, "doctors", Doctor.objects.all()
                )
        return self.search_form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.copy()
        query.pop("page", None)
        context.update(search_form=self.get_search_form(), query_string=query.urlencode())
        return context


class SectionDetailView(SectionMixin, DetailView):
    action = "detail"
    template_name = "core/object_detail.html"
    detail_fields = ()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []
        for field_name in self.detail_fields:
            try:
                label = self.model._meta.get_field(field_name).verbose_name
            except FieldDoesNotExist:
                label = {"department": "科室"}[field_name]
            value = getattr(self.object, f"get_{field_name}_display", None)
            value = value() if value else getattr(self.object, field_name)
            rows.append((label, value))
        context["detail_rows"] = rows
        return context


class SectionFormMixin(SectionMixin):
    template_name = "core/object_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_edit"] = bool(getattr(self, "object", None))
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        is_edit = self.request.resolver_match.url_name == "edit"
        log_operation(self.request, self.section_title, "编辑" if is_edit else "新增", self.object)
        messages.success(self.request, "修改成功。" if is_edit else "新增成功。")
        return response


class SectionCreateView(SectionFormMixin, CreateView):
    action = "add"


class SectionUpdateView(SectionFormMixin, UpdateView):
    action = "edit"


class SectionDeleteView(SectionMixin, DeleteView):
    action = "delete"
    template_name = "core/object_confirm_delete.html"

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        object_name = str(self.object)
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(request, "该记录已被其他数据引用，不能删除。")
        else:
            log_operation(request, self.section_title, "删除", object_name)
            messages.success(request, "删除成功。")
        return redirect(self.get_success_url())


class DepartmentListView(SectionListView):
    model = Department
    section = "departments"
    section_title = "科室管理"
    search_form_class = DepartmentSearchForm

    def get_queryset(self):
        queryset = super().get_queryset()
        form = self.get_search_form()
        if form.is_valid():
            if form.cleaned_data["name"]:
                queryset = queryset.filter(name__icontains=form.cleaned_data["name"])
            if form.cleaned_data["status"]:
                queryset = queryset.filter(status=form.cleaned_data["status"])
        return queryset


class DepartmentCreateView(SectionCreateView):
    model = Department
    form_class = DepartmentForm
    section = "departments"
    section_title = "科室管理"


class DepartmentUpdateView(SectionUpdateView):
    model = Department
    form_class = DepartmentForm
    section = "departments"
    section_title = "科室管理"


class DepartmentDetailView(SectionDetailView):
    model = Department
    section = "departments"
    section_title = "科室管理"
    detail_fields = ("name", "description", "status", "created_at", "updated_at")


class DepartmentDeleteView(SectionDeleteView):
    model = Department
    section = "departments"
    section_title = "科室管理"


class DoctorListView(SectionListView):
    model = Doctor
    section = "doctors"
    section_title = "医师管理"
    search_form_class = DoctorSearchForm

    def get_queryset(self):
        queryset = super().get_queryset().select_related("department", "user")
        form = self.get_search_form()
        if form.is_valid():
            if form.cleaned_data["name"]:
                queryset = queryset.filter(name__icontains=form.cleaned_data["name"])
            if form.cleaned_data["department"]:
                queryset = queryset.filter(department=form.cleaned_data["department"])
            if form.cleaned_data["status"]:
                queryset = queryset.filter(status=form.cleaned_data["status"])
        return queryset


class DoctorCreateView(SectionCreateView):
    model = Doctor
    form_class = DoctorForm
    section = "doctors"
    section_title = "医师管理"


class DoctorUpdateView(SectionUpdateView):
    model = Doctor
    form_class = DoctorForm
    section = "doctors"
    section_title = "医师管理"


class DoctorDetailView(SectionDetailView):
    model = Doctor
    section = "doctors"
    section_title = "医师管理"
    detail_fields = ("name", "gender", "age", "phone", "department", "title", "specialty", "introduction", "status", "user", "created_at", "updated_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recent_schedules"] = self.object.schedules.order_by("-schedule_date", "-start_time")[:5]
        context["recent_receptions"] = self.object.reception_records.order_by("-visit_time")[:5]
        context["recent_performances"] = self.object.performance_records.order_by("-period_start")[:5]
        return context


class DoctorDeleteView(SectionDeleteView):
    model = Doctor
    section = "doctors"
    section_title = "医师管理"


class ScheduleListView(SectionListView):
    model = Schedule
    section = "schedules"
    section_title = "出诊排班"
    search_form_class = ScheduleSearchForm

    def get_queryset(self):
        queryset = super().get_queryset().select_related("doctor__department")
        form = self.get_search_form()
        if form.is_valid():
            if form.cleaned_data["doctor"]:
                queryset = queryset.filter(doctor=form.cleaned_data["doctor"])
            if form.cleaned_data["department"]:
                queryset = queryset.filter(doctor__department=form.cleaned_data["department"])
            if form.cleaned_data["schedule_date"]:
                queryset = queryset.filter(schedule_date=form.cleaned_data["schedule_date"])
            if form.cleaned_data["status"]:
                queryset = queryset.filter(status=form.cleaned_data["status"])
        return queryset


class ScheduleCreateView(SectionCreateView):
    model = Schedule
    form_class = ScheduleForm
    section = "schedules"
    section_title = "出诊排班"


class ScheduleUpdateView(SectionUpdateView):
    model = Schedule
    form_class = ScheduleForm
    section = "schedules"
    section_title = "出诊排班"


class ScheduleDetailView(SectionDetailView):
    model = Schedule
    section = "schedules"
    section_title = "出诊排班"
    detail_fields = ("doctor", "department", "schedule_date", "start_time", "end_time", "location", "max_patients", "booked_patients", "status", "remark", "created_at", "updated_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["linked_receptions"] = self.object.reception_records.order_by("-visit_time")
        context["remaining_slots"] = self.object.remaining_slots
        return context


class ScheduleDeleteView(SectionDeleteView):
    model = Schedule
    section = "schedules"
    section_title = "出诊排班"


class PerformanceListView(SectionListView):
    model = PerformanceRecord
    section = "performances"
    section_title = "绩效记录"
    search_form_class = PerformanceSearchForm

    def get_queryset(self):
        return filtered_performances(self.get_search_form(), self.request.user)


class PerformanceCreateView(SectionCreateView):
    model = PerformanceRecord
    form_class = PerformanceRecordForm
    section = "performances"
    section_title = "绩效记录"


class PerformanceUpdateView(SectionUpdateView):
    model = PerformanceRecord
    form_class = PerformanceRecordForm
    section = "performances"
    section_title = "绩效记录"


class PerformanceDetailView(SectionDetailView):
    model = PerformanceRecord
    section = "performances"
    section_title = "绩效记录"
    detail_fields = (
        "doctor", "period_start", "period_end", "reception_count", "completed_count",
        "base_score", "reward_score", "deduction_score", "total_score", "status",
        "reviewer", "review_time", "abnormal_remark", "attachment", "created_at", "updated_at",
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["transitions"] = self.object.available_transitions(self.request.user)
        context["can_recalculate"] = self.object.status in (PerformanceRecord.Status.DRAFT, PerformanceRecord.Status.PENDING)
        context["suggested_base_score"] = self.object.suggested_base_score
        return context


class PerformanceDeleteView(SectionDeleteView):
    model = PerformanceRecord
    section = "performances"
    section_title = "绩效记录"


@login_required
@require_POST
def performance_recalculate(request, pk):
    require_access(request.user, "performances", "recalculate")
    with transaction.atomic():
        record = get_object_or_404(scoped_queryset(request.user, "performances", PerformanceRecord.objects.select_for_update()), pk=pk)
        if record.status not in (PerformanceRecord.Status.DRAFT, PerformanceRecord.Status.PENDING):
            messages.error(request, "当前状态不能重新统计。")
        else:
            record.recalculate_counts()
            log_operation(request, "绩效记录", "重新统计", record)
            messages.success(request, "接诊数量已重新统计。")
    return redirect("performances:detail", pk=pk)


@login_required
@require_POST
def performance_action(request, pk, action):
    require_access(request.user, "performances", action)
    with transaction.atomic():
        record = get_object_or_404(scoped_queryset(request.user, "performances", PerformanceRecord.objects.select_for_update()), pk=pk)
        if action == "submit" and record.status == PerformanceRecord.Status.DRAFT:
            record.recalculate_counts()
        try:
            record.apply_transition(action, request.user)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            action_names = {"submit": "提交审核", "approve": "审核通过", "reject": "审核驳回", "confirm": "确认绩效"}
            log_operation(request, "绩效记录", action_names.get(action, action), record)
            messages.success(request, "绩效状态已更新。")
    return redirect("performances:detail", pk=pk)


def filtered_performances(form, user):
    queryset = scoped_queryset(user, "performances", PerformanceRecord.objects.select_related("doctor__department"))
    if form.is_valid():
        data = form.cleaned_data
        if data["doctor"]:
            queryset = queryset.filter(doctor=data["doctor"])
        if data["status"]:
            queryset = queryset.filter(status=data["status"])
        if data["period_start"]:
            queryset = queryset.filter(period_start__gte=data["period_start"])
        if data["period_end"]:
            queryset = queryset.filter(period_end__lte=data["period_end"])
    return queryset


@login_required
def analysis(request):
    require_access(request.user, "analysis", "detail")
    return render(request, "core/analysis.html", {"snapshot": analysis_snapshot()})


@login_required
def crawled_data_list(request):
    require_access(request.user, "crawled_data", "list")
    form = CrawledDataSearchForm(request.GET or None)
    queryset = CrawledMedicalData.objects.all()
    if form.is_valid():
        data = form.cleaned_data
        if data["keyword"]:
            queryset = queryset.filter(title__icontains=data["keyword"])
        if data["category"]:
            queryset = queryset.filter(category__icontains=data["category"])
        if data["source_name"]:
            queryset = queryset.filter(source_name__icontains=data["source_name"])
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "core/crawled_data_list.html", {
        "search_form": form, "page_obj": Paginator(queryset, 10).get_page(request.GET.get("page")),
        "query_string": query.urlencode(),
    })


@login_required
def operation_log_list(request):
    require_access(request.user, "operation_logs", "list")
    form = OperationLogSearchForm(request.GET or None)
    queryset = OperationLog.objects.select_related("user")
    if form.is_valid():
        data = form.cleaned_data
        if data["user"]:
            queryset = queryset.filter(user=data["user"])
        if data["module"]:
            queryset = queryset.filter(module__icontains=data["module"])
        if data["operation_type"]:
            queryset = queryset.filter(operation_type__icontains=data["operation_type"])
        if data["date_from"]:
            queryset = queryset.filter(created_at__date__gte=data["date_from"])
        if data["date_to"]:
            queryset = queryset.filter(created_at__date__lte=data["date_to"])
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "core/operation_log_list.html", {
        "search_form": form, "page_obj": Paginator(queryset, 10).get_page(request.GET.get("page")),
        "query_string": query.urlencode(),
    })


@login_required
def performance_export(request):
    require_access(request.user, "performances", "export")
    records = filtered_performances(PerformanceSearchForm(request.GET or None), request.user)
    rows = ((item.doctor.name, item.period_start, item.period_end, item.reception_count,
             item.completed_count, item.base_score, item.reward_score, item.deduction_score,
             item.total_score, item.get_status_display()) for item in records)
    response = csv_response("performances.csv", ["医师", "周期开始", "周期结束", "接诊数", "完成数",
                                                  "基础分", "奖励分", "扣分", "总分", "状态"], rows)
    log_operation(request, "绩效记录", "数据导出", "绩效 CSV", f"筛选条件：{request.GET.urlencode()}")
    return response


@login_required
def analysis_export(request):
    require_access(request.user, "analysis", "export")
    snapshot = analysis_snapshot()
    rows = [("总接诊数", snapshot["total"]),
            ("已完成概率", snapshot["completed_probability"]),
            ("取消概率", snapshot["cancelled_probability"]),
            ("平均每日接诊量", snapshot["daily_mean"]),
            ("每日接诊量方差", snapshot["daily_variance"]),
            ("每日接诊量标准差", snapshot["daily_stddev"])]
    rows += [(f"科室接诊概率：{row['name']}", row["probability"]) for row in snapshot["department_rows"]]
    rows += [(f"科室完成率：{row['name']}", row["completion_rate"]) for row in snapshot["department_rows"]]
    rows += [("已采集公开资料", snapshot["crawled_count"])]
    rows += [(f"采集分类：{row['category'] or '未分类'}", row["count"]) for row in snapshot["crawled_categories"]]
    response = csv_response("analysis.csv", ["指标", "数值"], rows)
    log_operation(request, "数据分析", "数据导出", "统计 CSV")
    return response
