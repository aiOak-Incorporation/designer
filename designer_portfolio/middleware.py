from __future__ import annotations

from typing import Callable, Dict

from django.http import HttpRequest, HttpResponse


UTM_PARAM_NAMES = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    # Common ad click identifiers
    "gclid",
    "fbclid",
    "ttclid",
    "msclkid",
}


def _should_capture(request: HttpRequest) -> bool:
    if request.method != "GET":
        return False
    path = request.path or ""
    if path.startswith("/admin"):
        return False
    if path.startswith("/static"):
        return False
    return True


class UTMTrackingMiddleware:
    """Persist first-touch UTM and attribution data into the session.

    - Captures standard UTM params and common click IDs on GET requests
    - Records initial landing page and initial referrer once
    - Exposes the dict on `request.utm` for convenient access
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        session_has_utm = isinstance(request.session.get("utm"), dict)
        utm_data: Dict[str, str] = request.session.get("utm", {}) if session_has_utm else {}

        if _should_capture(request):
            # Collect any UTM/click id params present on this request
            found_any_param = False
            for name in UTM_PARAM_NAMES:
                value = request.GET.get(name)
                if value and name not in utm_data:
                    utm_data[name] = value
                    found_any_param = True

            # Record first landing page only once (prefer when UTM present)
            if "landing_page" not in utm_data and (found_any_param or not session_has_utm):
                utm_data["landing_page"] = request.build_absolute_uri()

            # Record initial referrer once
            if "initial_referrer" not in utm_data:
                referrer = request.META.get("HTTP_REFERER", "")
                if referrer:
                    utm_data["initial_referrer"] = referrer

            if utm_data:
                request.session["utm"] = utm_data
                # Mark session as modified to ensure it is saved even if values are equal
                request.session.modified = True

        # Attach to request for templates/views
        request.utm = request.session.get("utm", {})

        response = self.get_response(request)
        return response
