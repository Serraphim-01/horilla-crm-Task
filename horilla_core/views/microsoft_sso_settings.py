"""
Microsoft SSO Settings Views

This module contains views for managing Microsoft SSO configuration settings.
"""

import logging

import pycountry
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from horilla.utils.translation import gettext_lazy as _
from horilla_core.forms import MicrosoftSSOSettingsForm
from horilla_core.models import Company, Department, MicrosoftSSOSettings, Role


def _normalize_country(country_value):
    if not country_value:
        return None

    clean_value = country_value.strip()
    if not clean_value:
        return None

    if len(clean_value) == 2:
        try:
            country = pycountry.countries.get(alpha_2=clean_value.upper())
            return country.alpha_2 if country else None
        except (LookupError, AttributeError):
            return None

    try:
        countries = pycountry.countries.search_fuzzy(clean_value)
        if countries:
            return countries[0].alpha_2
    except LookupError:
        pass

    try:
        country = pycountry.countries.get(name=clean_value)
        return country.alpha_2 if country else None
    except (LookupError, AttributeError):
        return None


def _normalize_language(language_value):
    if not language_value:
        return None

    normalized = language_value.strip().lower()
    if not normalized:
        return None

    # Try exact matching against settings.LANGUAGES codes and labels
    for code, name in settings.LANGUAGES:
        if normalized == code.lower() or normalized == name.lower():
            return code

    # Match language code prefix, e.g. en-US -> en
    if '-' in normalized:
        prefix = normalized.split('-', 1)[0]
        for code, name in settings.LANGUAGES:
            if prefix == code.lower():
                return code

    # Match name or partial label
    for code, name in settings.LANGUAGES:
        if normalized in name.lower() or name.lower() in normalized:
            return code

    return None


def _extract_primary_business_phone(graph_user):
    phones = graph_user.get('businessPhones') or []
    if isinstance(phones, list) and phones:
        return phones[0]
    if isinstance(phones, str) and phones.strip():
        return phones.strip()
    return None


def _get_or_create_department(company, department_name):
    if not department_name:
        return None
    department_name = department_name.strip()
    if not department_name:
        return None
    department, _ = Department.objects.get_or_create(
        company=company, department_name=department_name
    )
    return department


def _get_or_create_role(role_name):
    if not role_name:
        return None
    role_name = role_name.strip()
    if not role_name:
        return None
    role, _ = Role.objects.get_or_create(role_name=role_name)
    return role


def _ensure_company_persisted(sso_settings, company):
    """Persist the company back to MicrosoftSSOSettings so it's saved for future runs."""
    if sso_settings.company_id != company.id:
        sso_settings.company = company
        sso_settings.save()


def _migrate_all_users_to_company(company):
    """Move every existing user to the given company."""
    user_model = get_user_model()
    updated = user_model.objects.filter(~models.Q(company=company)).update(company=company)
    if updated:
        logger.info("Migrated %d existing users to company: %s", updated, company)
    return updated


def _consolidate_companies(target_company):
    """
    Merge duplicate companies created by the old domain-based sync logic.

    Finds companies whose name matches case-insensitively (the old sync could
    create "Contoso" from companyName and "Contoso" from email domain, etc.).
    Users are moved to the target company, and the duplicates are deleted.
    """
    user_model = get_user_model()
    duplicates = Company.objects.filter(
        name__iexact=target_company.name
    ).exclude(pk=target_company.pk)

    removed = 0
    for dup in duplicates:
        user_model.objects.filter(company=dup).update(company=target_company)
        try:
            dup.delete()
            removed += 1
            logger.info("Removed duplicate company: %s (pk=%d)", dup.name, dup.pk)
        except Exception as e:
            logger.warning(
                "Could not delete company %s (pk=%d): %s", dup.name, dup.pk, e
            )
    if removed:
        logger.info("Consolidated %d duplicate companies into: %s", removed, target_company)
    return removed


def perform_azure_ad_sync(sso_settings=None):
    """
    Perform Azure AD user sync without request context.

    Determines the target company (from sso_settings, HQ fallback), persists it,
    migrates all existing users to it, consolidates duplicate companies, then
    syncs users from Microsoft Graph.

    Returns:
        dict: {'created': int, 'updated': int, 'skipped': int, 'error': str|None}
    """
    from horilla_core.views.microsoft_sso import get_msal_app

    result = {'created': 0, 'updated': 0, 'skipped': 0, 'error': None}

    if sso_settings is None:
        sso_settings = MicrosoftSSOSettings.load()

    if not sso_settings.is_enabled:
        result['error'] = 'Microsoft SSO is not configured or enabled.'
        return result

    company = sso_settings.company
    if company is None:
        company = Company.objects.filter(hq=True).first() or Company.objects.first()
        if company is None:
            result['error'] = 'No company found. Please create a company first.'
            return result

    _ensure_company_persisted(sso_settings, company)
    _migrate_all_users_to_company(company)
    _consolidate_companies(company)

    msal_app, _ = get_msal_app()
    if msal_app is None:
        result['error'] = 'Microsoft SSO is not configured or enabled.'
        return result

    token_response = msal_app.acquire_token_for_client(
        scopes=['https://graph.microsoft.com/.default']
    )

    if 'access_token' not in token_response:
        error = token_response.get('error', 'Unable to acquire Microsoft Graph token.')
        error_description = token_response.get('error_description', '')
        logger.error(
            f"Microsoft Graph token acquisition error: {error} - {error_description}"
        )
        result['error'] = 'Failed to sync users from Azure AD. Check app permissions and credentials.'
        return result

    access_token = token_response['access_token']
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
    }
    url = 'https://graph.microsoft.com/v1.0/users'
    params = {
        '$select': 'displayName,mail,userPrincipalName,givenName,surname,department,jobTitle,businessPhones,postalCode,preferredLanguage,country,city,companyName',
        '$top': '999',
    }

    user_model = get_user_model()

    try:
        while url:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            for graph_user in data.get('value', []):
                email = graph_user.get('mail') or graph_user.get('userPrincipalName')
                if not email:
                    result['skipped'] += 1
                    continue

                if not sso_settings.is_domain_allowed(email):
                    result['skipped'] += 1
                    continue

                first_name = graph_user.get('givenName') or ''
                last_name = graph_user.get('surname') or ''
                if not first_name and not last_name:
                    display_name = graph_user.get('displayName') or ''
                    parts = display_name.split(' ', 1)
                    first_name = parts[0] if parts else ''
                    last_name = parts[1] if len(parts) > 1 else ''

                department = _get_or_create_department(company, graph_user.get('department'))
                role = _get_or_create_role(graph_user.get('jobTitle'))
                contact_number = _extract_primary_business_phone(graph_user)
                language_code = _normalize_language(graph_user.get('preferredLanguage') or graph_user.get('preferred_language'))
                country_code = _normalize_country(graph_user.get('country'))
                postal_code = graph_user.get('postalCode') or graph_user.get('postal_code')
                city = graph_user.get('city')

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
                    if existing_user.company != company:
                        existing_user.company = company
                        updated_fields.append('company')
                    if not existing_user.department and department:
                        existing_user.department = department
                        updated_fields.append('department')
                    if not existing_user.role and role:
                        existing_user.role = role
                        updated_fields.append('role')
                    if not existing_user.contact_number and contact_number:
                        existing_user.contact_number = contact_number
                        updated_fields.append('contact_number')
                    if not existing_user.language and language_code:
                        existing_user.language = language_code
                        updated_fields.append('language')
                    if not existing_user.country and country_code:
                        existing_user.country = country_code
                        updated_fields.append('country')
                    if not existing_user.zip_code and postal_code:
                        existing_user.zip_code = postal_code
                        updated_fields.append('zip_code')
                    if not existing_user.city and city:
                        existing_user.city = city
                        updated_fields.append('city')

                    if updated_fields:
                        existing_user.save(update_fields=updated_fields)
                        result['updated'] += 1
                    continue

                username = email.split('@')[0]
                base_username = username
                suffix = 1
                while user_model.objects.filter(username=username).exists():
                    username = f'{base_username}{suffix}'
                    suffix += 1

                new_user = user_model.objects.create(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=True,
                    company=company,
                    department=department,
                    role=role,
                    contact_number=contact_number,
                    language=language_code or 'en',
                    country=country_code or 'NG',
                    city=city or 'Lagos',
                    zip_code=postal_code or '101234',
                )
                new_user.set_unusable_password()
                new_user.save()
                result['created'] += 1

            url = data.get('@odata.nextLink')
            params = None

    except requests.RequestException as error:
        logger.error(f'Microsoft Graph sync failed: {error}', exc_info=True)
        result['error'] = 'Failed to sync users from Azure AD. Please try again later.'
    except Exception as error:
        logger.error(f'Unexpected error syncing users from Azure AD: {error}', exc_info=True)
        result['error'] = 'An unexpected error occurred while syncing users.'

    return result


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

        sso_settings = MicrosoftSSOSettings.load()
        if not sso_settings.is_enabled:
            messages.error(request, _('Microsoft SSO is not configured or enabled.'))
            return redirect(self.success_url)

        result = perform_azure_ad_sync(sso_settings)

        if result['error']:
            messages.error(request, result['error'])
        else:
            company = sso_settings.company
            messages.success(
                request,
                _('Microsoft Azure AD sync completed for "%(company)s": '
                  '%(created)s created, %(updated)s updated, %(skipped)s skipped.') % {
                    'company': company.name if company else _('Unknown'),
                    'created': result['created'],
                    'updated': result['updated'],
                    'skipped': result['skipped'],
                },
            )

        return redirect(self.success_url)
