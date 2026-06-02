# horilla_core/scheduler.py

"""
Background scheduler tasks for Horilla.

This module defines periodic background jobs executed using APScheduler.
It handles maintenance and automation tasks such as:

- Updating the active fiscal year
- Cleaning up expired records from the recycle bin
- Periodically syncing users from Azure AD / Microsoft Entra ID
- Initializing and starting the background scheduler

These tasks are intended to run continuously in the background
alongside the Django application.
"""

import logging
import sys

from apscheduler.schedulers.background import BackgroundScheduler
from django.core.management import call_command
from django.utils import timezone

from horilla_core.models import RecycleBin, RecycleBinPolicy

logger = logging.getLogger(__name__)


def fiscal_year_update():
    """
    Trigger the fiscal year update management command.

    This function invokes the `update_fiscal_year` Django management
    command to ensure fiscal year data remains up to date.
    """
    call_command("update_fiscal_year")


def clear_expired_recyclebin():
    """
    Remove recycle bin records that exceed their retention period.

    For each recycle bin policy, this function deletes records whose
    deletion date is older than the configured retention duration.
    """
    now = timezone.now()
    total_deleted = 0
    for policy in RecycleBinPolicy.objects.select_related("company"):
        cutoff = now - timezone.timedelta(days=policy.retention_days)
        deleted_count, _ = RecycleBin.objects.filter(
            company=policy.company, deleted_at__date__lte=cutoff.date()
        ).delete()
        total_deleted += deleted_count


def sync_azure_ad_users():
    """
    Periodically sync users from Azure AD / Microsoft Entra ID.

    This function reads the MicrosoftSSOSettings singleton and, if SSO is
    enabled and an organization is configured, performs a full user sync
    from the configured Azure AD tenant. All synced users are assigned
    to the organization configured in the SSO settings.
    """
    from horilla_core.models import MicrosoftSSOSettings
    from horilla_core.views.microsoft_sso_settings import perform_azure_ad_sync

    try:
        sso_settings = MicrosoftSSOSettings.load()
    except Exception as e:
        logger.error("Failed to load Microsoft SSO settings for background sync: %s", e)
        return

    if not sso_settings.is_enabled:
        return

    if sso_settings.company is None:
        logger.warning(
            "Azure AD background sync skipped: no organization is associated "
            "with the Microsoft SSO configuration."
        )
        return

    logger.info("Starting Azure AD background sync for organization: %s", sso_settings.company)
    result = perform_azure_ad_sync(sso_settings)

    if result['error']:
        logger.error("Azure AD background sync failed: %s", result['error'])
    else:
        logger.info(
            "Azure AD background sync completed: %(created)s created, "
            "%(updated)s updated, %(skipped)s skipped.",
            result,
        )


if not any(
    cmd in sys.argv
    for cmd in ["makemigrations", "migrate", "compilemessages", "flush", "shell"]
):
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        fiscal_year_update, "interval", hours=12, id="fiscal_year_update_job"
    )
    scheduler.add_job(
        clear_expired_recyclebin,
        "interval",
        hours=4,
        id="clear_expired_recyclebin_job",
        replace_existing=True,
    )
    scheduler.add_job(
        sync_azure_ad_users,
        "interval",
        minutes=30,
        id="sync_azure_ad_users_job",
        replace_existing=True,
    )
    scheduler.start()
