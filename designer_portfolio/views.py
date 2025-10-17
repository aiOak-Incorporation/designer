from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import TemplateView, DetailView, ListView
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login, authenticate
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from .forms import (
    DesignerSignUpForm,
    DesignerLoginForm,
    UserUpdateForm,
    DesignerProfileForm,
)
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
        # Attempt to restore an existing but inactive account based on username/email
        desired_username = (request.POST.get("username") or "").strip()
        email_input = (request.POST.get("email") or "").strip().lower()
        website_url = (request.POST.get("website_url") or "").strip()
        password1 = request.POST.get("password1") or ""
        password2 = request.POST.get("password2") or ""

        if password1 and password1 == password2:
            inactive_user = (
                User.objects.filter(
                    Q(is_active=False),
                    Q(username__iexact=desired_username) | Q(email__iexact=email_input),
                )
                .order_by("id")
                .first()
            )

            if inactive_user is not None:
                # Validate password strength before restoring
                try:
                    validate_password(password1, user=inactive_user)
                except ValidationError as exc:
                    form = DesignerSignUpForm(request.POST)
                    form.add_error("password1", exc)
                    messages.error(request, "Please correct the errors below.")
                    return render(request, "registration/signup.html", {"form": form})

                # Restore user account
                inactive_user.is_active = True
                if email_input:
                    inactive_user.email = email_input
                inactive_user.set_password(password1)
                inactive_user.save()

                # Ensure related records exist
                profile, _ = DesignerProfile.objects.get_or_create(user=inactive_user)
                # Persist optional website URL if valid
                if website_url:
                    try:
                        URLValidator()(website_url)
                        profile.portfolio_website = website_url
                        profile.save()
                    except ValidationError:
                        # Ignore invalid URL in restore path; do not block restore
                        pass
                if not hasattr(inactive_user, "subscription"):
                    trial_end = timezone.now() + timedelta(days=7)
                    UserSubscription.objects.create(
                        user=inactive_user,
                        plan=None,
                        status="free_trial",
                        payment_method=None,
                        trial_end_date=trial_end,
                        next_billing_date=trial_end,
                    )

                # Log the user in using identifier they provided (email or username)
                user_identifier = email_input or desired_username
                user_auth = authenticate(request, username=user_identifier, password=password1)
                if user_auth is not None and user_auth.is_active:
                    login(request, user_auth)
                    return redirect("designer_dashboard")

                messages.success(request, "Account restored. Please log in.")
                return redirect("login")

        # Fall back to normal signup flow
        form = DesignerSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            raw_password = form.cleaned_data.get("password1")
            user_auth = authenticate(request, username=user.username, password=raw_password)
            if user_auth is not None and user_auth.is_active:
                login(request, user_auth)
                return redirect("designer_dashboard")
            messages.success(request, "Account created. Please log in.")
            return redirect("login")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = DesignerSignUpForm()

    return render(request, "registration/signup.html", {"form": form})

# Basic view classes for URL compatibility
class HomePageView(TemplateView):
    template_name = "designer_portfolio/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Temporarily simplified to avoid potential model issues
        context["designers"] = []
        return context

class AboutView(TemplateView):
    template_name = "designer_portfolio/about.html"

class AboutSiteView(TemplateView):
    template_name = "designer_portfolio/about_site.html"

class CollectionsPageView(TemplateView):
    template_name = "designer_portfolio/collections.html"

class CollectionDetailView(DetailView):
    template_name = "designer_portfolio/collection_detail.html"

class DesignListView(TemplateView):
    template_name = "designer_portfolio/designs.html"

class DesignDetailView(DetailView):
    template_name = "designer_portfolio/design_detail.html"
class EventListView(TemplateView):
    template_name = "designer_portfolio/events.html"
class EventDetailView(DetailView):
    template_name = "designer_portfolio/event_detail.html"
class DesignerDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "designer_portfolio/designer_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Simplified dashboard to avoid potential issues
        try:
            user_designs_qs = Design.objects.filter(designer=user).order_by("-created_at")
            recent_designs = list(user_designs_qs[:8])
            total_designs = user_designs_qs.count()
        except Exception as e:
            # Fallback if there's an issue with Design model
            recent_designs = []
            total_designs = 0

        try:
            total_collections = Collection.objects.count()
        except Exception as e:
            total_collections = 0

        try:
            total_events = Event.objects.count()
        except Exception as e:
            total_events = 0

        try:
            recent_collections = list(Collection.objects.order_by("-year", "name")[:5])
        except Exception as e:
            recent_collections = []

        context.update(
            {
                "current_section": "dashboard",
                "total_designs": total_designs,
                "total_collections": total_collections,
                "total_events": total_events,
                "user_designs": recent_designs,
                "recent_designs": recent_designs,
                "recent_collections": recent_collections,
            }
        )

        return context

class PendingDesignersView(ListView):
    template_name = "designer_portfolio/pending_designers.html"

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
        website_url = (data.get("website_url") or data.get("portfolio_website") or "").strip()
        subscription_plan = (data.get("subscription_plan") or "").strip()
        payment_method = (data.get("payment_method") or "").strip()

        # If a previously registered but inactive user exists, restore their account
        if email or username:
            inactive_user = (
                User.objects.filter(
                    Q(is_active=False), Q(username__iexact=username) | Q(email__iexact=email)
                )
                .order_by("id")
                .first()
            )
            if inactive_user is not None:
                errors = {}
                if not password:
                    errors["password"] = "This field is required."
                else:
                    try:
                        validate_password(password, user=inactive_user)
                    except ValidationError as exc:
                        errors["password"] = list(exc.messages)

                if errors:
                    return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

                inactive_user.is_active = True
                if email:
                    inactive_user.email = email
                inactive_user.set_password(password)
                inactive_user.save()

                # Ensure related records
                profile, _ = DesignerProfile.objects.get_or_create(user=inactive_user)
                if website_url:
                    try:
                        URLValidator()(website_url)
                        profile.portfolio_website = website_url
                        profile.save()
                    except ValidationError:
                        pass
                if not hasattr(inactive_user, "subscription"):
                    trial_end = timezone.now() + timedelta(days=7)
                    plan_instance = None
                    if subscription_plan:
                        plan_instance = SubscriptionPlan.objects.filter(
                            name=subscription_plan, is_active=True
                        ).first()
                    UserSubscription.objects.create(
                        user=inactive_user,
                        plan=plan_instance,
                        status="free_trial",
                        payment_method=payment_method if payment_method else None,
                        trial_end_date=trial_end,
                        next_billing_date=trial_end,
                    )

                return Response(
                    {"message": "Account restored. You can now sign in."},
                    status=status.HTTP_200_OK,
                )

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
            # Activate designer accounts immediately
            user.is_active = True
            user.save()

            # Ensure a profile exists for template access patterns
            profile, _ = DesignerProfile.objects.get_or_create(user=user)
            if website_url:
                try:
                    URLValidator()(website_url)
                    profile.portfolio_website = website_url
                    profile.save()
                except ValidationError:
                    pass

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
                    subject="Welcome to designer — Your Account Is Ready",
                    message=(
                        f"Hello {username},\n\n"
                        "Thanks for registering as a designer with designer.\n"
                        "Your account is now active. You can sign in and access your dashboard immediately.\n\n"
                        "Best,\nTeam designer"
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
            {"message": "Registration successful. You can now sign in."},
            status=status.HTTP_201_CREATED,
        )
# Placeholder functions
def upload_design(request):
    return render(request, "designer_portfolio/upload_design.html", {})

def approve_designer(request, user_id):
    return JsonResponse({"status": "ok"})

def reject_designer(request, user_id):
    return JsonResponse({"status": "ok"})

def reinstate_designer(request, designer_id):
    return JsonResponse({"status": "ok"})

def designer_design_edit_view(request, design_id):
    return render(request, "designer_portfolio/designer_design_edit.html", {})

def designer_design_delete_view(request, design_id):
    return render(request, "designer_portfolio/designer_design_delete.html", {})

def designer_design_detail_api(request, design_id):
    return JsonResponse({"status": "ok"})

def subscription_dashboard(request):
    return render(request, "designer_portfolio/subscription_dashboard.html", {})

def change_subscription_plan(request):
    return JsonResponse({"status": "ok"})

def cancel_subscription(request):
    return JsonResponse({"status": "ok"})

def payment_methods(request):
    return render(request, "designer_portfolio/payment_methods.html", {})

def billing_history(request):
    return render(request, "designer_portfolio/billing_history.html", {})

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
    return render(request, "designer_portfolio/dashboard.html", {"current_section": "dashboard"})

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
        "designer_portfolio/designer_designs.html",
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
        "designer_portfolio/designer_design_create.html",
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

    if request.method == "POST":
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = DesignerProfileForm(request.POST, request.FILES, instance=profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("designer_about_me")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = DesignerProfileForm(instance=profile)

    return render(
        request,
        "designer_portfolio/designer_about_me.html",
        {
            "current_section": "about",
            "designer_profile": profile,
            "user_form": user_form,
            "profile_form": profile_form,
        },
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

    if request.method == "POST":
        # Update basic user email
        request.user.email = request.POST.get("email", request.user.email)
        request.user.save(update_fields=["email"])

        # Update allowed profile fields
        updatable = {
            "location": request.POST.get("location", profile.location or ""),
            "portfolio_website": request.POST.get("website", profile.portfolio_website or ""),
            "instagram_handle": request.POST.get("instagram", profile.instagram_handle or ""),
            "linkedin_profile": request.POST.get("linkedin", profile.linkedin_profile or ""),
            "contact_email": request.POST.get("email", profile.contact_email or ""),
            "available_for_collaborations": "available_for_collaboration" in request.POST
            or "available_for_collaborations" in request.POST,
        }
        for field_name, value in updatable.items():
            setattr(profile, field_name, value)
        try:
            profile.save()
            messages.success(request, "Contact information updated.")
        except Exception:
            messages.error(request, "Unable to save contact information.")

        return redirect("designer_contact")

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
        "designer_portfolio/designer_contact.html",
        {
            "current_section": "contact",
            "designer_profile": profile,
            "social_links_count": social_links_count,
        },
    )

from django.contrib.auth import logout
def logout_view(request):
    logout(request)
    return redirect('home')

class DesignersListView(ListView):
    model = DesignerProfile
    template_name = "designer_portfolio/designers.html"
    context_object_name = "designers"
    paginate_by = 20

    def get_queryset(self):
        # Only return profiles for active users
        return DesignerProfile.objects.filter(
            user__is_active=True
        ).select_related('user').order_by('-created_at')


class DesignerLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = DesignerLoginForm

    def form_valid(self, form):
        response = super().form_valid(form)
        remember_me = form.cleaned_data.get("remember_me")

        # Control session expiry based on remember_me
        # When remember_me is True, use a longer session age; otherwise expire at browser close
        if remember_me:
            # Use custom setting if provided; fallback to 30 days
            session_age_seconds = getattr(settings, "REMEMBER_ME_SESSION_AGE", 60 * 60 * 24 * 30)
            self.request.session.set_expiry(session_age_seconds)
        else:
            # 0 = expire at browser close
            self.request.session.set_expiry(0)

        return response
