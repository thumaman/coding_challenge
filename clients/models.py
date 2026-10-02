from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import DraftBase


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
    address = models.CharField(_("address / postcode"), max_length=200, blank=True,
                               help_text=_("Work location, used to calculate travel distance"))
    city = models.CharField(_("city"), max_length=100, blank=True)
    max_rate_per_hour = models.DecimalField(_("max client rate / hour (€)"), max_digits=7, decimal_places=2)
    hours_per_week = models.PositiveSmallIntegerField(_("hours per week"), default=40)
    remote_days_allowed = models.PositiveSmallIntegerField(_("remote days allowed"), default=0)
    min_salary = models.DecimalField(_("min salary / month (€)"), max_digits=8, decimal_places=2, null=True, blank=True)
    max_salary = models.DecimalField(_("max salary / month (€)"), max_digits=8, decimal_places=2, null=True, blank=True)
    skills = models.TextField(_("skills / keywords"), blank=True, help_text=_("Comma separated"))
    client_pays_travel = models.BooleanField(
        _("client pays travel costs"), default=False,
        help_text=_("Travel costs are then left out of the tariff"),
    )
    is_open = models.BooleanField(_("open"), default=True)

    class Meta:
        ordering = ["client__name", "title"]
        verbose_name = _("vacancy")
        verbose_name_plural = _("vacancies")

    def __str__(self):
        return f"{self.client.name} · {self.title}"

    @property
    def location(self):
        """Work location for the travel distance (address + city, falling back to the client's city)."""
        return ", ".join(part for part in (self.address, self.city or self.client.city) if part)


class VacancyDraft(DraftBase):
    """An unfinished "new vacancy" form (see core/drafts.py)."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vacancy_drafts")

    class Meta(DraftBase.Meta):
        verbose_name = _("vacancy draft")
        verbose_name_plural = _("vacancy drafts")

    @property
    def title(self):
        return self.data.get("title", "").strip() or str(_("Untitled draft"))

    @property
    def subtitle(self):
        client_id = str(self.data.get("client", ""))
        client = Client.objects.filter(pk=client_id).first() if client_id.isdigit() else None
        return client.name if client else ""
