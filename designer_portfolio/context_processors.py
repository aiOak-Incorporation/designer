from django.db.models import Q
from django.http import HttpRequest

from .models import Design, DesignerProfile


def dashboard_counts(request: HttpRequest) -> dict:
    """Provide commonly used dashboard counts for the authenticated user.

    Returns zeros when the user is anonymous to keep templates simple.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {
            "total_designs": 0,
            "designs_with_techpack_count": 0,
            "published_designs_count": 0,
        }

    user_designs = Design.objects.filter(designer=user)

    designs_with_techpack = user_designs.filter(
        Q(techpack_pdf__isnull=False) | Q(techpack_excel__isnull=False)
    )

    return {
        "total_designs": user_designs.count(),
        "designs_with_techpack_count": designs_with_techpack.count(),
        "published_designs_count": user_designs.filter(published=True).count(),
    }


def active_portfolio_template(request: HttpRequest) -> dict:
    """Expose the active portfolio template key and css path.

    Falls back to the global default (classic) if no authenticated user/profile.
    """
    default_key = "classic"
    user = getattr(request, "user", None)
    template_key = default_key

    if user is not None and user.is_authenticated:
        try:
            profile: DesignerProfile = DesignerProfile.objects.get(user=user)
            template_key = getattr(profile, "portfolio_template", default_key) or default_key
        except DesignerProfile.DoesNotExist:
            template_key = default_key

    # Build css path under static
    css_path = f"css/templates/{template_key}.css"
    return {
        "portfolio_template_key": template_key,
        "portfolio_template_css": css_path,
    }
