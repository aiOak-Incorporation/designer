from typing import Any, Dict
from django.http import HttpRequest
from django.db.models import Q

from .models import Design


def designer_stats(request: HttpRequest) -> Dict[str, Any]:
    """
    Provide commonly needed designer statistics for authenticated users.
    Avoids calling queryset methods with arguments inside templates.
    """
    user = getattr(request, "user", None)

    total_designs: int = 0
    designs_with_techpack_count: int = 0
    published_designs_count: int = 0
    recent_designs = []

    if user is not None and getattr(user, "is_authenticated", False):
        try:
            user_designs_qs = Design.objects.filter(designer=user)
            total_designs = user_designs_qs.count()
            designs_with_techpack_count = user_designs_qs.filter(
                Q(techpack_pdf__isnull=False) | Q(techpack_excel__isnull=False)
            ).count()
            published_designs_count = user_designs_qs.filter(published=True).count()
            recent_designs = list(user_designs_qs.order_by("-created_at")[:8])
        except Exception:
            # Be resilient in case of transient DB issues
            total_designs = 0
            designs_with_techpack_count = 0
            published_designs_count = 0
            recent_designs = []

    return {
        "total_designs": total_designs,
        "designs_with_techpack_count": designs_with_techpack_count,
        "published_designs_count": published_designs_count,
        "recent_designs": recent_designs,
    }
