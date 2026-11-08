from django.core.exceptions import ValidationError
from django.db import transaction
from django.db import models
from django.utils import timezone

from core.models import Doctor, Schedule


class ReceptionRecord(models.Model):
    class Gender(models.TextChoices):
        MALE = "male", "男"
        FEMALE = "female", "女"
        OTHER = "other", "其他"

    class Status(models.TextChoices):
        PENDING = "pending", "待接诊"
        IN_PROGRESS = "in_progress", "接诊中"
        COMPLETED = "completed", "已完成"
        CANCELLED = "cancelled", "已取消"

    patient_name = models.CharField("患者姓名", max_length=50)
    patient_gender = models.CharField("患者性别", max_length=10, choices=Gender.choices, blank=True)
    patient_age = models.PositiveSmallIntegerField("患者年龄", blank=True, null=True)
    patient_phone = models.CharField("患者电话", max_length=30, blank=True)
    doctor = models.ForeignKey(Doctor, verbose_name="接诊医师", on_delete=models.PROTECT, related_name="reception_records")
    schedule = models.ForeignKey(Schedule, verbose_name="对应排班", on_delete=models.SET_NULL, null=True, blank=True, related_name="reception_records")
    visit_time = models.DateTimeField("接诊时间")
    chief_complaint = models.CharField("主诉", max_length=200)
    symptoms = models.TextField("症状描述", blank=True)
    diagnosis = models.TextField("诊断结果", blank=True)
    treatment = models.TextField("治疗/处理意见", blank=True)
    prescription = models.TextField("处方内容", blank=True)
    status = models.CharField("接诊状态", max_length=20, choices=Status.choices, default=Status.PENDING)
    remark = models.TextField("备注", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "接诊记录"
        verbose_name_plural = "接诊记录"
        ordering = ["-visit_time", "-id"]
        indexes = [models.Index(fields=["visit_time", "status"], name="reception_visit_status_idx")]

    @property
    def department(self):
        return self.doctor.department

    def available_transitions(self):
        return {
            self.Status.PENDING: {"start": (self.Status.IN_PROGRESS, "开始接诊"), "cancel": (self.Status.CANCELLED, "取消接诊")},
            self.Status.IN_PROGRESS: {"complete": (self.Status.COMPLETED, "完成接诊"), "cancel": (self.Status.CANCELLED, "取消接诊")},
        }.get(self.status, {})

    def clean(self):
        previous = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        if previous and self.status != previous.status:
            permitted = {target for target, _ in previous.available_transitions().values()}
            if self.status not in permitted:
                raise ValidationError({"status": "不允许从当前接诊状态直接跳转到所选状态。"})
        if self.status == self.Status.COMPLETED:
            errors = {}
            if not self.diagnosis or not self.diagnosis.strip():
                errors["diagnosis"] = "完成接诊前请填写诊断结果。"
            if not self.treatment or not self.treatment.strip():
                errors["treatment"] = "完成接诊前请填写治疗方案。"
            if errors:
                raise ValidationError(errors)
        if not self.schedule_id:
            return
        schedule = self.schedule
        if self.doctor_id and schedule.doctor_id != self.doctor_id:
            raise ValidationError({"schedule": "排班医师与接诊医师不一致，科室也必须一致。"})
        if self.visit_time and schedule.schedule_date and schedule.start_time and schedule.end_time:
            local_visit = timezone.localtime(self.visit_time) if timezone.is_aware(self.visit_time) else self.visit_time
            if local_visit.date() != schedule.schedule_date or not (schedule.start_time <= local_visit.time().replace(tzinfo=None) < schedule.end_time):
                raise ValidationError({"visit_time": "接诊时间必须在所选排班的日期与时段内。"})
        if self.status != self.Status.CANCELLED:
            new_link = not previous or previous.schedule_id != self.schedule_id or previous.status == self.Status.CANCELLED
            if new_link and schedule.status != Schedule.Status.NORMAL:
                raise ValidationError({"schedule": "只能为正常出诊的排班新增有效接诊。"})
            occupied = type(self).objects.filter(schedule_id=self.schedule_id).exclude(status=self.Status.CANCELLED).exclude(pk=self.pk).count()
            if occupied >= schedule.max_patients:
                raise ValidationError({"schedule": "该排班已满号，请选择其他排班。"})

    def save(self, *args, **kwargs):
        with transaction.atomic():
            previous = type(self).objects.select_for_update().filter(pk=self.pk).first() if self.pk else None
            schedule_ids = {schedule_id for schedule_id in (self.schedule_id, previous.schedule_id if previous else None) if schedule_id}
            list(Schedule.objects.select_for_update().filter(pk__in=schedule_ids).order_by("pk"))
            self.full_clean()
            super().save(*args, **kwargs)
            for schedule in Schedule.objects.filter(pk__in=schedule_ids):
                schedule.sync_booked_patients()

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            schedule_id = self.schedule_id
            if schedule_id:
                Schedule.objects.select_for_update().get(pk=schedule_id)
            result = super().delete(*args, **kwargs)
            if schedule_id:
                Schedule.objects.get(pk=schedule_id).sync_booked_patients()
            return result

    def __str__(self):
        return f"{self.patient_name} - {self.doctor.name} - {self.get_status_display()}"
