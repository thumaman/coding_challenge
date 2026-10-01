from django import forms

from .models import Employee


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "name",
            "position",
            "office",
            "start_date",
            "salary",
        ]

        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
        }
