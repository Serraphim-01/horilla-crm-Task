"""
HTTP response classes for Horilla.

Provides redirect and refresh responses with safe URL validation
and optional HTMX (HX-Redirect, HX-Refresh) support.
"""

from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect

from horilla.http import safe_url


class HorillaRedirectResponse(HttpResponseRedirect):
    """
    Safe redirect class to prevent open redirect vulnerabilities.
    Validates the target URL before redirecting.
    """

    def __init__(self, request, redirect_to=None, message=None, fallback_url="/"):
        """
        Initialize a safe redirect response.

        :param request: Django request object.
        :param redirect_to: Target URL (optional). If omitted, uses HTTP_REFERER.
        :param message: Optional error message to add via Django messages.
        :param fallback_url: Safe fallback URL if redirect_to is invalid (default: "/").
        """

        # If redirect_to not provided, use HTTP_REFERER
        previous_url = redirect_to or request.META.get("HTTP_REFERER", fallback_url)

        if message:
            messages.error(request, message)

        previous_url = safe_url(request, previous_url, fallback_url)

        if request.headers.get("HX-Request"):
            super().__init__(previous_url)
            self.status_code = 200
            self.headers.pop("Location", None)
            self.headers["HX-Redirect"] = previous_url
        else:
            super().__init__(previous_url)


class HorillaRefreshResponse(HttpResponse):
    """
    HTTP response that triggers a full page refresh in HTMX clients.
    For HTMX requests: sets HX-Refresh header to reload the current page.
    For non-HTMX requests: falls back to a standard redirect to the current path.
    """

    def __init__(self, request=None, fallback_url="/") -> None:
        super().__init__(content=b"", content_type="text/plain")
        if request and not request.headers.get("HX-Request"):
            safe_path = safe_url(request, request.path, fallback_url)
            self.status_code = 302
            self["Location"] = safe_path
        else:
            self.status_code = 200
            self["HX-Refresh"] = "true"
