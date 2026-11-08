from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .performance_storage import PrivatePerformanceStorage, performance_attachment_path


class ActiveStatus(models.TextChoices):
    ACTIVE = "active", "启用"
    INACTIVE = "inactive", "停用"


class Department(models.Model):
    name = models.CharField("科室名称", max_length=100, unique=True)
    description = models.TextField("科室介绍", blank=True)
    status = models.CharField("状态", max_length=10, choices=ActiveStatus.choices, default=ActiveStatus.ACTIVE)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "科室"
        verbose_name_plural = "科室"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Doctor(models.Model):
    class Gender(models.TextChoices):
        MALE = "male", "男"
        FEMALE = "female", "女"
        OTHER = "other", "其他"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name="登录用户", null=True, blank=True, on_delete=models.SET_NULL, related_name="doctor_profile")
    name = models.CharField("姓名", max_length=50)
    gender = models.CharField("性别", max_length=10, choices=Gender.choices, blank=True)
    age = models.PositiveSmallIntegerField("年龄", null=True, blank=True)
    phone = models.CharField("电话", max_length=30, blank=True)
    department = models.ForeignKey(Department, verbose_name="科室", on_delete=models.PROTECT, related_name="doctors")
    title = models.CharField("职称", max_length=100, blank=True)
    specialty = models.TextField("擅长", blank=True)
    introduction = models.TextField("简介", blank=True)
    status = models.CharField("状态", max_length=10, choices=ActiveStatus.choices, default=ActiveStatus.ACTIVE)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "医师"
        verbose_name_plural = "医师"
        ordering = ["name", "id"]

    def __str__(self):
        return f"{self.name}（{self.department.name}）"


class Schedule(models.Model):
    class Status(models.TextChoices):
        NORMAL = "normal", "正常出诊"
        SUSPENDED = "suspended", "停诊"
        ENDED = "ended", "已结束"

    doctor = models.ForeignKey(Doctor, verbose_name="医师", on_delete=models.PROTECT, related_name="schedules")
    schedule_date = models.DateField("出诊日期")
    start_time = models.TimeField("开始时间")
    end_time = models.TimeField("结束时间")
    max_patients = models.PositiveIntegerField("最大接诊人数", default=0)
    booked_patients = models.PositiveIntegerField("已预约人数", default=0)
    location = models.CharField("出诊地点", max_length=100, blank=True)
    status = models.CharField("状态", max_length=10, choices=Status.choices, default=Status.NORMAL)
    remark = models.TextField("备注", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "出诊排班"
        verbose_name_plural = "出诊排班"
        ordering = ["-schedule_date", "start_time"]

    @property
    def department(self):
        return self.doctor.department

    @property
    def remaining_slots(self):
        return max(0, self.max_patients - self.booked_patients)

    def active_reception_count(self):
        if not self.pk:
            return 0
        return self.reception_records.exclude(status="cancelled").count()

    def sync_booked_patients(self):
        count = self.active_reception_count()
        Schedule.objects.filter(pk=self.pk).update(booked_patients=count, updated_at=timezone.now())
        self.booked_patients = count
        return count

    def has_time_conflict(self):
        if not self.doctor_id or not self.schedule_date or not self.start_time or not self.end_time:
            return False
        return Schedule.objects.filter(
            doctor_id=self.doctor_id,
            schedule_date=self.schedule_date,
            status=Schedule.Status.NORMAL,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
        ).exclude(pk=self.pk).exists()

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({"end_time": "结束时间必须晚于开始时间。"})
        actual_count = self.active_reception_count()
        if self.max_patients is not None and actual_count > self.max_patients:
            raise ValidationError({"max_patients": "最大接诊人数不能少于已有的有效接诊人数。"})
        if self.pk and self.doctor_id and self.schedule_date and self.start_time and self.end_time:
            from receptions.models import ReceptionRecord

            linked = ReceptionRecord.objects.filter(schedule_id=self.pk)
            if linked.exclude(doctor_id=self.doctor_id).exists():
                raise ValidationError({"doctor": "已有接诊记录，不能更换为其他医师。"})
            for visit_time in linked.values_list("visit_time", flat=True):
                local_visit = timezone.localtime(visit_time) if timezone.is_aware(visit_time) else visit_time
                if local_visit.date() != self.schedule_date or not (self.start_time <= local_visit.time().replace(tzinfo=None) < self.end_time):
                    raise ValidationError("已有接诊时间不在修改后的排班时段内。")
        if self.status == self.Status.NORMAL and self.has_time_conflict():
            raise ValidationError("该医师在此时段已有正常出诊排班。")

    def save(self, *args, **kwargs):
        self.booked_patients = self.active_reception_count()
        self.full_clean()
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"booked_patients"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.doctor.name} {self.schedule_date} {self.start_time}-{self.end_time}"


class PerformanceRecord(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "待提交"
        PENDING = "pending", "待审核"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已驳回"
        CONFIRMED = "confirmed", "已确认"

    doctor = models.ForeignKey(Doctor, verbose_name="医师", on_delete=models.PROTECT, related_name="performance_records")
    period_start = models.DateField("周期开始")
    period_end = models.DateField("周期结束")
    reception_count = models.PositiveIntegerField("接诊总数", default=0)
    completed_count = models.PositiveIntegerField("完成接诊数", default=0)
    base_score = models.DecimalField("基础分", max_digits=9, decimal_places=2, default=Decimal("0"))
    reward_score = models.DecimalField("奖励分", max_digits=9, decimal_places=2, default=Decimal("0"))
    deduction_score = models.DecimalField("扣减分", max_digits=9, decimal_places=2, default=Decimal("0"))
    total_score = models.DecimalField("总分", max_digits=10, decimal_places=2, default=Decimal("0"), editable=False)
    status = models.CharField("状态", max_length=12, choices=Status.choices, default=Status.DRAFT)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="审核人", null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_performance_records")
    review_time = models.DateTimeField("审核时间", null=True, blank=True)
    abnormal_remark = models.TextField("异常说明", blank=True)
    attachment = models.FileField("附件", upload_to=performance_attachment_path, storage=PrivatePerformanceStorage(), blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "绩效记录"
        verbose_name_plural = "绩效记录"
        ordering = ["-period_start", "doctor_id"]

    def clean(self):
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValidationError({"period_end": "周期结束不能早于开始。"})
        if self.completed_count is not None and self.reception_count is not None and self.completed_count > self.reception_count:
            raise ValidationError({"completed_count": "完成接诊数不能超过接诊总数。"})
        for name in ("base_score", "reward_score", "deduction_score"):
            if getattr(self, name) is not None and getattr(self, name) < 0:
                raise ValidationError({name: "分值不能为负数。"})

    def save(self, *args, **kwargs):
        if self.doctor_id and self.period_start and self.period_end and (self._state.adding or kwargs.get("update_fields") is None):
            self.reception_count, self.completed_count = self.calculate_reception_counts()
        self.total_score = sum(
            (Decimal(str(value or 0)) for value in (self.base_score, self.reward_score)),
            Decimal("0"),
        ) - Decimal(str(self.deduction_score or 0))
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"total_score"}
        super().save(*args, **kwargs)

    @property
    def suggested_base_score(self):
        return Decimal(self.completed_count or 0) * Decimal("10.00")

    def recalculate_counts(self):
        self.reception_count, self.completed_count = self.calculate_reception_counts()
        self.save(update_fields={"reception_count", "completed_count", "updated_at"})

    def calculate_reception_counts(self):
        from receptions.models import ReceptionRecord

        records = ReceptionRecord.objects.filter(
            doctor_id=self.doctor_id,
            visit_time__date__gte=self.period_start,
            visit_time__date__lte=self.period_end,
        ).exclude(status=ReceptionRecord.Status.CANCELLED)
        return records.count(), records.filter(status=ReceptionRecord.Status.COMPLETED).count()

    def available_transitions(self, user):
        if self.status in (self.Status.DRAFT, self.Status.REJECTED):
            return {"submit": (self.Status.PENDING, "提交审核")}
        if self.status == self.Status.PENDING and user.is_staff:
            return {
                "approve": (self.Status.APPROVED, "审核通过"),
                "reject": (self.Status.REJECTED, "驳回"),
            }
        if self.status == self.Status.APPROVED and user.is_staff:
            return {"confirm": (self.Status.CONFIRMED, "确认绩效")}
        return {}

    def apply_transition(self, action, user):
        transitions = self.available_transitions(user)
        if action not in transitions:
            raise ValidationError("当前状态或权限不允许此操作。")
        self.status = transitions[action][0]
        fields = {"status", "updated_at"}
        if action in ("approve", "reject"):
            self.reviewer = user
            self.review_time = timezone.now()
            fields.update({"reviewer", "review_time"})
        elif action == "submit":
            self.reviewer = None
            self.review_time = None
            fields.update({"reviewer", "review_time"})
        self.save(update_fields=fields)

    def __str__(self):
        return f"{self.doctor.name} {self.period_start} 至 {self.period_end}"


class OperationLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="用户", null=True, blank=True, on_delete=models.SET_NULL, related_name="operation_logs")
    performance_record = models.ForeignKey("PerformanceRecord", verbose_name="绩效记录", null=True, blank=True, on_delete=models.SET_NULL, related_name="operation_logs")
    module = models.CharField("模块", max_length=100)
    operation_type = models.CharField("操作类型", max_length=50)
    object_name = models.CharField("对象名称", max_length=200, blank=True)
    description = models.TextField("描述", blank=True)
    ip_address = models.GenericIPAddressField("IP 地址", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "操作日志"
        verbose_name_plural = "操作日志"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.module} · {self.operation_type}"


class CrawledMedicalData(models.Model):
    title = models.CharField("标题", max_length=200)
    category = models.CharField("分类", max_length=50, blank=True)
    symptom = models.CharField("症状关键词", max_length=200, blank=True)
    department_name = models.CharField("相关科室", max_length=100, blank=True)
    source_name = models.CharField("来源名称", max_length=100)
    source_url = models.URLField("原文地址", max_length=500, unique=True)
    publish_date = models.DateField("发布日期", null=True, blank=True)
    crawled_at = models.DateTimeField("采集时间", auto_now_add=True)
    raw_text = models.TextField("公开文本", blank=True)

    class Meta:
        verbose_name = "采集数据"
        verbose_name_plural = "采集数据"
        ordering = ["-crawled_at"]

    def __str__(self):
        return self.title
