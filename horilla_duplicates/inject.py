"""Runtime injections for duplicate checking in Horilla generic views."""

# Standard library imports
import logging

# First-party / Horilla apps
from horilla_duplicates.form_integration import (
    create_form_valid_with_duplicate_check,
    create_init_with_duplicate_tab,
)
from horilla_generics.views import (
    HorillaDetailTabView,
    HorillaMultiStepFormView,
    HorillaSingleFormView,
)


def inject_duplicate_checking():
    """
    Inject duplicate checking into HorillaSingleFormView and HorillaMultiStepFormView.
    This should be called from apps.py ready() method.
    """
    try:
        # Store original form_valid methods
        if not hasattr(HorillaSingleFormView, "_original_form_valid"):
            HorillaSingleFormView._original_form_valid = (
                HorillaSingleFormView.form_valid
            )
            HorillaSingleFormView.form_valid = create_form_valid_with_duplicate_check(
                HorillaSingleFormView._original_form_valid, is_multi_step=False
            )

        if not hasattr(HorillaMultiStepFormView, "_original_form_valid"):
            HorillaMultiStepFormView._original_form_valid = (
                HorillaMultiStepFormView.form_valid
            )
            HorillaMultiStepFormView.form_valid = (
                create_form_valid_with_duplicate_check(
                    HorillaMultiStepFormView._original_form_valid, is_multi_step=True
                )
            )
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning("Failed to inject duplicate checking: %s", e)


def inject_duplicate_tab():
    """
    Inject Potential Duplicates tab into HorillaDetailTabView.
    This should be called from apps.py ready() method.
    """
    try:
        # Store original __init__ method
        if not hasattr(HorillaDetailTabView, "_original_init"):
            HorillaDetailTabView._original_init = HorillaDetailTabView.__init__
            HorillaDetailTabView.__init__ = create_init_with_duplicate_tab(
                HorillaDetailTabView._original_init
            )
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning("Failed to inject duplicate tab: %s", e)


# Inject duplicate checking into form views
inject_duplicate_checking()

# Inject Potential Duplicates tab into detail views
inject_duplicate_tab()
