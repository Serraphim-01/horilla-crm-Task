"""
AppConfig for the horilla_duplicates app
"""

# First party imports (Horilla)
from horilla.apps import AppLauncher
from horilla.utils.translation import gettext_lazy as _


class HorillaDuplicatesConfig(AppLauncher):
    """App configuration class for horilla_duplicates."""

    default = True

    default_auto_field = "django.db.models.BigAutoField"
    name = "horilla_duplicates"
    verbose_name = _("Clone Management")

    url_prefix = "duplicates/"
    url_module = "horilla_duplicates.urls"

    auto_import_modules = ["menu", "registration", "inject"]
