"""
This module registers Floating, Settings, My Settings, and Main Section menus
for the horilla_theme app
"""

from horilla.menu.main_section_menu import register as main_register
from horilla.menu import sub_section_menu

# First party imports (Horilla)
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _

# First-party / Horilla apps
from horilla_theme.apps import HorillaThemeConfig
from horilla_theme.models import HorillaColorTheme

# Define your menu registration logic here


@main_register
class ColorThemePage:
    """Direct link to the color theme page in the main section menu."""

    title = "Color Theme"
    icon = "horilla_theme/assets/icons/theme.svg"
    order = 8
    section = "theme"
    name = "Color Theme"
    items = [
        {
            "label": "Color Theme",
            "url": reverse_lazy("horilla_theme:color_theme_view"),
            "hx-push-url": "true",
            "hx-target": "#settings-content",
            "hx-select": "#theme-view",
            "hx-select-oob": "#settings-sidebar",
            "perm": "horilla_theme.change_horillacolortheme",
        }
    ]


@sub_section_menu.register
class ThemeSubSection:
    section = "theme"
    verbose_name = _("Color Theme")
    icon = "horilla_theme/assets/icons/theme.svg"
    url = reverse_lazy("horilla_theme:color_theme_view")
    app_label = "horilla_theme"
    position = 1
    attrs = {
        "hx-boost": "true",
        "hx-target": "#mainContent",
        "hx-select": "#mainContent",
        "hx-swap": "outerHTML",
    }
