"""
Microsoft SSO Settings Model

This module defines the model for storing Microsoft SSO configuration settings
in the database with encrypted sensitive fields.
"""

import logging

from django.db import IntegrityError

from horilla.db import models
from horilla.utils.translation import gettext_lazy as _
from horilla_core.models import HorillaCoreModel
from horilla_mail.encryption_utils import decrypt_password
from horilla_mail.fields import EncryptedCharField

logger = logging.getLogger(__name__)


class MicrosoftSSOSettings(HorillaCoreModel):
    """
    Singleton model to store Microsoft SSO configuration settings.
    
    This model stores the Azure AD / Microsoft Entra ID configuration
    needed for Single Sign-On authentication.
    """

    # Basic Configuration
    is_enabled = models.BooleanField(
        default=False,
        verbose_name=_("Enable Microsoft SSO"),
        help_text=_("Turn on/off Microsoft Single Sign-On"),
    )
    
    client_id = models.CharField(
        max_length=500,
        verbose_name=_("Client ID"),
        help_text=_("Azure AD Application (Client) ID"),
        blank=True,
        null=True,
    )
    
    client_secret = EncryptedCharField(
        max_length=1000,
        verbose_name=_("Client Secret"),
        help_text=_("Azure AD Application Client Secret (will be encrypted)"),
        blank=True,
        null=True,
    )
    
    tenant_id = models.CharField(
        max_length=500,
        verbose_name=_("Tenant ID"),
        help_text=_(
            "Azure AD Directory (Tenant) ID. Use 'common' for multi-tenant apps."
        ),
        default="common",
        blank=True,
        null=True,
    )
    
    # Auto-provisioning settings
    auto_provision = models.BooleanField(
        default=True,
        verbose_name=_("Auto-provision Users"),
        help_text=_(
            "Automatically create user accounts on first Microsoft SSO login"
        ),
    )
    
    # Allowed domains (optional restriction)
    allowed_domains = models.TextField(
        verbose_name=_("Allowed Email Domains"),
        help_text=_(
            "Comma-separated list of allowed email domains. "
            "Leave empty to allow all domains. Example: company.com,partner.org"
        ),
        blank=True,
        null=True,
    )
    
    # Scopes configuration
    scopes = models.TextField(
        verbose_name=_("OAuth Scopes"),
        help_text=_(
            "Comma-separated list of Microsoft Graph API scopes. "
            "Default: User.Read,email,profile,openid"
        ),
        default="User.Read,email,profile,openid",
        blank=True,
        null=True,
    )
    
    # Display settings
    button_text = models.CharField(
        max_length=100,
        verbose_name=_("Button Text"),
        help_text=_("Text displayed on the Microsoft SSO button"),
        default="Sign in with Microsoft",
        blank=True,
        null=True,
    )

    class Meta:
        """Meta options for MicrosoftSSOSettings."""

        verbose_name = _("Microsoft SSO Settings")
        verbose_name_plural = _("Microsoft SSO Settings")

    def __str__(self):
        """String representation."""
        status = "Enabled" if self.is_enabled else "Disabled"
        return f"Microsoft SSO Settings ({status})"

    def save(self, *args, **kwargs):
        """
        Ensure only one instance exists (singleton pattern).
        """
        self.pk = 1  # Force primary key to 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """
        Load or create the singleton instance.
        Uses all_objects to bypass company filtering since this is a global setting.
        
        Returns:
            MicrosoftSSOSettings instance
        """
        try:
            # Use all_objects to bypass CompanyFilteredManager
            return cls.all_objects.get(pk=1)
        except cls.DoesNotExist:
            # Create new instance if it doesn't exist
            try:
                return cls.all_objects.create(pk=1)
            except IntegrityError:
                # Another thread created it or there's a conflict
                # Use filter and first() to avoid race conditions
                obj = cls.all_objects.filter(pk=1).first()
                if obj:
                    return obj
                # If still not found, create without forcing pk
                # The save() method will set pk=1 anyway
                return cls()

    def get_client_secret(self):
        """
        Get decrypted client secret.
        
        Returns:
            Decrypted client secret string or None
        """
        if self.client_secret:
            try:
                return decrypt_password(self.client_secret)
            except Exception as e:
                logger.error(f"Failed to decrypt client secret: {str(e)}")
                return None
        return None

    def get_scopes_list(self):
        """
        Get scopes as a list.
        
        Returns:
            List of scope strings
        """
        if self.scopes:
            return [scope.strip() for scope in self.scopes.split(',') if scope.strip()]
        return ['User.Read', 'email', 'profile', 'openid']

    def get_allowed_domains_list(self):
        """
        Get allowed domains as a list.
        
        Returns:
            List of domain strings or empty list (meaning all domains allowed)
        """
        if self.allowed_domains:
            return [domain.strip() for domain in self.allowed_domains.split(',') if domain.strip()]
        return []

    def is_domain_allowed(self, email):
        """
        Check if the email domain is allowed.
        
        Args:
            email: Email address to check
            
        Returns:
            True if domain is allowed, False otherwise
        """
        if not self.allowed_domains:
            return True  # No restrictions
        
        allowed_domains = self.get_allowed_domains_list()
        if not allowed_domains:
            return True
        
        email_domain = email.split('@')[-1].lower() if '@' in email else ''
        return email_domain in [domain.lower() for domain in allowed_domains]

    def get_redirect_uri(self, request=None):
        """
        Get the redirect URI for Microsoft SSO callback.
        
        Args:
            request: HTTP request object (optional)
            
        Returns:
            Redirect URI string
        """
        if request:
            return request.build_absolute_uri('/microsoft-sso/callback/')
        # Fallback - will be overridden in views
        return '/microsoft-sso/callback/'
