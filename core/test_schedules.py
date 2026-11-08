"""出诊排班验收测试；仅使用 Django 创建的隔离测试数据库。"""

from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from receptions.models import ReceptionRecord

from .models import Department, Doctor, Schedule


class ScheduleAcceptanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("schedule_tester", password="StrongPass765!", is_staff=True)
        self.client.force_login(self.user)
        self.department = Department.objects.create(name="中医内科")
        self.other_department = Department.objects.create(name="针灸科")
        self.doctor = Doctor.objects.create(name="李医师", department=self.department)
        self.other_doctor = Doctor.objects.create(name="王医师", department=self.other_department)
        self.day = date(2026, 11, 12)

    def form_data(self, **overrides):
        data = {
            "doctor": str(self.doctor.pk),
            "schedule_date": self.day.isoformat(),
            "start_time": "09:00",
            "end_time": "12:00",
            "max_patients": "2",
            "location": "一诊室",
            "status": Schedule.Status.NORMAL,
            "remark": "上午门诊",
        }
        data.update(overrides)
        return data

    def make_schedule(self, **overrides):
        values = {
            "doctor": self.doctor,
            "schedule_date": self.day,
            "start_time": time(9),
            "end_time": time(12),
            "max_patients": 2,
            "location": "一诊室",
        }
        values.update(overrides)
        return Schedule.objects.create(**values)

    def make_reception(self, schedule, name, *, status=ReceptionRecord.Status.PENDING):
        return ReceptionRecord.objects.create(
            patient_name=name,
            doctor=schedule.doctor,
            schedule=schedule,
            visit_time=timezone.make_aware(datetime.combine(schedule.schedule_date, time(9, 30))),
            chief_complaint="头痛",
            status=status,
        )

    def test_add_persists_fields_and_opens_detail(self):
        self.assertEqual(self.client.get(reverse("schedules:add")).status_code, 200)
        response = self.client.post(reverse("schedules:add"), self.form_data())
        self.assertRedirects(response, reverse("schedules:list"))
        schedule = Schedule.objects.get()
        self.assertEqual((schedule.doctor, schedule.department), (self.doctor, self.department))
        self.assertEqual((schedule.schedule_date, schedule.start_time, schedule.end_time), (self.day, time(9), time(12)))
        self.assertEqual((schedule.max_patients, schedule.booked_patients, schedule.location), (2, 0, "一诊室"))
        detail = self.client.get(reverse("schedules:detail", args=[schedule.pk]))
        self.assertContains(detail, "上午门诊")
        self.assertContains(detail, "剩余名额")
        self.assertContains(detail, "<strong>2</strong>", html=True)

    def test_edit_updates_schedule_without_creating_another(self):
        schedule = self.make_schedule()
        url = reverse("schedules:edit", args=[schedule.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, self.form_data(end_time="11:30", max_patients="3", location="二诊室"))
        self.assertRedirects(response, reverse("schedules:list"))
        schedule.refresh_from_db()
        self.assertEqual((schedule.end_time, schedule.max_patients, schedule.location), (time(11, 30), 3, "二诊室"))
        self.assertEqual(Schedule.objects.count(), 1)

    def test_delete_requires_post_and_unlinks_receptions(self):
        schedule = self.make_schedule()
        reception = self.make_reception(schedule, "患者甲")
        url = reverse("schedules:delete", args=[schedule.pk])
        self.assertContains(self.client.get(url), "确认删除")
        self.assertTrue(Schedule.objects.filter(pk=schedule.pk).exists())
        response = self.client.post(url)
        self.assertRedirects(response, reverse("schedules:list"))
        self.assertFalse(Schedule.objects.filter(pk=schedule.pk).exists())
        reception.refresh_from_db()
        self.assertIsNone(reception.schedule_id)

    def test_combined_filters_return_only_matching_schedule(self):
        target = self.make_schedule()
        self.make_schedule(doctor=self.other_doctor)
        self.make_schedule(schedule_date=self.day + timedelta(days=1))
        self.make_schedule(start_time=time(13), end_time=time(16), status=Schedule.Status.SUSPENDED)
        response = self.client.get(reverse("schedules:list"), {
            "doctor": self.doctor.pk,
            "department": self.department.pk,
            "schedule_date": self.day.isoformat(),
            "status": Schedule.Status.NORMAL,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertEqual([item.pk for item in response.context["items"]], [target.pk])

    def test_pagination_preserves_combined_filters(self):
        for offset in range(12):
            self.make_schedule(schedule_date=self.day + timedelta(days=offset))
        self.make_schedule(doctor=self.other_doctor)
        filters = {"doctor": self.doctor.pk, "department": self.department.pk, "status": Schedule.Status.NORMAL}
        first = self.client.get(reverse("schedules:list"), filters)
        self.assertEqual(first.context["page_obj"].paginator.count, 12)
        self.assertEqual(len(first.context["items"]), 10)
        self.assertContains(first, f"doctor={self.doctor.pk}&amp;department={self.department.pk}&amp;status=normal&amp;page=2")
        second = self.client.get(reverse("schedules:list"), {**filters, "page": 2})
        self.assertEqual(len(second.context["items"]), 2)
        self.assertEqual(second.context["page_obj"].number, 2)

    def test_overlapping_normal_schedule_rejected_but_adjacent_allowed(self):
        self.make_schedule()
        overlap = self.client.post(reverse("schedules:add"), self.form_data(start_time="11:00", end_time="13:00"))
        self.assertEqual(overlap.status_code, 200)
        self.assertContains(overlap, "该医师在此时段已有正常出诊排班")
        self.assertEqual(Schedule.objects.count(), 1)
        adjacent = self.client.post(reverse("schedules:add"), self.form_data(start_time="12:00", end_time="13:00"))
        self.assertRedirects(adjacent, reverse("schedules:list"))
        self.assertEqual(Schedule.objects.count(), 2)

    def test_conflict_is_scoped_to_doctor_and_normal_status(self):
        self.make_schedule()
        other_doctor = self.client.post(reverse("schedules:add"), self.form_data(doctor=str(self.other_doctor.pk)))
        suspended = self.client.post(reverse("schedules:add"), self.form_data(status=Schedule.Status.SUSPENDED))
        self.assertRedirects(other_doctor, reverse("schedules:list"))
        self.assertRedirects(suspended, reverse("schedules:list"))
        self.assertEqual(Schedule.objects.count(), 3)

    def test_invalid_time_and_edit_conflict_do_not_mutate_schedule(self):
        first = self.make_schedule()
        second = self.make_schedule(start_time=time(13), end_time=time(16))
        invalid = self.client.post(reverse("schedules:add"), self.form_data(start_time="12:00", end_time="12:00"))
        self.assertContains(invalid, "结束时间必须晚于开始时间")
        edit = self.client.post(reverse("schedules:edit", args=[second.pk]), self.form_data(start_time="11:00", end_time="14:00"))
        self.assertContains(edit, "该医师在此时段已有正常出诊排班")
        second.refresh_from_db()
        self.assertEqual((second.start_time, second.end_time), (time(13), time(16)))
        self.assertEqual(Schedule.objects.count(), 2)

    def test_capacity_and_detail_follow_reception_count(self):
        schedule = self.make_schedule()
        self.make_reception(schedule, "患者甲")
        self.make_reception(schedule, "患者乙")
        schedule.refresh_from_db()
        self.assertEqual((schedule.booked_patients, schedule.remaining_slots), (2, 0))
        detail = self.client.get(reverse("schedules:detail", args=[schedule.pk]))
        self.assertContains(detail, "患者甲")
        self.assertContains(detail, "患者乙")
        self.assertContains(detail, "剩余名额")
        self.assertContains(detail, "<strong>0</strong>", html=True)
        with self.assertRaisesMessage(ValidationError, "该排班已满号"):
            self.make_reception(schedule, "患者丙")
        self.assertEqual(ReceptionRecord.objects.count(), 2)

    def test_capacity_cannot_drop_below_active_receptions(self):
        schedule = self.make_schedule()
        self.make_reception(schedule, "患者甲")
        response = self.client.post(reverse("schedules:edit", args=[schedule.pk]), self.form_data(max_patients="0"))
        self.assertContains(response, "最大接诊人数不能少于已有的有效接诊人数")
        schedule.refresh_from_db()
        self.assertEqual(schedule.max_patients, 2)

    def test_cancel_delete_and_relink_update_both_schedules(self):
        first = self.make_schedule()
        second = self.make_schedule(start_time=time(9), end_time=time(12), schedule_date=self.day + timedelta(days=1))
        record = self.make_reception(first, "患者甲")
        first.refresh_from_db()
        self.assertEqual(first.booked_patients, 1)

        record.status = ReceptionRecord.Status.CANCELLED
        record.save()
        first.refresh_from_db()
        self.assertEqual(first.booked_patients, 0)

        record.visit_time = timezone.make_aware(datetime.combine(second.schedule_date, time(9, 30)))
        record.schedule = second
        record.status = ReceptionRecord.Status.PENDING
        # 状态机禁止取消后恢复，改用新的有效接诊验证排班转移。
        with self.assertRaises(ValidationError):
            record.save()
        moved = self.make_reception(first, "患者乙")
        moved.visit_time = timezone.make_aware(datetime.combine(second.schedule_date, time(9, 30)))
        moved.schedule = second
        moved.save()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.booked_patients, second.booked_patients), (0, 1))
        moved.delete()
        second.refresh_from_db()
        self.assertEqual(second.booked_patients, 0)

    def test_linked_reception_blocks_doctor_or_time_change(self):
        schedule = self.make_schedule()
        self.make_reception(schedule, "患者甲")
        url = reverse("schedules:edit", args=[schedule.pk])
        wrong_doctor = self.client.post(url, self.form_data(doctor=str(self.other_doctor.pk)))
        outside_time = self.client.post(url, self.form_data(start_time="10:00"))
        self.assertContains(wrong_doctor, "已有接诊记录，不能更换为其他医师")
        self.assertContains(outside_time, "已有接诊时间不在修改后的排班时段内")
        schedule.refresh_from_db()
        self.assertEqual((schedule.doctor, schedule.start_time), (self.doctor, time(9)))
