"""
Microsoft SSO Settings Views

This module contains views for managing Microsoft SSO configuration settings.
"""

import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from horilla.utils.translation import gettext_lazy as _
from horilla_core.forms import MicrosoftSSOSettingsForm
from horilla_core.models import MicrosoftSSOSettings

logger = logging.getLogger(__name__)


class MicrosoftSSOSettingsView(LoginRequiredMixin, View):
    """
    View for managing Microsoft SSO settings.
    Only accessible by admin/superuser.
    """

    template_name = 'microsoft_sso/settings.html'
    success_url = reverse_lazy('horilla_core:microsoft_sso_settings')

    def get(self, request):
        """
        Display the Microsoft SSO settings form.
        """
        # Check if user is admin/superuser
        if not request.user.is_superuser:
            messages.error(request, _('You do not have permission to access this page.'))
            return redirect('horilla_core:home_view')

        # Load or create settings instance
        settings_obj = MicrosoftSSOSettings.load()
        
        form = MicrosoftSSOSettingsForm(instance=settings_obj)
        
        context = {
            'form': form,
            'settings_obj': settings_obj,
            'page_title': _('Microsoft SSO Settings'),
        }
        
        return render(request, self.template_name, context)

    def post(self, request):
        """
        Save Microsoft SSO settings.
        """
        # Check if user is admin/superuser
        if not request.user.is_superuser:
            messages.error(request, _('You do not have permission to access this page.'))
            return redirect('horilla_core:home_view')

        # Load or create settings instance
        settings_obj = MicrosoftSSOSettings.load()
        
        form = MicrosoftSSOSettingsForm(request.POST, instance=settings_obj)
        
        if form.is_valid():
            try:
                form.save()
                messages.success(
                    request,
                    _('Microsoft SSO settings saved successfully.')
                )
                return redirect(self.success_url)
            except Exception as e:
                logger.error(f"Error saving Microsoft SSO settings: {str(e)}", exc_info=True)
                messages.error(
                    request,
                    _('An error occurred while saving settings. Please try again.')
                )
        else:
            messages.error(
                request,
                _('Please correct the errors below.')
            )
        
        context = {
            'form': form,
            'settings_obj': settings_obj,
            'page_title': _('Microsoft SSO Settings'),
        }
        
        return render(request, self.template_name, context)
