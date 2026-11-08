from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import ActiveStatus, Department, Doctor, PerformanceRecord, Schedule


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(label="邮箱", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs.setdefault("class", css_class)


class DepartmentForm(StyledModelForm):
    class Meta:
        model = Department
        fields = ("name", "description", "status")


class DoctorForm(StyledModelForm):
    class Meta:
        model = Doctor
        fields = ("user", "name", "gender", "age", "phone", "department", "title", "specialty", "introduction", "status")


class ScheduleForm(StyledModelForm):
    class Meta:
        model = Schedule
        fields = ("doctor", "schedule_date", "start_time", "end_time", "max_patients", "location", "status", "remark")
        widgets = {
            "schedule_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "start_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "end_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
        }


class PerformanceRecordForm(StyledModelForm):
    class Meta:
        model = PerformanceRecord
        fields = (
            "doctor", "period_start", "period_end", "base_score", "reward_score",
            "deduction_score", "abnormal_remark", "attachment",
        )
        widgets = {
            "period_start": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "period_end": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }


class SearchForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs.setdefault("class", css_class)


class DepartmentSearchForm(SearchForm):
    name = forms.CharField(label="科室名称", max_length=100, required=False)
    status = forms.ChoiceField(label="状态", choices=[("", "全部状态"), *ActiveStatus.choices], required=False)


class DoctorSearchForm(SearchForm):
    name = forms.CharField(label="医师姓名", max_length=50, required=False)
    department = forms.ModelChoiceField(label="科室", queryset=Department.objects.all(), required=False, empty_label="全部科室")
    status = forms.ChoiceField(label="状态", choices=[("", "全部状态"), *ActiveStatus.choices], required=False)


class ScheduleSearchForm(SearchForm):
    doctor = forms.ModelChoiceField(label="医师", queryset=Doctor.objects.all(), required=False, empty_label="全部医师")
    department = forms.ModelChoiceField(label="科室", queryset=Department.objects.all(), required=False, empty_label="全部科室")
    schedule_date = forms.DateField(label="出诊日期", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    status = forms.ChoiceField(label="状态", choices=[("", "全部状态"), *Schedule.Status.choices], required=False)


class PerformanceSearchForm(SearchForm):
    doctor = forms.ModelChoiceField(label="医师", queryset=Doctor.objects.all(), required=False, empty_label="全部医师")
    status = forms.ChoiceField(label="状态", choices=[("", "全部状态"), *PerformanceRecord.Status.choices], required=False)
    period_start = forms.DateField(label="周期开始（起）", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    period_end = forms.DateField(label="周期结束（止）", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        data = super().clean()
        if data.get("period_start") and data.get("period_end") and data["period_start"] > data["period_end"]:
            self.add_error("period_end", "结束日期不能早于开始日期。")
        return data


class OperationLogSearchForm(SearchForm):
    user = forms.ModelChoiceField(label="用户", queryset=User.objects.all(), required=False, empty_label="全部用户")
    module = forms.CharField(label="模块", required=False, max_length=100)
    operation_type = forms.CharField(label="操作类型", required=False, max_length=50)
    date_from = forms.DateField(label="开始日期", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(label="结束日期", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        data = super().clean()
        if data.get("date_from") and data.get("date_to") and data["date_from"] > data["date_to"]:
            self.add_error("date_to", "结束日期不能早于开始日期。")
        return data


class CrawledDataSearchForm(SearchForm):
    keyword = forms.CharField(label="标题关键词", required=False, max_length=100)
    category = forms.CharField(label="分类", required=False, max_length=50)
    source_name = forms.CharField(label="来源", required=False, max_length=100)
