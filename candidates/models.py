from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import DraftBase
from pricing import constants as C
from pricing.engine import PricingInput, calculate
from pricing.travel import route_distance_km


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

    # Personal
    first_name = models.CharField(_("first name"), max_length=100)
    last_name = models.CharField(_("last name"), max_length=100)
    email = models.EmailField(_("email"), blank=True)
    phone = models.CharField(_("phone"), max_length=30, blank=True)
    city = models.CharField(_("home location"), max_length=150, blank=True,
                            help_text=_("City, postcode or address, used to calculate travel distance"))
    desired_role = models.CharField(_("desired role"), max_length=150, blank=True)
    status = models.CharField(_("status"), max_length=20, choices=Status.choices, default=Status.INTAKE)

    # Salary & hours
    expected_salary_month = models.DecimalField(_("desired gross salary / month (€)"), max_digits=8, decimal_places=2)
    hours_per_week = models.PositiveSmallIntegerField(
        _("desired hours per week"), default=40, validators=[MinValueValidator(1), MaxValueValidator(60)]
    )

    # Travel: distance and who pays it depend on the vacancy, so they live on CandidateVacancy
    transport_type = models.CharField(_("travel means"), max_length=10, choices=Transport.choices, default=Transport.CAR)
    remote_days_per_week = models.PositiveSmallIntegerField(
        _("remote days / week"), default=0, validators=[MaxValueValidator(5)],
        help_text=_("Used for matching only"),
    )

    # Pricing (vacation days and other employment conditions are included in the cost price factor)
    cost_factor = models.DecimalField(_("cost price factor"), max_digits=4, decimal_places=2, default=Decimal("2.00"))
    margin_per_hour = models.DecimalField(
        _("margin / hour (€)"), max_digits=6, decimal_places=2, default=Decimal("10.00"),
        validators=[MinValueValidator(C.MIN_MARGIN), MaxValueValidator(C.MAX_MARGIN)],
    )

    vacancies = models.ManyToManyField(
        "clients.Vacancy", through="CandidateVacancy", related_name="candidates", verbose_name=_("vacancies"),
    )
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # pricing.engine.PricingInput field -> model field (used by the AI advisor to apply tweaks).
    # Travel distance and who pays it are stored per vacancy, on CandidateVacancy.
    PRICING_FIELD_MAP = {
        "salary_month": "expected_salary_month",
        "hours_per_week": "hours_per_week",
        "cost_factor": "cost_factor",
        "margin": "margin_per_hour",
        "transport_type": "transport_type",
    }
    LINK_PRICING_FIELD_MAP = {
        "travel_distance_km": "travel_distance_km",
        "client_pays_travel": "client_pays_travel",
    }

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("candidate")
        verbose_name_plural = _("candidates")

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def pricing_input(self, link=None, vacancy=None, **overrides) -> PricingInput:
        """Build the engine input for this candidate at a vacancy; overrides use PricingInput field names.

        With a link (CandidateVacancy) its travel distance, travel toggle and proposed tariff are used. For a
        vacancy the candidate isn't linked to (matching), the vacancy's travel default applies and travel is unknown.
        """
        vacancy = link.vacancy if link else vacancy
        data = {engine: getattr(self, model) for engine, model in self.PRICING_FIELD_MAP.items()}
        if link:
            data.update({engine: getattr(link, model) for engine, model in self.LINK_PRICING_FIELD_MAP.items()})
        else:
            data["client_pays_travel"] = bool(vacancy and vacancy.client_pays_travel)
        data.update(
            max_rate=vacancy.max_rate_per_hour if vacancy else None,
            proposed_rate=link.proposed_rate if link else None,
        )
        data.update(overrides)
        return PricingInput(**data)

    def link_for(self, vacancy):
        """This candidate's CandidateVacancy for `vacancy` (uses prefetched links when available)."""
        return next((link for link in self.links.all() if link.vacancy_id == vacancy.pk), None)

    def pricing_for(self, vacancy):
        link = self.link_for(vacancy)
        return link.pricing if link else calculate(self.pricing_input(vacancy=vacancy))

    def distance_to(self, vacancy):
        """One-way km to the vacancy: the stored distance when linked, otherwise looked up (cached)."""
        link = self.link_for(vacancy)
        if link and link.travel_distance_km is not None:
            return link.travel_distance_km
        if self.city and vacancy.location:
            result = route_distance_km(self.city, vacancy.location)
            return result["km"] if result else None
        return None


class CandidateVacancy(models.Model):
    """A candidate considered for a vacancy. Holds everything about the pair that changes the tariff."""

    class Status(models.TextChoices):
        CONSIDERED = "considered", _("Considered")
        PROPOSED = "proposed", _("Proposed")
        PLACED = "placed", _("Placed")
        REJECTED = "rejected", _("Rejected")

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="links")
    vacancy = models.ForeignKey(
        "clients.Vacancy", on_delete=models.CASCADE, related_name="candidate_links", verbose_name=_("vacancy"),
    )
    status = models.CharField(_("status"), max_length=20, choices=Status.choices, default=Status.CONSIDERED)
    # Travel only counts in the price when the distance is known (business rule)
    travel_distance_km = models.DecimalField(
        _("travel distance one way (km)"), max_digits=6, decimal_places=1, null=True, blank=True,
        help_text=_("Calculated automatically from the home location and the vacancy location"),
    )
    client_pays_travel = models.BooleanField(
        _("client pays travel costs"), default=False,
        help_text=_("Travel costs are then left out of the tariff (defaults to the vacancy's setting)"),
    )
    proposed_rate = models.DecimalField(
        _("proposed tariff / hour (€)"), max_digits=7, decimal_places=2, null=True, blank=True,
        help_text=_("Leave empty to use the advised tariff."),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [models.UniqueConstraint(fields=["candidate", "vacancy"], name="unique_candidate_vacancy")]
        verbose_name = _("candidate vacancy")
        verbose_name_plural = _("candidate vacancies")

    def __str__(self):
        return f"{self.candidate} → {self.vacancy}"

    def refresh_travel_distance(self):
        """Recalculate the one-way distance home → vacancy location (keeps the old value if lookup fails)."""
        if not (self.candidate.city and self.vacancy.location):
            return
        result = route_distance_km(self.candidate.city, self.vacancy.location)
        if result:
            self.travel_distance_km = result["km"]

    @property
    def pricing(self):
        if not hasattr(self, "_pricing_cache"):
            self._pricing_cache = calculate(self.candidate.pricing_input(link=self))
        return self._pricing_cache

    def save(self, *args, **kwargs):
        self.__dict__.pop("_pricing_cache", None)
        if self._state.adding and self.travel_distance_km is None:
            self.refresh_travel_distance()
        super().save(*args, **kwargs)


class CandidateDraft(DraftBase):
    """An unfinished "new candidate" form. Kept apart from Candidate so drafts never enter the candidate pool."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="candidate_drafts")

    class Meta(DraftBase.Meta):
        verbose_name = _("candidate draft")
        verbose_name_plural = _("candidate drafts")

    @property
    def title(self):
        name = f"{self.data.get('first_name', '')} {self.data.get('last_name', '')}".strip()
        return name or str(_("Untitled draft"))

    @property
    def subtitle(self):
        return self.data.get("desired_role", "")
