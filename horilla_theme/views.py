"""Views for managing Horilla UI themes via HTMX-enabled endpoints."""

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.template.loader import render_to_string
from django.views import View
from django.views.generic import TemplateView

# First party imports (Horilla)
from horilla.http import HttpResponse
# The theme manager used to restrict access to users with specific permissions.
# For this change we want all users to be able to view and edit the color theme,
# so we remove the permission checks. The decorators are commented out for
# reference but not applied.
# from horilla.utils.decorators import method_decorator, permission_required_or_denied
from horilla.utils.translation import gettext_lazy as _

# First-party / Horilla apps
from horilla_theme.models import HorillaColorTheme, UserTheme


# @method_decorator(
#     permission_required_or_denied(["horilla_theme.view_horillacolortheme"]),
#     name="dispatch",
# )
class ThemeView(TemplateView):
    """
    Displays the theme management interface for authenticated users.
    """

    template_name = "theme/theme_view.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["themes"] = HorillaColorTheme.objects.all()
        context["active_theme"] = self._get_active_theme()

        # Get the global default theme (for login page)
        context["default_theme"] = HorillaColorTheme.get_default_theme()

        return context

    def _get_active_theme(self):
        """Get the active theme for the current user."""
        return UserTheme.get_theme_for_user(self.request.user)


# @method_decorator(
#     permission_required_or_denied(
#         ["horilla_theme.change_companytheme", "horilla_theme.add_companytheme"]
#     ),
#     name="dispatch",
# )
class ChangeThemeView(LoginRequiredMixin, View):
    """
    View to change the company theme via HTMX.
    """

    def post(self, request, *args, **kwargs):
        """Handle an HTMX request to change the active company theme."""
        theme_id = request.POST.get("theme_id")
        is_default = request.POST.get("is_default") == "on"

        if not theme_id:
            return self._error_response(request, _("Theme ID is required"), 400)

        try:
            theme = HorillaColorTheme.objects.get(pk=theme_id)
            self._update_user_theme(request.user, theme, is_default)

            if is_default:
                messages.success(
                    request,
                    _("Theme changed successfully and set as default for login page"),
                )
            else:
                messages.success(request, _("Theme changed successfully"))

            return self._render_themes(request, theme)

        except HorillaColorTheme.DoesNotExist:
            return self._error_response(request, _("Theme not found"), 404)
        except Exception as e:
            return self._error_response(
                request,
                _("An error occurred while changing the theme: %(error)s")
                % {"error": str(e)},
                500,
            )

    def _update_user_theme(self, user, theme, is_default=False):
        """Update or create the user's theme preference."""
        with transaction.atomic():
            UserTheme.objects.update_or_create(
                user=user, defaults={"theme": theme}
            )

            # If setting as default, set it on the theme itself
            if is_default:
                theme.is_default = True
                theme.save()  # This will automatically unset other defaults

    def _render_themes(self, request, active_theme=None, status=200):
        """Render the theme cards HTML."""
        if active_theme is None:
            active_theme = UserTheme.get_theme_for_user(request.user)

        themes = HorillaColorTheme.objects.all()

        default_theme = HorillaColorTheme.get_default_theme()

        html = render_to_string(
            "theme/theme_cards.html",
            {
                "themes": themes,
                "active_theme": active_theme,
                "default_theme": default_theme,
                "request": request,
            },
        )
        return HttpResponse(html, status=status)

    def _error_response(self, request, message, status):
        """Generate an error response with appropriate message and status."""
        messages.error(request, message)
        return self._render_themes(request, status=status)


# @method_decorator(
#     permission_required_or_denied(["horilla_theme.add_horillacolortheme"]),
#     name="dispatch",
# )
class SetDefaultThemeView(LoginRequiredMixin, View):
    """
    View to set/unset a theme as default for login page via HTMX.
    """

    def post(self, request, *args, **kwargs):
        """Handle an HTMX request to toggle a theme as the global default."""
        theme_id = request.POST.get("theme_id")

        if not theme_id:
            return self._error_response(request, _("Theme ID is required"), 400)

        try:
            theme = HorillaColorTheme.objects.get(pk=theme_id)

            # Save this selection as the current user's preferred theme
            from horilla_theme.models import UserTheme

            UserTheme.objects.update_or_create(user=request.user, defaults={"theme": theme})

            messages.success(request, _("Theme set successfully for your account"))

            return self._render_themes(request)

        except Exception as e:
            return self._error_response(
                request,
                _("An error occurred while setting the default theme: %(error)s")
                % {"error": str(e)},
                500,
            )

    def _render_themes(self, request, status=200):
        """Render the theme cards HTML."""
        active_theme = UserTheme.get_theme_for_user(request.user)

        themes = HorillaColorTheme.objects.all()
        default_theme = HorillaColorTheme.get_default_theme()

        html = render_to_string(
            "theme/theme_cards.html",
            {
                "themes": themes,
                "active_theme": active_theme,
                "default_theme": default_theme,
                "request": request,
            },
        )
        return HttpResponse(html, status=status)

    def _error_response(self, request, message, status):
        """Generate an error response with appropriate message and status."""
        messages.error(request, message)
        return self._render_themes(request, status=status)
