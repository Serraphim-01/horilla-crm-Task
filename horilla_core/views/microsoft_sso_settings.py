"""
Microsoft SSO Settings Views

This module contains views for managing Microsoft SSO configuration settings.
"""

import logging

import requests
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from horilla.utils.translation import gettext_lazy as _
from horilla_core.forms import MicrosoftSSOSettingsForm
from horilla_core.models import Company, MicrosoftSSOSettings
from horilla_core.views.microsoft_sso import get_msal_app

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


class MicrosoftSSOSyncUsersView(LoginRequiredMixin, View):
    """
    View to sync Microsoft Entra ID users into the local user database.
    """

    success_url = reverse_lazy('horilla_core:microsoft_sso_settings')

    def post(self, request):
        if not request.user.is_superuser:
            messages.error(request, _('You do not have permission to perform this action.'))
            return redirect(self.success_url)

        msal_app, sso_settings = get_msal_app(request)
        if msal_app is None:
            messages.error(request, _('Microsoft SSO is not configured or enabled.'))
            return redirect(self.success_url)

        token_response = msal_app.acquire_token_for_client(
            scopes=['https://graph.microsoft.com/.default']
        )

        if 'access_token' not in token_response:
            error = token_response.get('error', _('Unable to acquire Microsoft Graph token.'))
            error_description = token_response.get('error_description', '')
            logger.error(
                f"Microsoft Graph token acquisition error: {error} - {error_description}"
            )
            messages.error(request, _('Failed to sync users from Azure AD. Check app permissions and credentials.'))
            return redirect(self.success_url)

        access_token = token_response['access_token']
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
        }
        url = 'https://graph.microsoft.com/v1.0/users'
        params = {
            '$select': 'displayName,mail,userPrincipalName,givenName,surname',
            '$top': '999',
        }

        created = 0
        updated = 0
        skipped = 0
        user_model = get_user_model()

        try:
            while url:
                response = requests.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                for graph_user in data.get('value', []):
                    email = graph_user.get('mail') or graph_user.get('userPrincipalName')
                    if not email:
                        skipped += 1
                        continue

                    if not sso_settings.is_domain_allowed(email):
                        skipped += 1
                        continue

                    first_name = graph_user.get('givenName') or ''
                    last_name = graph_user.get('surname') or ''
                    if not first_name and not last_name:
                        display_name = graph_user.get('displayName') or ''
                        parts = display_name.split(' ', 1)
                        first_name = parts[0] if parts else ''
                        last_name = parts[1] if len(parts) > 1 else ''

                    existing_user = user_model.objects.filter(email__iexact=email).first()
                    if existing_user:
                        updated_fields = []
                        if first_name and existing_user.first_name != first_name:
                            existing_user.first_name = first_name
                            updated_fields.append('first_name')
                        if last_name and existing_user.last_name != last_name:
                            existing_user.last_name = last_name
                            updated_fields.append('last_name')
                        if not existing_user.is_active:
                            existing_user.is_active = True
                            updated_fields.append('is_active')

                        if updated_fields:
                            existing_user.save(update_fields=updated_fields)
                            updated += 1
                        continue

                    username = email.split('@')[0]
                    base_username = username
                    suffix = 1
                    while user_model.objects.filter(username=username).exists():
                        username = f'{base_username}{suffix}'
                        suffix += 1

                    company = Company.objects.filter(hq=True).first() or Company.objects.first()
                    new_user = user_model.objects.create(
                        username=username,
                        email=email,
                        first_name=first_name,
                        last_name=last_name,
                        is_active=True,
                        company=company,
                        country='US',
                    )
                    new_user.set_unusable_password()
                    new_user.save()
                    created += 1

                url = data.get('@odata.nextLink')
                params = None

        except requests.RequestException as error:
            logger.error(f'Microsoft Graph sync failed: {error}', exc_info=True)
            messages.error(request, _('Failed to sync users from Azure AD. Please try again later.'))
            return redirect(self.success_url)
        except Exception as error:
            logger.error(f'Unexpected error syncing users from Azure AD: {error}', exc_info=True)
            messages.error(request, _('An unexpected error occurred while syncing users.'))
            return redirect(self.success_url)

        messages.success(
            request,
            _('Microsoft Azure AD sync completed: %(created)s created, %(updated)s updated, %(skipped)s skipped.') % {
                'created': created,
                'updated': updated,
                'skipped': skipped,
            },
        )
        return redirect(self.success_url)
