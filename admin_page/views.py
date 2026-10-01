from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .forms import EmployeeForm
from .models import Employee


def employee_list(request):
    employees = Employee.objects.all()

    return render(
        request,
        "employees/employee_list.html",
        {"employees": employees},
    )


def employee_create(request):
    if request.method == "POST":
        form = EmployeeForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect("admin_page:employee_list")
    else:
        form = EmployeeForm()

    return render(
        request,
        "employees/employee_form.html",
        {
            "form": form,
            "title": _("Add employee"),
        },
    )


def employee_update(request, pk):
    employee = get_object_or_404(Employee, pk=pk)

    if request.method == "POST":
        form = EmployeeForm(request.POST, instance=employee)

        if form.is_valid():
            form.save()
            return redirect("admin_page:employee_list")
    else:
        form = EmployeeForm(instance=employee)

    return render(
        request,
        "employees/employee_form.html",
        {
            "form": form,
            "title": _("Edit employee"),
        },
    )


def employee_delete(request, pk):
    employee = get_object_or_404(Employee, pk=pk)

    if request.method == "POST":
        employee.delete()

    return redirect("admin_page:employee_list")
