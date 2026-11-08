from django import forms

from .models import ReceptionRecord


class ReceptionRecordForm(forms.ModelForm):
    visit_time = forms.SplitDateTimeField(
        label="接诊时间",
        input_date_formats=["%Y-%m-%d"],
        input_time_formats=["%H:%M", "%H:%M:%S"],
        widget=forms.SplitDateTimeWidget(
            date_attrs={"type": "date", "class": "form-control"},
            time_attrs={"type": "time", "class": "form-control"},
            date_format="%Y-%m-%d",
            time_format="%H:%M",
        ),
    )

    class Meta:
        model = ReceptionRecord
        fields = [
            "patient_name", "patient_gender", "patient_age", "patient_phone", "doctor", "schedule",
            "visit_time", "chief_complaint", "symptoms", "diagnosis", "treatment",
            "prescription", "remark",
        ]
        widgets = {
            "patient_name": forms.TextInput(attrs={"class": "form-control"}),
            "patient_gender": forms.Select(attrs={"class": "form-select"}),
            "patient_age": forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 120}),
            "patient_phone": forms.TextInput(attrs={"class": "form-control"}),
            "doctor": forms.Select(attrs={"class": "form-select"}),
            "schedule": forms.Select(attrs={"class": "form-select"}),
            "chief_complaint": forms.TextInput(attrs={"class": "form-control"}),
            "symptoms": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "diagnosis": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "treatment": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "prescription": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "remark": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def clean_patient_age(self):
        age = self.cleaned_data.get("patient_age")
        if age is not None and age > 120:
            raise forms.ValidationError("患者年龄不能超过 120 岁。")
        return age

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["schedule"].help_text = "可留空。选择排班时，医师和接诊时间必须与排班一致。"


class ReceptionSearchForm(forms.Form):
    patient_name = forms.CharField(label="患者姓名", required=False, max_length=50)
    doctor = forms.CharField(label="接诊医师", required=False, max_length=50)
    department = forms.CharField(label="科室", required=False, max_length=50)
    status = forms.ChoiceField(
        label="接诊状态", required=False,
        choices=[("", "全部状态"), *ReceptionRecord.Status.choices],
    )
    date_from = forms.DateField(label="开始日期", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(label="结束日期", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("date_from"), cleaned.get("date_to")
        if start and end and start > end:
            self.add_error("date_to", "结束日期不能早于开始日期。")
        return cleaned
