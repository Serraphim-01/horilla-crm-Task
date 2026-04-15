"""
horilla_mail Mailjet mail views
"""

# Standard library imports
import logging
from functools import cached_property

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.views.generic import FormView, TemplateView

# First-party / Horilla imports
from horilla.http import HttpResponse
from horilla.urls import reverse_lazy
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _
from horilla_generics.views import (
    HorillaListView,
    HorillaNavView,
    HorillaSingleDeleteView,
    HorillaSingleFormView,
    HorillaView,
)
from horilla_mail.filters import HorillaMailServerFilter
from horilla_mail.forms import DynamicMailTestForm, MailjetMailConfigurationForm
from horilla_mail.models import HorillaMailConfiguration

logger = logging.getLogger(__name__)


@method_decorator(
    permission_required_or_denied(["horilla_mail.view_horillamailconfiguration"]),
    name="dispatch",
)
class MailjetMailServerView(LoginRequiredMixin, HorillaView):
    """
    TemplateView for Mailjet mail server page.
    """

    template_name = "mailjet/mailjet_server_view.html"
    nav_url = reverse_lazy("horilla_mail:mailjet_mail_server_navbar_view")
    list_url = reverse_lazy("horilla_mail:mailjet_mail_server_list_view")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(["horilla_mail.view_horillamailconfiguration"]),
    name="dispatch",
)
class MailjetMailServerNavbar(LoginRequiredMixin, HorillaNavView):
    """
    Navbar view for Mailjet mail server (Outgoing Mail Server)
    """

    nav_title = _("Outgoing Mail Configurations")
    search_url = reverse_lazy("horilla_mail:mailjet_mail_server_list_view")
    main_url = reverse_lazy("horilla_mail:mailjet_mail_server_view")
    nav_width = False
    gap_enabled = False
    all_view_types = False
    one_view_only = True
    filter_option = False
    reload_option = False
    border_enabled = False

    @cached_property
    def new_button(self):
        """Return new button configuration if user has permission"""
        if self.request.user.has_perm("horilla_mail.create_horillaemailconfiguration"):
            return {
                "url": f"""{ reverse_lazy('horilla_mail:mailjet_mail_server_form_view')}?new=true""",
                "attrs": {"id": "mailjet-server-create"},
                "onclick": "openhorillaModal()",
                "target": "#horillaModalBox",
            }
        return None


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(["horilla_mail.view_horillamailconfiguration"]),
    name="dispatch",
)
class MailjetMailServerListView(LoginRequiredMixin, HorillaListView):
    """
    List view of outgoing mail server configurations (Mailjet)
    """

    model = HorillaMailConfiguration
    view_id = "mailjet-server-list"
    search_url = reverse_lazy("horilla_mail:mailjet_mail_server_list_view")
    main_url = reverse_lazy("horilla_mail:mailjet_mail_server_view")
    filterset_class = HorillaMailServerFilter
    bulk_update_two_column = True
    table_width = False
    bulk_delete_enabled = False
    table_height_as_class = "h-[500px]"
    bulk_select_option = False
    list_column_visibility = False
    action_method = "custom_actions"

    columns = ["get_email_identifier", "type"]

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(type="mailjet", mail_channel="outgoing")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        [
            "horilla_mail.view_horillamailconfiguration",
            "horilla_mail.add_horillamailconfiguration",
        ]
    ),
    name="dispatch",
)
class MailjetMailServerFormView(LoginRequiredMixin, HorillaSingleFormView):
    """
    Create and update form view for Mailjet mail server (Outgoing Mail Server)
    """

    model = HorillaMailConfiguration
    form_class = MailjetMailConfigurationForm
    form_title = "Outgoing Mail Server Configuration"
    modal_height = False
    hidden_fields = ["company", "type", "mail_channel"]
    save_and_new = False

    def get_initial(self):
        """Set initial form data for Mailjet mail configuration."""
        initial = super().get_initial()
        pk = self.kwargs.get("pk")
        company = getattr(self.request, "active_company", None)
        if not pk:
            initial["company"] = company
            initial["type"] = "mailjet"
            initial["mail_channel"] = "outgoing"
        return initial

    @cached_property
    def form_url(self):
        """URL for form submission"""
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy(
                "horilla_mail:mailjet_mail_server_update_view", kwargs={"pk": pk}
            )
        return reverse_lazy("horilla_mail:mailjet_mail_server_form_view")

    def form_valid(self, form):
        super().form_valid(form)
        return HttpResponse(
            "<script>$('#reloadButton').click();closeModal();closehorillaModal();</script>"
        )


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        [
            "horilla_mail.view_horillamailconfiguration",
            "horilla_mail.add_horillamailconfiguration",
        ]
    ),
    name="dispatch",
)
class MailjetMailServerTestEmailView(LoginRequiredMixin, FormView):
    """
    View to send test email from Mailjet mail server configuration
    """

    template_name = "mailjet/mailjet_test_email.html"
    form_class = DynamicMailTestForm

    def get_html_content(self, company):
        """Generate HTML email content from template"""
        user = self.request.user.get_full_name()
        button_url = f"{self.request.scheme}://{self.request.get_host()}"

        context = {
            "user": user,
            "company": company,
            "button_url": button_url,
        }

        html_content = render_to_string("mail_server_success.html", context)
        return html_content

    def send_test_email(self, form):
        """Send the test email using Mailjet API"""
        import requests
        import base64
        
        email_to = form.cleaned_data["to_email"]
        company = self.request.active_company
        subject = f"Test mail from {company} (Mailjet)"

        html_content = self.get_html_content(company)
        text_content = strip_tags(html_content)

        # Get the Mailjet configuration
        instance_id = self.request.GET.get("instance_id")
        try:
            config = HorillaMailConfiguration.objects.get(pk=instance_id, type="mailjet")
        except HorillaMailConfiguration.DoesNotExist:
            logger.error(f"Mailjet configuration not found: {instance_id}")
            return False, "Mailjet configuration not found"

        api_key = config.mailjet_api_key
        secret_key = config.get_decrypted_mailjet_secret_key()

        if not api_key or not secret_key:
            logger.error("Mailjet API credentials not configured")
            return False, "Mailjet API credentials not configured"

        try:
            # Log email configuration for debugging
            logger.info(f"Sending test email via Mailjet to {email_to}")
            logger.info(f"From Email: {config.from_email}")
            logger.info(f"Display Name: {config.display_name}")
            
            # Mailjet API endpoint
            url = "https://api.mailjet.com/v3.1/send"
            
            # Prepare the payload
            payload = {
                "Messages": [
                    {
                        "From": {
                            "Email": config.from_email,
                            "Name": config.display_name or company.name
                        },
                        "To": [
                            {
                                "Email": email_to,
                                "Name": email_to
                            }
                        ],
                        "Subject": subject,
                        "TextPart": text_content,
                        "HTMLPart": html_content,
                    }
                ]
            }

            # Make the API request
            response = requests.post(
                url,
                json=payload,
                auth=(api_key, secret_key),
                timeout=30
            )

            logger.info(f"Mailjet API Response Status: {response.status_code}")
            logger.info(f"Mailjet API Response: {response.text}")

            if response.status_code == 200:
                return True, None
            else:
                error_data = response.json()
                error_message = error_data.get("Messages", [{}])[0].get(
                    "Errors", [{}]
                )[0].get("ErrorMessage", "Unknown error")
                return False, error_message

        except Exception as e:
            logger.error(f"Failed to send test email via Mailjet: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False, str(e)

    def form_valid(self, form):
        """Handle valid form submission"""
        success, error = self.send_test_email(form)

        if success:
            messages.success(self.request, _("Mail sent successfully via Mailjet"))
        else:
            messages.error(self.request, f"{_('Something went wrong:')} {error}")

        return HttpResponse("<script>closeModal();$('#reloadButton').click();</script>")

    def get_context_data(self, **kwargs):
        """Add instance_id to context"""
        context = super().get_context_data(**kwargs)
        context["instance_id"] = self.request.GET.get("instance_id")
        return context


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        "horilla_mail.delete_horillamailconfiguration", modal=True
    ),
    name="dispatch",
)
class MailjetMailServerDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """
    Delete view for Mailjet mail server configuration
    """

    model = HorillaMailConfiguration

    def get_post_delete_response(self):
        return HttpResponse("<script>$('#reloadButton').click();</script>")
