"""创建可重复执行的中医馆演示接诊记录。"""

from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Department, Doctor
from receptions.models import ReceptionRecord


SAMPLES = [
    ("张伟", "male", 42, "李明医师", "中医内科", "失眠多梦，夜间易醒", "入睡困难两周，伴口干心烦", "心肾不交证", "建议规律作息，配合养心安神治疗", "酸枣仁汤加减", "completed"),
    ("李娜", "female", 36, "王晓医师", "针灸科", "腰痛反复发作", "久坐后腰部酸痛，活动受限", "腰肌劳损", "局部针灸治疗，避免久坐", "", "in_progress"),
    ("王强", "male", 51, "陈静医师", "中医内科", "胃部不适，食欲减退", "餐后腹胀，偶有嗳气", "脾胃虚弱证", "饮食清淡，健脾和胃", "六君子汤加减", "completed"),
    ("刘芳", "female", 29, "赵平医师", "推拿科", "颈肩疼痛", "伏案工作后颈肩僵硬", "", "", "", "pending"),
    ("陈晨", "female", 24, "李明医师", "康复科", "头晕乏力", "晨起头晕，精神欠佳", "气血不足证", "适量运动，调理饮食", "八珍汤加减", "completed"),
    ("周杰", "male", 47, "王晓医师", "针灸科", "膝关节疼痛", "上下楼时膝部疼痛", "膝痹病", "针灸配合功能锻炼", "", "completed"),
    ("吴敏", "female", 33, "陈静医师", "中医内科", "经常疲倦，睡眠欠佳", "近一月工作繁忙，易疲劳", "", "", "", "pending"),
    ("赵磊", "male", 58, "赵平医师", "推拿科", "肩背酸痛", "肩背肌肉紧张三日", "筋膜劳损", "推拿放松，热敷观察", "", "in_progress"),
    ("孙婷", "female", 40, "李明医师", "中医内科", "咳嗽咽干", "干咳五日，无发热", "肺燥咳嗽", "润肺止咳，多饮温水", "桑杏汤加减", "completed"),
    ("郑浩", "male", 31, "王晓医师", "针灸科", "手臂麻木", "预约后因个人原因取消", "", "", "", "cancelled"),
    ("何莉", "female", 62, "陈静医师", "康复科", "步行后腿部乏力", "步行约十分钟后双腿疲劳", "", "", "", "pending"),
    ("高鹏", "male", 27, "赵平医师", "推拿科", "运动后腰背紧绷", "运动后腰背肌肉紧张", "腰背部肌肉拉伤", "暂缓剧烈运动，推拿辅助恢复", "", "completed"),
]


class Command(BaseCommand):
    help = "创建 12 条中医馆接诊演示数据；重复执行不会重复插入。"

    def handle(self, *args, **options):
        created = 0
        base = datetime(2026, 10, 1, 9, 0)
        for index, sample in enumerate(SAMPLES):
            patient, gender, age, doctor, department, complaint, symptoms, diagnosis, treatment, prescription, status = sample
            visit_time = timezone.make_aware(base + timedelta(days=index, hours=index % 4))
            department_obj, _ = Department.objects.get_or_create(name=department)
            doctor_obj, _ = Doctor.objects.get_or_create(name=doctor, department=department_obj)
            _, is_created = ReceptionRecord.objects.get_or_create(
                patient_name=patient,
                visit_time=visit_time,
                defaults={
                    "patient_gender": gender, "patient_age": age, "doctor": doctor_obj,
                    "chief_complaint": complaint,
                    "symptoms": symptoms, "diagnosis": diagnosis,
                    "treatment": treatment, "prescription": prescription,
                    "status": status, "remark": "课堂演示数据",
                },
            )
            created += is_created
        self.stdout.write(self.style.SUCCESS(f"已新增 {created} 条接诊记录，现有演示记录共 {len(SAMPLES)} 条。"))
