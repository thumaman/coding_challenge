from django.db import models
from django.utils.translation import gettext_lazy as _


class Client(models.Model):
    """A client company ("opdrachtgever")."""

    name = models.CharField(_("name"), max_length=200)
    industry = models.CharField(_("industry"), max_length=100, blank=True)
    city = models.CharField(_("city"), max_length=100, blank=True)
    contact_name = models.CharField(_("contact name"), max_length=150, blank=True)
    contact_email = models.EmailField(_("contact email"), blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Vacancy(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="vacancies", verbose_name=_("client"))
    title = models.CharField(_("title"), max_length=200)
    city = models.CharField(_("city"), max_length=100, blank=True)
    max_rate_per_hour = models.DecimalField(_("max client rate / hour (€)"), max_digits=7, decimal_places=2)
    hours_per_week = models.PositiveSmallIntegerField(_("hours per week"), default=40)
    remote_days_allowed = models.PositiveSmallIntegerField(_("remote days allowed"), default=0)
    min_salary = models.DecimalField(_("min salary / month (€)"), max_digits=8, decimal_places=2, null=True, blank=True)
    max_salary = models.DecimalField(_("max salary / month (€)"), max_digits=8, decimal_places=2, null=True, blank=True)
    skills = models.TextField(_("skills / keywords"), blank=True, help_text=_("Comma separated"))
    is_open = models.BooleanField(_("open"), default=True)

    class Meta:
        ordering = ["client__name", "title"]
        verbose_name_plural = "vacancies"

    def __str__(self):
        return f"{self.client.name} · {self.title}"
