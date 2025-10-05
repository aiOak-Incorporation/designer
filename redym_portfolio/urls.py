from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views  # ✅ add this if you plan to call views.generate_techpack

from .views import (
    HomePageView,
    CollectionsPageView,
    CollectionViewSet,
    CollectionDetailView,
    DesignListView, DesignDetailView,
    EventListView, EventDetailView,
    upload_design,
    BrandViewSet, DesignViewSet, EventViewSet,
    PendingDesignersView, approve_designer, reject_designer, reinstate_designer,
    AboutView,
    DesignerDashboardView, designer_designs_view, designer_design_create_view, 
    designer_design_edit_view, designer_design_delete_view,
)



router = DefaultRouter()
router.register(r"brands", BrandViewSet, basename="brand")
router.register(r"collections", CollectionViewSet, basename="collection")
router.register(r"designs", DesignViewSet, basename="design")
router.register(r"events", EventViewSet, basename="event")

urlpatterns = [
    # Pages
    path("", HomePageView.as_view(), name="home"),
    
    # Collections
    path("collections/", CollectionsPageView.as_view(), name="collections"),
    path("collections/<slug:slug>/", CollectionDetailView.as_view(), name="collection_detail"),
    
    
    path("designs/upload/", upload_design, name="upload_design"),  # 👈 Move this ABOVE
    path("designs/", DesignListView.as_view(), name="design_list"),
    path("designs/<slug:slug>/", DesignDetailView.as_view(), name="design_detail"),

    path("events/", EventListView.as_view(), name="event_list"),
    path("events/<slug:slug>/", EventDetailView.as_view(), name="event_detail"),
    
    path("about/", AboutView.as_view(), name="about"),   # ✅ fix added here
    
    # Designer Dashboard
    path("dashboard/", DesignerDashboardView.as_view(), name="designer_dashboard"),
    path("dashboard/designs/", designer_designs_view, name="designer_designs"),
    path("dashboard/designs/new/", designer_design_create_view, name="designer_design_create"),
    path("dashboard/designs/<slug:slug>/edit/", designer_design_edit_view, name="designer_design_edit"),
    path("dashboard/designs/<slug:slug>/delete/", designer_design_delete_view, name="designer_design_delete"),
    
    # Authenticated upload page
    path("designs/upload/", upload_design, name="upload_design"),

    # API
    path("api/", include(router.urls)),

    # Admin actions
    path("admin/pending-designers/", PendingDesignersView.as_view(), name="pending_designers"),
    path("admin/approve-designer/<int:user_id>/", approve_designer, name="approve_designer"),
    path("admin/reject-designer/<int:user_id>/", reject_designer, name="reject_designer"),
    path("admin/reinstate-designer/<int:designer_id>/", reinstate_designer, name="reinstate_designer"),

     # ✅ Techpack generator route
    path("generate-techpack/<slug:slug>/", views.generate_techpack, name="generate_techpack"),
]
