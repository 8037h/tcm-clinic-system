"""关键角色访问和排班到绩效的完整业务验收。"""

from datetime import date, time
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from receptions.models import ReceptionRecord

from .models import Department, Doctor, OperationLog, PerformanceRecord, Schedule
from .performance_storage import PrivatePerformanceStorage


class AccessAndWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("manager", password="StrongPass765!", is_staff=True)
        self.doctor_user = User.objects.create_user("doctor_account", password="StrongPass765!")
        self.normal_user = User.objects.create_user("normal_account", password="StrongPass765!")
        self.department = Department.objects.create(name="针灸科")
        self.other_department = Department.objects.create(name="推拿科")
        self.doctor = Doctor.objects.create(name="演示医师甲", department=self.department, user=self.doctor_user)
        self.other_doctor = Doctor.objects.create(name="演示医师乙", department=self.other_department)
        self.day = date(2026, 11, 12)

    def test_role_menu_and_direct_url_scope(self):
        self.client.force_login(self.normal_user)
        dashboard = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertNotContains(dashboard, "chart-data")
        self.assertNotContains(dashboard, "出诊排班")
        self.assertEqual(self.client.get(reverse("departments:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("doctors:list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("analysis")).status_code, 403)
        self.assertEqual(self.client.get(reverse("departments:add")).status_code, 403)

        foreign_schedule = Schedule.objects.create(
            doctor=self.other_doctor, schedule_date=self.day,
            start_time=time(9), end_time=time(12), max_patients=2,
        )
        self.client.force_login(self.doctor_user)
        self.assertContains(self.client.get(reverse("dashboard")), "本人排班")
        self.assertEqual(self.client.get(reverse("schedules:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("schedules:detail", args=[foreign_schedule.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("schedules:add")).status_code, 403)
        self.assertEqual(self.client.get(reverse("performances:export")).status_code, 403)

    def test_complete_reception_and_performance_approval(self):
        schedule = Schedule.objects.create(
            doctor=self.doctor, schedule_date=self.day,
            start_time=time(9), end_time=time(12), max_patients=2,
        )
        self.client.force_login(self.doctor_user)
        reception_data = {
            "patient_name": "演示患者甲", "doctor": str(self.doctor.pk),
            "schedule": str(schedule.pk), "visit_time_0": self.day.isoformat(),
            "visit_time_1": "09:30", "chief_complaint": "演示用头痛主诉",
            "diagnosis": "", "treatment": "", "prescription": "", "remark": "模拟业务数据",
        }
        self.assertRedirects(
            self.client.post(reverse("receptions:add"), reception_data), reverse("receptions:list")
        )
        reception = ReceptionRecord.objects.get(patient_name="演示患者甲")
        schedule.refresh_from_db()
        self.assertEqual(schedule.booked_patients, 1)
        self.assertRedirects(
            self.client.post(reverse("receptions:action", args=[reception.pk, "start"])),
            reverse("receptions:detail", args=[reception.pk]),
        )
        reception_data.update(diagnosis="演示诊断", treatment="演示治疗方案")
        self.assertRedirects(
            self.client.post(reverse("receptions:edit", args=[reception.pk]), reception_data),
            reverse("receptions:detail", args=[reception.pk]),
        )
        self.assertRedirects(
            self.client.post(reverse("receptions:action", args=[reception.pk, "complete"])),
            reverse("receptions:detail", args=[reception.pk]),
        )
        reception.refresh_from_db()
        self.assertEqual(reception.status, ReceptionRecord.Status.COMPLETED)

        self.client.force_login(self.admin)
        performance_data = {
            "doctor": str(self.doctor.pk), "period_start": self.day.isoformat(),
            "period_end": self.day.isoformat(), "base_score": "100",
            "reward_score": "20", "deduction_score": "5", "abnormal_remark": "",
        }
        self.assertRedirects(
            self.client.post(reverse("performances:add"), performance_data),
            reverse("performances:list"),
        )
        performance = PerformanceRecord.objects.get(doctor=self.doctor)
        self.assertEqual((performance.reception_count, performance.completed_count), (1, 1))
        self.assertEqual(performance.total_score, Decimal("115"))

        self.client.force_login(self.doctor_user)
        self.assertRedirects(
            self.client.post(reverse("performances:action", args=[performance.pk, "submit"])),
            reverse("performances:detail", args=[performance.pk]),
        )
        self.client.force_login(self.admin)
        for action in ("approve", "confirm"):
            self.assertRedirects(
                self.client.post(reverse("performances:action", args=[performance.pk, action])),
                reverse("performances:detail", args=[performance.pk]),
            )
        performance.refresh_from_db()
        self.assertEqual(performance.status, PerformanceRecord.Status.CONFIRMED)
        self.assertEqual(performance.reviewer, self.admin)
        self.assertIsNotNone(performance.review_time)
        self.assertGreaterEqual(OperationLog.objects.filter(performance_record=performance).count(), 4)

    def test_performance_attachment_requires_authorized_user(self):
        field = PerformanceRecord._meta.get_field("attachment")
        original_storage = field.storage
        with TemporaryDirectory() as directory:
            storage = PrivatePerformanceStorage()
            storage._location = Path(directory)
            field.storage = storage
            try:
                performance = PerformanceRecord.objects.create(
                    doctor=self.doctor, period_start=self.day, period_end=self.day,
                )
                performance.attachment.save("evidence.txt", ContentFile(b"demo attachment"))
                with self.assertRaises(ValueError):
                    performance.attachment.url
                download = reverse("performances:attachment", args=[performance.pk])
                self.client.force_login(self.normal_user)
                self.assertEqual(self.client.get(download).status_code, 404)
                self.client.force_login(self.doctor_user)
                response = self.client.get(download)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(b"".join(response.streaming_content), b"demo attachment")
            finally:
                field.storage = original_storage
