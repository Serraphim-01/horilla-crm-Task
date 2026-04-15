"""
This module defines the HorillaUser model.
It also includes related models for managing field-level permissions and company switching.
"""

# Standard library imports
from collections.abc import Iterable

# Django imports
from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import format_html

# Third-party imports
from django_countries.fields import CountryField

# First-party / Horilla imports
from horilla.db import models
from horilla.urls import reverse_lazy
from horilla.utils.choices import (
    DATE_FORMAT_CHOICES,
    DATETIME_FORMAT_CHOICES,
    NUMBER_GROUPING_CHOICES,
    TIME_FORMAT_CHOICES,
    TIMEZONE_CHOICES,
)
from horilla.utils.translation import gettext_lazy as _
from horilla.utils.upload import upload_path
from horilla_utils.methods import render_template

from .base import Company, HorillaContentType
from .finance import MultipleCurrency
from .organization import Department, Role


class HorillaUser(AbstractUser):
    """
    Represents a custom user profile for the Horilla application, extending Django's AbstractUser.

    This model serves as a replacement for Django's default User model, providing additional fields,
    such as profile image, contact details, and organizational settings.
    Users can set their language, time zone, currency, and formatting preferences to personalize their experience.
    """

    profile = models.ImageField(
        upload_to=upload_path,
        blank=True,
        null=True,
        verbose_name=_("Profile Image"),
    )
    contact_number = models.CharField(
        max_length=15, blank=True, null=True, verbose_name=_("Contact Number")
    )
    country = CountryField(verbose_name=_("Country"))
    state = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("State/Province")
    )
    city = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("City")
    )
    zip_code = models.CharField(
        max_length=20, blank=True, null=True, verbose_name=_("ZIP/Postal Code")
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("Company"),
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_department",
        verbose_name=_("Department"),
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
        verbose_name=_("Role"),
    )
    language = models.CharField(
        max_length=50,
        choices=settings.LANGUAGES,
        blank=True,
        null=True,
        verbose_name=_(
            "Language",
        ),
    )
    time_zone = models.CharField(
        max_length=100,
        choices=TIMEZONE_CHOICES,
        default="UTC",
        verbose_name=_("Time Zone"),
    )
    currency = models.ForeignKey(
        MultipleCurrency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=_("User's preferred currency for display"),
        verbose_name=_("Preferred Currency"),
        related_name="user_currency",
    )

    time_format = models.CharField(
        max_length=20,
        choices=TIME_FORMAT_CHOICES,
        default="%I:%M:%S %p",
        help_text=_("Select your preferred time format."),
        verbose_name=_("Time Format"),
    )
    date_format = models.CharField(
        max_length=20,
        choices=DATE_FORMAT_CHOICES,
        default="%Y-%m-%d",
        help_text=_("Select your preferred date format."),
        verbose_name=_("Date Format"),
    )
    date_time_format = models.CharField(
        max_length=100,
        choices=DATETIME_FORMAT_CHOICES,
        default="%Y-%m-%d %H:%M:%S",
        help_text=_("Select your preferred date time format."),
        verbose_name=_("Date Time Format"),
    )
    number_grouping = models.CharField(
        max_length=20,
        choices=NUMBER_GROUPING_CHOICES,
        default="0",
        help_text=_("Select your preferred number grouping format."),
        verbose_name=_("Number Grouping"),
    )
    created_at = models.DateTimeField(
        default=timezone.now, verbose_name=_("Created At")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="%(class)s_created",
        verbose_name=_("Created By"),
    )
    updated_at = models.DateTimeField(
        default=timezone.now, verbose_name=_("Updated At")
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="%(class)s_updated",
        verbose_name=_("Updated By"),
    )
    all_objects = UserManager()
    objects = UserManager()

    default_field_permissions = {
        "role": "readonly",
        "department": "readonly",
        "company": "readonly",
    }

    class Meta:
        """
        Meta options for the HorillaUser model.
        """

        swappable = "AUTH_USER_MODEL"
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        abstract = False
        unique_together = ["company", "username", "role"]

    AbstractUser._meta.get_field("username").verbose_name = _("Username")
    AbstractUser._meta.get_field("first_name").verbose_name = _("First Name")
    AbstractUser._meta.get_field("last_name").verbose_name = _("Last Name")
    AbstractUser._meta.get_field("email").verbose_name = _("Email")
    AbstractUser._meta.get_field("is_superuser").verbose_name = _("Administrator")
    AbstractUser._meta.get_field("is_active").verbose_name = _("Active")

    PROPERTY_LABELS = {"get_avatar_with_name": "Name"}

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def get_edit_url(self):
        """
        This method to get edit url for user
        """
        return reverse_lazy("horilla_core:user_edit_form", kwargs={"pk": self.pk})

    def get_detail_view_url(self):
        """
        This method to get detail view url for user
        """
        return reverse_lazy("horilla_core:user_detail_view", kwargs={"pk": self.pk})

    def get_change_company_url(self):
        """
        This method to get change company url for user
        """
        return reverse_lazy(
            "horilla_core:user_change_company_form", kwargs={"pk": self.pk}
        )

    def get_avatar(self):
        """
        Method will retun the api to the avatar or path to the profile image
        """
        url = f"https://ui-avatars.com/api/?name={self.first_name}&background=random"
        return url

    def get_avatar_with_name(self):
        """
        Returns HTML to render profile image and full name (first + last name).
        Safe for export: no file on profile ImageField will not raise.
        """
        try:
            image_url = (
                self.profile.url
                if self.profile and getattr(self.profile, "name", None)
                else self.get_avatar()
            )
        except (ValueError, OSError):
            image_url = self.get_avatar()
        full_name = (f"{self.first_name} {self.last_name}").strip() or getattr(
            self, "username", ""
        )

        return format_html(
            """
            <div class="flex items-center space-x-2">
                <img src="{}" alt="{}" class="w-8 h-8 rounded-full object-cover" />
                <span class="truncate text-sm font-medium text-gray-900 hover:text-primary-600">{}</span>
            </div>
            """,
            image_url,
            full_name,
            full_name,
        )

    def get_full_name(self):
        """
        Returns the user's full name.
        """
        return f"{self.first_name} {self.last_name}".strip()

    def get_delete_url(self):
        """
        This method to get delete url for user
        """
        return reverse_lazy("horilla_core:user_delete_view", kwargs={"pk": self.pk})

    def get_delete_user_from_role(self):
        """
        This method to get delete user from role url for user
        """
        return reverse_lazy(
            "horilla_core:delete_user_from_role", kwargs={"pk": self.pk}
        )

    def has_any_perms(self, perm_list, obj=None):
        """
        Check if user has any permission from the given list.
        If perm_list is empty, return True (no restrictions).
        """

        if self.is_superuser:
            return True

        if not perm_list:
            return True

        if not isinstance(perm_list, Iterable) or isinstance(perm_list, str):
            raise ValueError("perm_list must be an iterable of permissions.")

        return any(self.has_perm(perm, obj) for perm in perm_list)

    def save(self, *args, **kwargs):
        """Set username from email if missing; then save."""
        if not self.username and self.email:
            self.username = self.email

        super().save(*args, **kwargs)
    
    def send_credentials_email(self, request, password):
        """
        Send login credentials email to newly created user.
        This sends the username and password to the user's email.
        Uses Mailjet API directly, bypassing automations.
        
        Returns:
            tuple: (success: bool, message: str)
        """
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        from django.conf import settings
        from horilla_core.models import Company
        from horilla_mail.models import HorillaMailConfiguration
        from horilla_utils.middlewares import _thread_local
        import requests
        import logging
        
        logger = logging.getLogger(__name__)
        
        if not self.email:
            return False, "User has no email address"
        
        # Get Mailjet configuration directly
        mailjet_config = HorillaMailConfiguration.objects.filter(
            type="mailjet",
            mail_channel="outgoing"
        ).first()
        
        # If no specific Mailjet config, try primary config
        if not mailjet_config:
            primary_config = HorillaMailConfiguration.objects.filter(
                is_primary=True, company=self.company
            ).first()
            
            if not primary_config:
                hq_company = Company.objects.filter(hq=True).first()
                if hq_company:
                    primary_config = HorillaMailConfiguration.objects.filter(
                        is_primary=True, company=hq_company
                    ).first()
            
            # Check if the primary config is Mailjet
            if primary_config and primary_config.type == "mailjet":
                mailjet_config = primary_config
        
        if not mailjet_config:
            return False, "No Mailjet mail server configured. Please configure an outgoing Mailjet server in Settings > Mail."
        
        # Get Mailjet API credentials
        api_key = mailjet_config.mailjet_api_key
        secret_key = mailjet_config.get_decrypted_mailjet_secret_key()
        
        if not api_key or not secret_key:
            return False, "Mailjet API credentials not configured properly."
        
        # Email context
        context = {
            "user": self,
            "username": self.username,
            "password": password,
            "site_name": getattr(settings, "SITE_NAME", "Horilla"),
            "login_url": request.build_absolute_uri('/login/') if request else '/login/',
        }
        
        # Render email
        html_message = render_to_string(
            "users/user_credentials_email.html", context
        )
        plain_message = strip_tags(html_message)
        
        try:
            # Store request in thread local for the email backend to access
            old_request = getattr(_thread_local, 'request', None)
            if request:
                _thread_local.request = request
            
            # Send email directly using Mailjet API
            url = "https://api.mailjet.com/v3.1/send"
            
            display_name = mailjet_config.display_name or getattr(settings, "SITE_NAME", "Horilla")
            from_email = mailjet_config.from_email
            
            # Build the message payload
            payload = {
                "Messages": [
                    {
                        "From": {
                            "Email": from_email,
                            "Name": display_name
                        },
                        "To": [
                            {
                                "Email": self.email,
                                "Name": self.get_full_name() or self.email
                            }
                        ],
                        "Subject": f"Your {context['site_name']} Account Credentials",
                        "HTMLPart": html_message,
                        "TextPart": plain_message,
                    }
                ]
            }
            
            # Log the request for debugging
            logger.info(f"Sending credentials email to {self.email} via Mailjet API")
            
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
                # Restore old request
                if old_request:
                    _thread_local.request = old_request
                elif hasattr(_thread_local, 'request'):
                    del _thread_local.request
                
                return True, f"Credentials email sent successfully to {self.email}"
            else:
                error_data = response.json() if response.content else {}
                error_message = error_data.get("Messages", [{}])[0].get(
                    "Errors", [{}]
                )[0].get("ErrorMessage", f"Mailjet API Error: {response.status_code}")
                logger.error(f"Mailjet API Error: {error_message}")
                
                # Restore old request
                if old_request:
                    _thread_local.request = old_request
                elif hasattr(_thread_local, 'request'):
                    del _thread_local.request
                
                return False, f"Failed to send credentials email: {error_message}"
                
        except requests.exceptions.ConnectionError as e:
            # Handle connection errors specifically
            if old_request:
                _thread_local.request = old_request
            elif hasattr(_thread_local, 'request'):
                del _thread_local.request
            
            logger.error(f"Mailjet connection error: {str(e)}")
            return False, f"Failed to send credentials email: Connection error. Please check your network and Mailjet configuration."
        except Exception as e:
            # Restore old request even on error
            if old_request:
                _thread_local.request = old_request
            elif hasattr(_thread_local, 'request'):
                del _thread_local.request
            
            logger.error(f"Failed to send credentials email: {str(e)}")
            return False, f"Failed to send credentials email: {str(e)}"

    def super_user_action_col(self):
        """Returns the HTML for the super_user_action column in the list view with remove icon."""
        superuser_count = self.__class__.objects.filter(is_superuser=True).count()
        html = render_template(
            path="permissions/super_user_action_col.html",
            context={"instance": self, "superuser_count": superuser_count},
        )
        return html


class HorillaSwitchCompany(models.Model):
    """
    Horilla Switch Company model for permission management
    """

    class Meta:
        """
        Meta options for the HorillaSwitchCompany model.
        """

        managed = False
        default_permissions = ()
        permissions = (("can_switch_company", _("Can Switch Company")),)
        verbose_name = _("Switch Company")


class HorillaUserProfile(models.Model):
    """
    Horilla User Profile model for permission management
    """

    class Meta:
        """
        Meta options for the HorillaUserProfile model.
        """

        managed = False
        default_permissions = ()
        permissions = (
            ("can_view_profile", _("Can View Profile")),
            ("can_change_profile", _("Can Change Profile")),
        )
        verbose_name = _("User Profile")


class FieldPermission(models.Model):
    """
    Model to store field-level permissions for users and roles
    """

    PERMISSION_CHOICES = [
        ("readonly", "Read Only"),
        ("readwrite", "Read and Write"),
        ("hidden", "Don't Show"),
    ]

    # Link to either user or role (one must be set)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="field_permissions",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="field_permissions",
    )

    # Model and field information
    content_type = models.ForeignKey(HorillaContentType, on_delete=models.CASCADE)
    field_name = models.CharField(max_length=255)

    # Permission type
    permission_type = models.CharField(
        max_length=20, choices=PERMISSION_CHOICES, default="readwrite"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Meta options for the FieldPermission model.
        """

        unique_together = [
            ["user", "content_type", "field_name"],
            ["role", "content_type", "field_name"],
        ]
        verbose_name = _("Field Permission")
        verbose_name_plural = _("Field Permissions")

    def __str__(self):
        target = self.user.get_full_name() if self.user else self.role.role_name
        return f"{target} - {self.content_type.model}.{self.field_name}: {self.permission_type}"

    def clean(self):
        """Ensure either user or role is set, but not both."""
        # Ensure either user or role is set, but not both
        if not self.user and not self.role:
            raise ValidationError("Either user or role must be set")
        if self.user and self.role:
            raise ValidationError("Cannot set both user and role")
