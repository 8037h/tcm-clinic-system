from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Department, Doctor, Schedule
from .models import ReceptionRecord


class ReceptionRecordTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("reception_user", password="StrongPass765!", is_staff=True)
        self.client.force_login(self.user)
        department = Department.objects.create(name="中医内科")
        self.doctor = Doctor.objects.create(name="李明医师", department=department)
        other_department = Department.objects.create(name="针灸科")
        self.other_doctor = Doctor.objects.create(name="王晓医师", department=other_department)
        self.visit_time = timezone.make_aware(datetime(2026, 10, 10, 9, 30))
        self.record = ReceptionRecord.objects.create(
            patient_name="张伟", doctor=self.doctor,
            visit_time=self.visit_time, chief_complaint="失眠", status=ReceptionRecord.Status.PENDING,
        )

    def form_data(self, **overrides):
        data = {
            "patient_name": "李娜", "patient_gender": "female", "patient_age": "35",
            "doctor": str(self.other_doctor.pk), "schedule": "", "visit_time_0": "2026-10-11",
            "visit_time_1": "10:30", "chief_complaint": "腰痛", "symptoms": "久坐后腰酸",
            "diagnosis": "", "treatment": "", "prescription": "", "remark": "",
        }
        data.update(overrides)
        return data

    def create_schedule(self, **overrides):
        data = {
            "doctor": self.other_doctor,
            "schedule_date": self.visit_time.date() + timedelta(days=1),
            "start_time": time(9),
            "end_time": time(12),
            "max_patients": 1,
        }
        data.update(overrides)
        return Schedule.objects.create(**data)

    def action(self, record, action):
        return self.client.post(reverse("receptions:action", args=[record.pk, action]))

    def test_model_creation_and_string(self):
        self.assertEqual(self.record.get_status_display(), "待接诊")
        self.assertIn("张伟", str(self.record))

    def test_list_and_add_pages_accessible(self):
        self.assertEqual(self.client.get(reverse("receptions:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("receptions:add")).status_code, 200)

    def test_create_record(self):
        response = self.client.post(reverse("receptions:add"), self.form_data())
        self.assertRedirects(response, reverse("receptions:list"))
        self.assertTrue(ReceptionRecord.objects.filter(patient_name="李娜").exists())

    def test_edit_record_and_complete_via_status_actions(self):
        self.assertRedirects(self.action(self.record, "start"), reverse("receptions:detail", args=[self.record.pk]))
        response = self.client.post(
            reverse("receptions:edit", args=[self.record.pk]),
            self.form_data(
                patient_name="张伟", doctor=str(self.doctor.pk),
                visit_time_0="2026-10-10", visit_time_1="09:30",
                diagnosis="心肾不交证", treatment="养心安神",
            ),
        )
        self.assertRedirects(response, reverse("receptions:detail", args=[self.record.pk]))
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, ReceptionRecord.Status.IN_PROGRESS)
        self.assertRedirects(self.action(self.record, "complete"), reverse("receptions:detail", args=[self.record.pk]))
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, ReceptionRecord.Status.COMPLETED)
        self.assertContains(self.client.get(reverse("receptions:detail", args=[self.record.pk])), "养心安神")

    def test_completed_requires_diagnosis_and_treatment(self):
        self.action(self.record, "start")
        response = self.action(self.record, "complete")
        self.assertRedirects(response, reverse("receptions:detail", args=[self.record.pk]))
        self.assertContains(self.client.get(reverse("receptions:detail", args=[self.record.pk])), "接诊中")
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, ReceptionRecord.Status.IN_PROGRESS)
        self.assertEqual(ReceptionRecord.objects.count(), 1)

        self.record.status = ReceptionRecord.Status.COMPLETED
        with self.assertRaises(ValidationError) as raised:
            self.record.save()
        self.assertIn("diagnosis", raised.exception.message_dict)
        self.assertIn("treatment", raised.exception.message_dict)

    def test_cannot_skip_or_reverse_status_transition(self):
        self.assertRedirects(self.action(self.record, "complete"), reverse("receptions:detail", args=[self.record.pk]))
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, ReceptionRecord.Status.PENDING)
        self.record.status = ReceptionRecord.Status.COMPLETED
        self.record.diagnosis = "心肾不交证"
        self.record.treatment = "养心安神"
        with self.assertRaises(ValidationError) as raised:
            self.record.save()
        self.assertIn("status", raised.exception.message_dict)

    def test_schedule_link_checks_doctor_and_visit_time(self):
        schedule = self.create_schedule()
        response = self.client.post(reverse("receptions:add"), self.form_data(schedule=str(schedule.pk)))
        self.assertRedirects(response, reverse("receptions:list"))
        linked = ReceptionRecord.objects.get(patient_name="李娜")
        self.assertEqual(linked.schedule, schedule)
        self.assertEqual(linked.department, self.other_doctor.department)
        schedule.refresh_from_db()
        self.assertEqual(schedule.booked_patients, 1)

        wrong_doctor = self.client.post(reverse("receptions:add"), self.form_data(
            patient_name="异科患者", schedule=str(schedule.pk), doctor=str(self.doctor.pk),
        ))
        self.assertEqual(wrong_doctor.status_code, 200)
        self.assertIn("schedule", wrong_doctor.context["form"].errors)
        wrong_time = self.client.post(reverse("receptions:add"), self.form_data(
            patient_name="时段外患者", schedule=str(schedule.pk), visit_time_1="12:00",
        ))
        self.assertEqual(wrong_time.status_code, 200)
        self.assertIn("visit_time", wrong_time.context["form"].errors)
        self.assertEqual(ReceptionRecord.objects.filter(schedule=schedule).count(), 1)

    def test_full_schedule_rejects_new_reception(self):
        schedule = self.create_schedule()
        self.client.post(reverse("receptions:add"), self.form_data(schedule=str(schedule.pk)))
        response = self.client.post(reverse("receptions:add"), self.form_data(
            patient_name="第二位患者", schedule=str(schedule.pk),
        ))
        self.assertEqual(response.status_code, 200)
        self.assertIn("schedule", response.context["form"].errors)
        self.assertContains(response, "该排班已满号")
        self.assertFalse(ReceptionRecord.objects.filter(patient_name="第二位患者").exists())
        schedule.refresh_from_db()
        self.assertEqual(schedule.booked_patients, 1)
        self.assertEqual(schedule.remaining_slots, 0)

    def test_cancel_restores_slot_and_allows_new_reception(self):
        schedule = self.create_schedule()
        self.client.post(reverse("receptions:add"), self.form_data(schedule=str(schedule.pk)))
        first = ReceptionRecord.objects.get(patient_name="李娜")
        self.assertRedirects(self.action(first, "cancel"), reverse("receptions:detail", args=[first.pk]))
        first.refresh_from_db()
        schedule.refresh_from_db()
        self.assertEqual(first.status, ReceptionRecord.Status.CANCELLED)
        self.assertEqual(schedule.booked_patients, 0)
        self.assertEqual(schedule.remaining_slots, 1)

        response = self.client.post(reverse("receptions:add"), self.form_data(
            patient_name="第二位患者", schedule=str(schedule.pk),
        ))
        self.assertRedirects(response, reverse("receptions:list"))
        schedule.refresh_from_db()
        self.assertEqual(schedule.booked_patients, 1)
        self.assertEqual(ReceptionRecord.objects.filter(schedule=schedule).count(), 2)

    def test_suspended_schedule_rejects_new_reception(self):
        schedule = self.create_schedule(status=Schedule.Status.SUSPENDED)
        response = self.client.post(reverse("receptions:add"), self.form_data(schedule=str(schedule.pk)))
        self.assertEqual(response.status_code, 200)
        self.assertIn("schedule", response.context["form"].errors)
        self.assertFalse(ReceptionRecord.objects.filter(patient_name="李娜").exists())

    def test_combined_search_and_date_range(self):
        ReceptionRecord.objects.create(
            patient_name="张丽", doctor=self.other_doctor,
            visit_time=self.visit_time + timedelta(days=1), chief_complaint="腰痛",
            status=ReceptionRecord.Status.PENDING,
        )
        other = ReceptionRecord.objects.get(patient_name="张丽")
        self.action(other, "start")
        other.refresh_from_db()
        other.diagnosis = "腰肌劳损"
        other.treatment = "针灸治疗"
        other.save()
        self.action(other, "complete")
        response = self.client.get(reverse("receptions:list"), {
            "patient_name": "张", "doctor": "李明", "department": "中医内科", "status": "pending",
            "date_from": "2026-10-10", "date_to": "2026-10-10",
        })
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertContains(response, "张伟")
        self.assertNotContains(response, "张丽")
        completed = self.client.get(reverse("receptions:list"), {"status": "completed"})
        self.assertEqual(completed.context["page_obj"].paginator.count, 1)
        self.assertContains(completed, "张丽")

    def test_pagination_preserves_filters(self):
        for index in range(11):
            ReceptionRecord.objects.create(
                patient_name=f"演示患者{index}", doctor=self.doctor,
                visit_time=self.visit_time + timedelta(days=index + 1), chief_complaint="头晕",
            )
        response = self.client.get(reverse("receptions:list"), {"doctor": "李明"})
        self.assertEqual(len(response.context["page_obj"]), 10)
        self.assertContains(response, "doctor=%E6%9D%8E%E6%98%8E&amp;page=2")
        self.assertEqual(len(self.client.get(reverse("receptions:list"), {"doctor": "李明", "page": 2}).context["page_obj"]), 2)

    def test_delete_requires_post(self):
        url = reverse("receptions:delete", args=[self.record.pk])
        self.assertContains(self.client.get(url), "确认删除")
        self.assertTrue(ReceptionRecord.objects.filter(pk=self.record.pk).exists())
        response = self.client.post(url)
        self.assertRedirects(response, reverse("receptions:list"))
        self.assertFalse(ReceptionRecord.objects.filter(pk=self.record.pk).exists())

    def test_delete_linked_reception_restores_schedule_slot(self):
        schedule = self.create_schedule()
        self.client.post(reverse("receptions:add"), self.form_data(schedule=str(schedule.pk)))
        linked = ReceptionRecord.objects.get(patient_name="李娜")
        url = reverse("receptions:delete", args=[linked.pk])
        self.client.get(url)
        schedule.refresh_from_db()
        self.assertEqual(schedule.booked_patients, 1)
        self.assertRedirects(self.client.post(url), reverse("receptions:list"))
        schedule.refresh_from_db()
        self.assertEqual(schedule.booked_patients, 0)
        self.assertEqual(schedule.remaining_slots, 1)
