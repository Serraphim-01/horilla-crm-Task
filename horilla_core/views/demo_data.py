"""Views for generating demo data and cleaning up companies."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from horilla_core.models import Company, DemoDataRecord
from horilla_core.tasks import generate_demo_data_task


class GenerateDemoDataView(LoginRequiredMixin, View):
    """Generate demo CRM data from existing users."""

    success_url = reverse_lazy("horilla_core:company_information")

    def post(self, request):
        if not request.user.is_superuser:
            messages.error(request, _("You do not have permission to perform this action."))
            return redirect(self.success_url)

        company = getattr(request, "active_company", None)
        if not company:
            company = request.user.company
        if not company:
            messages.error(request, _("No active company found."))
            return redirect(self.success_url)

        generate_demo_data_task.delay(company.pk)
        messages.success(
            request,
            _("Demo data generation has been started in the background. It may take a few moments to complete."),
        )

        return redirect(self.success_url)


class ClearDemoDataView(LoginRequiredMixin, View):
    """Delete all previously generated demo data for the current company."""

    success_url = reverse_lazy("horilla_core:company_information")

    def post(self, request):
        if not request.user.is_superuser:
            messages.error(request, _("You do not have permission to perform this action."))
            return redirect(self.success_url)

        company = getattr(request, "active_company", None)
        if not company:
            company = request.user.company
        if not company:
            messages.error(request, _("No active company found."))
            return redirect(self.success_url)

        records = DemoDataRecord.objects.filter(company=company).select_related(
            "content_type"
        )

        if not records.exists():
            messages.info(request, _("No demo data found to clear."))
            return redirect(self.success_url)

        count = records.count()
        deleted_objects = 0
        with transaction.atomic():
            for record in records:
                model_class = record.content_type.model_class()
                if model_class:
                    deleted, _ = model_class.objects.filter(pk=record.object_id).delete()
                    deleted_objects += deleted
            deleted_records = records.delete()

        messages.success(
            request,
            _("Cleared {count} demo data records ({deleted} objects deleted).").format(
                count=count, deleted=deleted_objects
            ),
        )
        return redirect(self.success_url)


class CleanupCompaniesView(LoginRequiredMixin, View):
    """Delete all non-base (non-HQ) companies from the database."""

    success_url = reverse_lazy("horilla_core:company_information")

    def post(self, request):
        if not request.user.is_superuser:
            messages.error(request, _("You do not have permission to perform this action."))
            return redirect(self.success_url)

        hq_companies = Company.objects.filter(hq=True)
        if not hq_companies.exists():
            messages.error(request, _("No base (HQ) company found. Nothing to clean up."))
            return redirect(self.success_url)

        hq_company = hq_companies.first()
        non_hq = Company.objects.filter(hq=False)

        if not non_hq.exists():
            messages.info(request, _("No non-base companies to clean up."))
            return redirect(self.success_url)

        count = non_hq.count()
        names = list(non_hq.values_list("name", flat=True))
        try:
            non_hq.delete()
            messages.success(
                request,
                _("Deleted {count} non-base compan{'y' if count == 1 else 'ies'}: {names}").format(
                    count=count,
                    names=", ".join(names),
                ),
            )
        except Exception as e:
            messages.error(request, _("Error deleting companies: {}").format(str(e)))

        return redirect(self.success_url)
