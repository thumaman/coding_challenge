"""Drafts for full-page "new …" forms (candidates, vacancies). See core.models.DraftBase.

The page's form carries data-autosave (draft.js posts it while typing) and a hidden "draft" field with the
draft id. "Save as draft" submits with action=draft. Saving for real removes the draft; an invalid submit
keeps what was typed in the draft.
"""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import DeleteView

from .modals import ModalDeleteMixin


def form_data(post):
    """POST data worth keeping in a draft (single values, without the bookkeeping fields)."""
    return {k: v for k, v in post.items() if k not in ("csrfmiddlewaretoken", "draft", "action")}


def save_draft(request, model):
    """Create or update the current user's draft from the POSTed form (the id travels in the "draft" field)."""
    draft_id = request.POST.get("draft")
    draft = get_object_or_404(model, pk=draft_id, owner=request.user) if draft_id else model(owner=request.user)
    draft.data = form_data(request.POST)
    draft.save()
    return draft


class DraftCreateMixin:
    """For a CreateView: prefill from ?draft=<id>, "Save as draft", and delete the draft once saved."""

    draft_model = None
    draft_redirect_url = None  # where "Save as draft" goes (a URL name)

    def get_draft(self):
        draft_id = self.request.GET.get("draft") or self.request.POST.get("draft")
        if not draft_id:
            return None
        return get_object_or_404(self.draft_model, pk=draft_id, owner=self.request.user)

    def get_initial(self):
        draft = self.get_draft() if self.request.method == "GET" else None
        return {**super().get_initial(), **(draft.data if draft else {})}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["draft"] = getattr(self, "draft", None) or self.get_draft()
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "draft":
            save_draft(request, self.draft_model)
            messages.success(request, _("Draft saved."))
            return redirect(self.draft_redirect_url)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        draft = self.get_draft()
        response = super().form_valid(form)
        if draft and response.status_code == 302:  # saved for real (not re-rendered with errors)
            draft.delete()
        return response

    def form_invalid(self, form):
        self.draft = save_draft(self.request, self.draft_model)  # keep what was typed, even if the page is left now
        return super().form_invalid(form)


def draft_autosave_view(model):
    """Autosave endpoint for draft.js (fetch while typing, keepalive when the page is left)."""
    @require_POST
    def view(request):
        draft = save_draft(request, model)
        return JsonResponse({"ok": True, "id": draft.pk})
    return view


def draft_list_view(drafts_attr, **context):
    """Drafts modal (core/_drafts.html) with the current user's drafts from `request.user.<drafts_attr>`.

    `context`: heading, empty_text, continue_url (the create page) and delete_url_name.
    """
    def view(request):
        drafts = getattr(request.user, drafts_attr).all()
        return render(request, "core/_drafts.html", {"drafts": drafts, **context})
    return view


class DraftDeleteView(ModalDeleteMixin, DeleteView):
    """Subclass with `drafts_attr`, e.g. "candidate_drafts"."""

    drafts_attr = None
    modal_title = _("Delete draft")
    success_message = _("Draft deleted.")

    def get_queryset(self):
        return getattr(self.request.user, self.drafts_attr).all()
