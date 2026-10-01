from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from pricing.engine import PricingInput, calculate

_UNSET = object()


class Candidate(models.Model):
    class Status(models.TextChoices):
        INTAKE = "intake", _("Intake")
        AVAILABLE = "available", _("Available")
        PROPOSED = "proposed", _("Proposed")
        PLACED = "placed", _("Placed")
        INACTIVE = "inactive", _("Inactive")

    class Transport(models.TextChoices):
        CAR = "car", _("Car")
        OV = "ov", _("Public transport")
        BIKE = "bike", _("Bike")
        NONE = "none", _("None / unknown")

    # Personal
    first_name = models.CharField(_("first name"), max_length=100)
    last_name = models.CharField(_("last name"), max_length=100)
    email = models.EmailField(_("email"), blank=True)
    phone = models.CharField(_("phone"), max_length=30, blank=True)
    city = models.CharField(_("city"), max_length=100, blank=True)
    desired_role = models.CharField(_("desired role"), max_length=150, blank=True)
    status = models.CharField(_("status"), max_length=20, choices=Status.choices, default=Status.INTAKE)

    # Salary & hours
    expected_salary_month = models.DecimalField(_("expected gross salary / month (€)"), max_digits=8, decimal_places=2)
    hours_per_week = models.PositiveSmallIntegerField(
        _("hours per week"), default=40, validators=[MinValueValidator(1), MaxValueValidator(60)]
    )

    # Travel & remote: travel only counts in the price when travel_known is True (business rule)
    travel_known = models.BooleanField(_("travel details known"), default=False)
    travel_distance_km = models.DecimalField(
        _("distance one way (km)"), max_digits=6, decimal_places=1, null=True, blank=True
    )
    transport_type = models.CharField(_("transport"), max_length=10, choices=Transport.choices, default=Transport.NONE)
    remote_days_per_week = models.PositiveSmallIntegerField(
        _("remote days / week"), default=0, validators=[MaxValueValidator(5)]
    )

    # Days off & benefits
    vacation_days = models.PositiveSmallIntegerField(_("vacation days / year"), default=25)
    sick_days_estimate = models.PositiveSmallIntegerField(_("expected sick days / year"), default=8)
    secondary_benefits_month = models.DecimalField(
        _("secondary benefits / month (€)"), max_digits=8, decimal_places=2, default=Decimal("0")
    )
    benefits_description = models.CharField(_("benefits description"), max_length=255, blank=True)

    # Pricing overrides
    cost_factor = models.DecimalField(_("cost factor"), max_digits=4, decimal_places=2, default=Decimal("2.00"))
    margin_per_hour = models.DecimalField(_("margin / hour (€)"), max_digits=6, decimal_places=2, default=Decimal("10.00"))
    proposed_rate = models.DecimalField(
        _("proposed rate / hour (€)"), max_digits=7, decimal_places=2, null=True, blank=True,
        help_text=_("Leave empty to use the advised rate."),
    )

    vacancy = models.ForeignKey(
        "clients.Vacancy", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="candidates", verbose_name=_("vacancy"),
    )
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # pricing.engine.PricingInput field -> Candidate model field (used by the AI advisor to apply tweaks)
    PRICING_FIELD_MAP = {
        "salary_month": "expected_salary_month",
        "hours_per_week": "hours_per_week",
        "cost_factor": "cost_factor",
        "margin": "margin_per_hour",
        "remote_days": "remote_days_per_week",
        "vacation_days": "vacation_days",
        "sick_days": "sick_days_estimate",
        "benefits_month": "secondary_benefits_month",
    }

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def pricing_input(self, vacancy=_UNSET, **overrides) -> PricingInput:
        """Build the engine input from this candidate; overrides use PricingInput field names."""
        vacancy = self.vacancy if vacancy is _UNSET else vacancy
        data = {engine: getattr(self, model) for engine, model in self.PRICING_FIELD_MAP.items()}
        data.update(
            travel_known=self.travel_known,
            travel_distance_km=self.travel_distance_km,
            transport_type=self.transport_type,
            max_rate=vacancy.max_rate_per_hour if vacancy else None,
            proposed_rate=self.proposed_rate,
        )
        data.update(overrides)
        return PricingInput(**data)

    def pricing_for(self, vacancy):
        return calculate(self.pricing_input(vacancy=vacancy))

    @property
    def pricing(self):
        if not hasattr(self, "_pricing_cache"):
            self._pricing_cache = calculate(self.pricing_input())
        return self._pricing_cache

    def save(self, *args, **kwargs):
        self.__dict__.pop("_pricing_cache", None)
        super().save(*args, **kwargs)
