"""Branding configuration utilities for Task."""

from importlib import import_module

from django.conf import settings
from django.utils.translation import gettext_lazy as _

DEFAULTS = {
    "TITLE": _("Task"),
    "LOGIN_WELCOME_LINE": _("Welcome to Task"),
    "LOGIN_TAG_LINE": _("Please sign in to access your dashboard"),
    "SIGNUP_TAG_LINE": _("Please sign up to access Task"),
    "LOGO_PATH": "assets/img/task-logo.png",
    "FAVICON_PATH": "favicon.ico",
    "PAGE_HEADER": _("Task"),
}


def load_branding():
    """
    Loads branding values from an optional module defined in settings.
    Falls back to DEFAULTS when not defined.
    """

    branding = DEFAULTS.copy()

    module_path = getattr(settings, "BRANDING_MODULE", None)

    if not module_path:
        return branding

    try:
        module = import_module(module_path)
    except Exception as e:
        print(e)
        return branding

    for key in DEFAULTS.keys():
        if hasattr(module, key):
            branding[key] = getattr(module, key)

    return branding
