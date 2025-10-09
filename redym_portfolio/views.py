from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import TemplateView, DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from .forms import DesignerSignUpForm
from .models import (
    DesignerProfile,
    SubscriptionPlan,
    UserSubscription,
    Design,
    Collection,
    Event,
)

def signup_view(request):
    if request.method == "POST":
        form = DesignerSignUpForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Signup received! Your account will be reviewed and approved by an admin."
            )
            return redirect("login")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = DesignerSignUpForm()

    return render(request, "registration/signup.html", {"form": form})

# Basic view classes for URL compatibility
class HomePageView(TemplateView):
    template_name = "redym_portfolio/home.html"

class AboutView(TemplateView):
    template_name = "redym_portfolio/about.html"

class CollectionsPageView(TemplateView):
    template_name = "redym_portfolio/collections.html"

class CollectionDetailView(DetailView):
    template_name = "redym_portfolio/collection_detail.html"

class DesignListView(TemplateView):
    template_name = "redym_portfolio/designs.html"

class DesignDetailView(DetailView):
    template_name = "redym_portfolio/design_detail.html"

class EventListView(TemplateView):
    template_name = "redym_portfolio/events.html"

class EventDetailView(DetailView):
    template_name = "redym_portfolio/event_detail.html"

class DesignerDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "redym_portfolio/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Ensure related records exist so templates do not error
        DesignerProfile.objects.get_or_create(user=user)

        # Ensure a subscription exists (default free trial if missing)
        if not hasattr(user, "subscription"):
            trial_end = timezone.now() + timedelta(days=7)
            UserSubscription.objects.create(
                user=user,
                plan=None,
                status="free_trial",
                payment_method=None,
                trial_end_date=trial_end,
                next_billing_date=trial_end,
            )

        # Dashboard metrics and lists
        user_designs_qs = Design.objects.filter(designer=user).order_by("-created_at")
        recent_designs = list(user_designs_qs[:8])

        context.update(
            {
                "current_section": "dashboard",
                "total_designs": user_designs_qs.count(),
                "total_collections": Collection.objects.count(),
                "total_events": Event.objects.count(),
                "user_designs": recent_designs,
                "recent_designs": recent_designs,
                "recent_collections": list(Collection.objects.order_by("-year", "name")[:5]),
            }
        )

        return context

class PendingDesignersView(ListView):
    template_name = "redym_portfolio/pending_designers.html"

# ViewSets (minimal)
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

class BrandViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response([])

class CollectionViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response([])

class DesignViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response([])

class EventViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response([])

# ---- API: Designer Registration ----
class DesignerRegistrationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        data = getattr(request, "data", {}) or {}
        username = (data.get("username") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        subscription_plan = (data.get("subscription_plan") or "").strip()
        payment_method = (data.get("payment_method") or "").strip()

        errors = {}
        if not username:
            errors["username"] = "This field is required."
        if not email:
            errors["email"] = "This field is required."
        if not password:
            errors["password"] = "This field is required."
        if User.objects.filter(username__iexact=username).exists():
            errors["username"] = "Username is already taken."
        if User.objects.filter(email__iexact=email).exists():
            errors["email"] = "Email is already registered."

        if not errors and password:
            try:
                validate_password(password)
            except ValidationError as exc:
                errors["password"] = list(exc.messages)

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user = User.objects.create_user(username=username, email=email, password=password)
            # New designer accounts are inactive until approved by admin
            user.is_active = False
            user.save()

            # Ensure a profile exists for template access patterns
            DesignerProfile.objects.get_or_create(user=user)

            # Create a default trial subscription
            trial_days = 7
            trial_end = timezone.now() + timedelta(days=trial_days)

            plan_instance = None
            if subscription_plan:
                plan_instance = SubscriptionPlan.objects.filter(name=subscription_plan, is_active=True).first()

            UserSubscription.objects.create(
                user=user,
                plan=plan_instance,
                status="free_trial",
                payment_method=payment_method if payment_method else None,
                trial_end_date=trial_end,
                next_billing_date=trial_end,
            )

            def send_registration_emails():
                # Welcome email to designer
                send_mail(
                    subject="Welcome to Redym — Designer Registration Received",
                    message=(
                        f"Hello {username},\n\n"
                        "Thanks for registering as a designer with Redym.\n"
                        "Your account is pending admin approval. We will notify you as soon as it is active.\n\n"
                        "Best,\nTeam Redym"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=True,
                )

                # Internal notification email to owner
                owner_email = getattr(settings, "ADMIN_EMAIL", None)
                if owner_email:
                    send_mail(
                        subject="New Designer Registration — Review Needed",
                        message=(
                            "A new designer has registered and is pending approval.\n\n"
                            f"Username: {username}\n"
                            f"Email: {email}\n"
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[owner_email],
                        fail_silently=True,
                    )

            transaction.on_commit(send_registration_emails)

        return Response(
            {"message": "Registration received. Your account is pending admin approval."},
            status=status.HTTP_201_CREATED,
        )
# Placeholder functions
def upload_design(request):
    return render(request, "redym_portfolio/upload_design.html", {})

def approve_designer(request, user_id):
    return JsonResponse({"status": "ok"})

def reject_designer(request, user_id):
    return JsonResponse({"status": "ok"})

def reinstate_designer(request, designer_id):
    return JsonResponse({"status": "ok"})

def designer_design_edit_view(request, design_id):
    return render(request, "redym_portfolio/designer_design_edit.html", {})

def designer_design_delete_view(request, design_id):
    return render(request, "redym_portfolio/designer_design_delete.html", {})

def designer_design_detail_api(request, design_id):
    return JsonResponse({"status": "ok"})

def subscription_dashboard(request):
    return render(request, "redym_portfolio/subscription_dashboard.html", {})

def change_subscription_plan(request):
    return JsonResponse({"status": "ok"})

def cancel_subscription(request):
    return JsonResponse({"status": "ok"})

def payment_methods(request):
    return render(request, "redym_portfolio/payment_methods.html", {})

def billing_history(request):
    return render(request, "redym_portfolio/billing_history.html", {})

def create_stripe_setup_intent(request):
    return JsonResponse({"status": "ok"})

def stripe_webhook(request):
    return JsonResponse({"status": "ok"})

def create_paypal_subscription(request):
    return JsonResponse({"status": "ok"})

def paypal_webhook(request):
    return JsonResponse({"status": "ok"})

def generate_techpack(request, slug):
    return JsonResponse({"status": "ok"})

@login_required
def dashboard_view(request):
    return render(request, "redym_portfolio/dashboard.html", {"current_section": "dashboard"})

@login_required
def designer_designs_view(request):
    # Ensure related records exist
    DesignerProfile.objects.get_or_create(user=request.user)
    if not hasattr(request.user, "subscription"):
        trial_end = timezone.now() + timedelta(days=7)
        UserSubscription.objects.create(
            user=request.user,
            plan=None,
            status="free_trial",
            payment_method=None,
            trial_end_date=trial_end,
            next_billing_date=trial_end,
        )

    designs = Design.objects.filter(designer=request.user).order_by("-created_at")
    available_years = (
        designs.values_list("year", flat=True).distinct().order_by("-year")
    )

    return render(
        request,
        "redym_portfolio/designer_designs.html",
        {
            "current_section": "designs",
            "designs": designs,
            "available_years": available_years,
        },
    )

@login_required
def designer_design_create_view(request):
    # Ensure related records exist
    DesignerProfile.objects.get_or_create(user=request.user)
    if not hasattr(request.user, "subscription"):
        trial_end = timezone.now() + timedelta(days=7)
        UserSubscription.objects.create(
            user=request.user,
            plan=None,
            status="free_trial",
            payment_method=None,
            trial_end_date=trial_end,
            next_billing_date=trial_end,
        )

    return render(
        request,
        "redym_portfolio/designer_design_create.html",
        {
            "current_section": "designs",
            "current_year": timezone.now().year,
        },
    )

@login_required
def designer_about_me_view(request):
    profile, _ = DesignerProfile.objects.get_or_create(user=request.user)
    if not hasattr(request.user, "subscription"):
        trial_end = timezone.now() + timedelta(days=7)
        UserSubscription.objects.create(
            user=request.user,
            plan=None,
            status="free_trial",
            payment_method=None,
            trial_end_date=trial_end,
            next_billing_date=trial_end,
        )

    return render(
        request,
        "redym_portfolio/designer_about_me.html",
        {"current_section": "about", "designer_profile": profile},
    )

@login_required
def designer_contact_view(request):
    profile, _ = DesignerProfile.objects.get_or_create(user=request.user)
    if not hasattr(request.user, "subscription"):
        trial_end = timezone.now() + timedelta(days=7)
        UserSubscription.objects.create(
            user=request.user,
            plan=None,
            status="free_trial",
            payment_method=None,
            trial_end_date=trial_end,
            next_billing_date=trial_end,
        )

    # Count non-empty social links for small stat
    social_links_count = sum(
        1
        for value in [
            getattr(profile, "portfolio_website", ""),
            getattr(profile, "instagram_handle", ""),
            getattr(profile, "linkedin_profile", ""),
        ]
        if value
    )

    return render(
        request,
        "redym_portfolio/designer_contact.html",
        {
            "current_section": "contact",
            "designer_profile": profile,
            "social_links_count": social_links_count,
        },
    )
