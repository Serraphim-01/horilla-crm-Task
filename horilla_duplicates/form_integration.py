"""
Integration module to inject duplicate checking into Horilla form views.
This module patches HorillaSingleFormView and HorillaMultiStepFormView
to check for duplicates before saving.
Also injects Potential Duplicates tab into detail views.
"""

# Standard library imports
import logging
import uuid
from functools import wraps

# Third party/ Django imports
from django.template.loader import render_to_string

# First-party / Horilla apps
from horilla.apps import apps
from horilla.http import HttpResponse, QueryDict
from horilla.urls import reverse
from horilla.utils.translation import gettext_lazy as _
from horilla_core.models import HorillaContentType
from horilla_duplicates.duplicate_checker import check_duplicates
from horilla_duplicates.models import DuplicateRule
from horilla_utils.middlewares import _thread_local


def create_form_valid_with_duplicate_check(original_form_valid, is_multi_step=False):
    """
    Create a wrapped form_valid method that checks for duplicates before saving.

    Args:
        original_form_valid: The original form_valid method
        is_multi_step: Whether this is for multi-step form view
    """

    @wraps(original_form_valid)
    def form_valid_with_duplicate_check(self, form):
        # Skip duplicate checking if this is not the final step (for multi-step)
        if is_multi_step:
            # Get current step from POST data or view attribute
            step = int(self.request.POST.get("step", getattr(self, "current_step", 1)))
            total_steps = getattr(self, "total_steps", 1)
            if step < total_steps:
                # Not final step, proceed normally
                return original_form_valid(self, form)

        # Check if we should skip duplicate checking (e.g., if bypass flag is set)
        skip_check = (
            self.request.GET.get("skip_duplicate_check", "false").lower() == "true"
        )
        skip_check = (
            skip_check
            or self.request.POST.get("skip_duplicate_check", "false").lower() == "true"
        )
        if skip_check:
            # Set flag on request so we don't check again
            self.request.skip_duplicate_check = True
            return original_form_valid(self, form)

        # Only check duplicates if model is registered for duplicate checking
        if not hasattr(self, "model") or not self.model:
            return original_form_valid(self, form)

        # Check if model is registered for duplicate checking
        try:
            from horilla.registry.feature import FEATURE_REGISTRY

            duplicate_models = FEATURE_REGISTRY.get("duplicate_models", [])
            if self.model not in duplicate_models:
                return original_form_valid(self, form)
        except Exception:
            # If registry check fails, continue anyway
            pass

        # Create instance from form (before saving)
        instance = form.save(commit=False)

        try:
            if hasattr(self.request, "active_company"):
                instance.company = self.request.active_company
            elif hasattr(_thread_local, "request") and hasattr(
                _thread_local.request, "active_company"
            ):
                instance.company = _thread_local.request.active_company
            elif hasattr(self.request.user, "company"):
                instance.company = self.request.user.company
        except Exception:
            pass

        is_edit = bool(
            getattr(self, "object", None) and getattr(self.object, "pk", None)
        )
        if not is_edit:
            is_edit = bool(self.kwargs.get("pk"))
        if getattr(self, "duplicate_mode", False):
            is_edit = False
        try:
            duplicate_result = check_duplicates(instance, is_edit=is_edit)

            if duplicate_result.get("has_duplicates"):
                return get_duplicate_warning_response(
                    self.request,
                    duplicate_result,
                    form,
                    self,
                    original_form_valid,
                    is_multi_step,
                )
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning("Duplicate check failed: %s", e)

        return original_form_valid(self, form)

    return form_valid_with_duplicate_check


def get_duplicate_warning_response(
    request, duplicate_result, form, view, original_form_valid, is_multi_step
):
    """
    Generate HTMX response that opens horillaModal with duplicate warning.
    Returns the form HTML with script appended so the form stays visible.

    Args:
        request: HttpRequest
        duplicate_result: dict from check_duplicates()
        form: Form instance
        view: View instance
        original_form_valid: Original form_valid method to call after user confirms
        is_multi_step: Whether this is a multi-step form
    """
    # Serialize form data for re-submission
    form_data = {}
    for field_name in form.fields:
        if field_name in form.cleaned_data:
            value = form.cleaned_data[field_name]
            # Handle various field types
            if hasattr(value, "pk"):  # ForeignKey
                form_data[field_name] = value.pk
            elif hasattr(value, "__iter__") and not isinstance(
                value, str
            ):  # ManyToMany
                form_data[field_name] = [v.pk if hasattr(v, "pk") else v for v in value]
            else:
                form_data[field_name] = value

    # Also include POST data for file fields and other fields not in cleaned_data
    for key, value in request.POST.items():
        if key not in form_data and key != "csrfmiddlewaretoken":
            if key in request.POST.getlist(key):
                form_data[key] = request.POST.getlist(key)
            else:
                form_data[key] = value

    # Get form URL for continue button
    form_url = request.path
    query_params = request.GET.copy()
    query_params["skip_duplicate_check"] = "true"
    if query_params:
        form_url += "?" + query_params.urlencode()

    # Preserve save_and_new button value if it was clicked
    save_and_new_value = request.POST.get("save_and_new", "")

    # Store modal context in session for the view to retrieve
    session_key = f"duplicate_modal_{uuid.uuid4().hex[:16]}"
    request.session[session_key] = {
        "alert_title": duplicate_result.get(
            "alert_title", "Potential Duplicate Detected"
        ),
        "alert_message": duplicate_result.get(
            "alert_message", "Similar records were found. Do you want to proceed?"
        ),
        "duplicate_records": [
            (r.pk, str(r)) for r in duplicate_result.get("duplicate_records", [])[:10]
        ],
        "show_duplicate_records": duplicate_result.get("show_duplicate_records", True),
        "form_url": form_url,
        "model_name": (
            view.model._meta.model_name
            if hasattr(view, "model") and view.model
            else None
        ),
        "action": duplicate_result.get("action", "allow"),  # 'allow' or 'block'
        "save_and_new": save_and_new_value,  # Preserve save_and_new button value
    }
    request.session.modified = True

    modal_url = reverse(
        "horilla_duplicates:duplicate_warning_modal",
        kwargs={"session_key": session_key},
    )

    try:
        context = view.get_context_data(form=form)
        if is_multi_step:
            template_name = "form_view.html"
        else:
            template_name = view.template_name or "single_form_view.html"

        form_html = render_to_string(template_name, context, request=request)

        # Append HTMX div to form HTML to open duplicate modal
        htmx_content = f"""
        <div hx-get="{modal_url}"
             hx-target="#dynamicCreateModalBox"
             hx-trigger="load"
             hx-swap="innerHTML"
             hx-on::load="openDynamicModal();">
        </div>
        """

        return HttpResponse(form_html + htmx_content)
    except Exception as e:
        # Fallback to HTMX-only response if rendering fails
        logger = logging.getLogger(__name__)
        logger.warning("Error rendering form for duplicate warning: %s", str(e))
        htmx_content = f"""
        <div hx-get="{modal_url}"
             hx-target="#dynamicCreateModalBox"
             hx-trigger="load"
             hx-swap="innerHTML"
             hx-on::load="openDynamicModal();">
        </div>
        """
        return HttpResponse(htmx_content)


def create_init_with_duplicate_tab(original_init):
    """
    Create a wrapped __init__ method that adds Potential Duplicates tab.

    Args:
        original_init: The original __init__ method
    """

    @wraps(original_init)
    def __init___with_duplicate_tab(self, **kwargs):
        # Call original __init__ first
        original_init(self, **kwargs)

        # Check if we have an object_id (required for tabs)
        if not self.object_id:
            return
        try:
            # Get model from self if available
            model = None
            if hasattr(self, "model") and self.model:
                model = self.model
            else:

                duplicate_rule_content_types = DuplicateRule.objects.values_list(
                    "content_type", flat=True
                ).distinct()

                # Try each content type to see if object_id exists in that model
                for horilla_ct_id in duplicate_rule_content_types:
                    try:
                        horilla_ct = HorillaContentType.objects.get(pk=horilla_ct_id)
                        model_name = horilla_ct.model

                        # Find the model class
                        Model = None
                        for app_config in apps.get_app_configs():
                            try:
                                Model = apps.get_model(
                                    app_config.label, model_name.lower()
                                )
                                if Model:
                                    break
                            except (LookupError, ValueError):
                                continue

                        if Model:
                            # Check if object with this pk exists in this model
                            if Model.objects.filter(pk=self.object_id).exists():
                                model = Model
                                break
                    except Exception:
                        continue

            if not model:
                return

            # Check if model has duplicate rules and matching rules
            try:
                model_name = model._meta.model_name.lower()
                content_type = HorillaContentType.objects.filter(
                    model=model_name
                ).first()

                if not content_type:
                    return

                # Check if there are duplicate rules for this content type
                duplicate_rules = DuplicateRule.objects.filter(
                    content_type=content_type
                )
                if not duplicate_rules.exists():
                    return

                # Check if at least one duplicate rule has a matching rule
                has_matching_rule = False
                for dup_rule in duplicate_rules:
                    if dup_rule.matching_rule:
                        has_matching_rule = True
                        break

                if not has_matching_rule:
                    return

                django_content_type = HorillaContentType.objects.get_for_model(model)
                content_type_id = django_content_type.pk

                duplicates_url = reverse(
                    "horilla_duplicates:potential_duplicates_tab", kwargs={}
                )
                # Use QueryDict to properly construct URL with parameters
                params = QueryDict(mutable=True)
                params["object_id"] = self.object_id
                params["content_type_id"] = content_type_id
                duplicates_url = f"{duplicates_url}?{params.urlencode()}"

                # Add the tab to self.tabs
                if not hasattr(self, "tabs"):
                    self.tabs = []

                # Check if tab already exists
                tab_exists = any(
                    tab.get("id") == "potential-duplicates" for tab in self.tabs
                )
                if not tab_exists:
                    tab_data = {
                        "title": _("Potential Duplicates"),
                        "url": duplicates_url,
                        "target": "tab-potential-duplicates-content",
                        "id": "potential-duplicates",
                    }
                    self.tabs.append(tab_data)
            except Exception as e:
                # If any error occurs, just skip adding the tab
                logger = logging.getLogger(__name__)
                logger.debug(
                    "Could not add Potential Duplicates tab: %s", e, exc_info=True
                )
        except Exception:
            pass

    return __init___with_duplicate_tab
