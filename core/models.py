from django.db import models
from django.utils.translation import gettext_lazy as _


class DraftBase(models.Model):
    """An unfinished "new …" form (see core/drafts.py). Subclasses add `owner` with their own related_name."""

    data = models.JSONField(default=dict)  # raw form values: {field name: value}
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    @property
    def title(self):
        return str(_("Untitled draft"))

    @property
    def subtitle(self):
        return ""
