"""Shared view mixins for the modal CRUD contract (see docs/PLAN.md, "Shared contracts").

GET  -> renders the modal partial (a <form class="modal-form">) that app.js puts into the <dialog>.
POST -> {"ok": true, "message": ...} on success, or {"ok": false, "html": ...} with the re-rendered form.

Usage:
    class CandidateCreateView(ModalFormMixin, CreateView):
        model = Candidate
        form_class = CandidateForm
        success_message = _("Candidate added.")
"""

from django.http import JsonResponse
from django.template.loader import render_to_string


class ModalFormMixin:
    template_name = "core/_modal_form.html"
    success_message = ""
    modal_title = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["modal_title"] = self.modal_title
        context["form_action"] = self.request.path
        return context

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({"ok": True, "message": str(self.success_message), "id": self.object.pk})

    def form_invalid(self, form):
        html = render_to_string(self.template_name, self.get_context_data(form=form), request=self.request)
        return JsonResponse({"ok": False, "html": html})


class ModalDeleteMixin:
    template_name = "core/_confirm_delete.html"
    success_message = ""
    modal_title = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["modal_title"] = self.modal_title
        context["form_action"] = self.request.path
        return context

    def form_valid(self, form):
        self.object.delete()
        return JsonResponse({"ok": True, "message": str(self.success_message)})
