import base64
import json

from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import TemplateView, DetailView, ListView
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login, authenticate, get_user_model
from django.http import JsonResponse
from django.views.decorators.csrf import requires_csrf_token
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from decimal import Decimal, InvalidOperation
import os
from .forms import DesignerSignUpForm, DesignerLoginForm
from .models import (
    DesignerProfile,
    SubscriptionPlan,
    UserSubscription,
    Design,
    DesignImage,
    Collection,
    Event,
    WebAuthnCredential,
)

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticationCredential,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialUserEntity,
    RegistrationCredential,
    UserVerificationRequirement,
)


def _base64url_from_bytes(value: bytes) -> str:
    if not isinstance(value, (bytes, bytearray)):
        raise TypeError("value must be bytes")
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _bytes_from_base64url(data: str) -> bytes:
    if not isinstance(data, str):
        raise TypeError("data must be str")
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _find_user_by_identifier(identifier: str):
    identifier = (identifier or "").strip()
    if not identifier:
        return None

    UserModel = get_user_model()

    try:
        return UserModel.objects.get(username__iexact=identifier)
    except UserModel.DoesNotExist:
        try:
            return UserModel.objects.get(email__iexact=identifier)
        except UserModel.DoesNotExist:
            return None

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
                    trial_end = timezone.now() + timedelta(days=30)
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
        # Provide featured designers for the homepage slideshow.
        # Currently: show the latest active designer profiles (up to 8).
        # If curation is needed later, add a boolean flag on DesignerProfile and filter by it.
        try:
            designers_qs = (
                DesignerProfile.objects.filter(user__is_active=True)
                .select_related("user")
                .order_by("-created_at")
            )
            context["designers"] = list(designers_qs[:8])
        except Exception:
            # Fallback to an empty list if the database or model is unavailable
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
                    trial_end = timezone.now() + timedelta(days=30)
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
            trial_days = 30
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
                    subject="Welcome to designer ? Your Account Is Ready",
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
                        subject="New Designer Registration ? Review Needed",
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


@login_required
@require_POST
def webauthn_register_options(request):
    user = request.user

    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (TypeError, ValueError):
        payload = {}

    nickname = (payload.get("nickname") or "").strip()

    exclude = [
        PublicKeyCredentialDescriptor(id=cred.credential_id)
        for cred in user.webauthn_credentials.all()
    ]

    selection = AuthenticatorSelectionCriteria(
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    options = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user=PublicKeyCredentialUserEntity(
            id=str(user.pk).encode("utf-8"),
            name=user.username,
            display_name=user.get_full_name() or user.username,
        ),
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=selection,
        exclude_credentials=exclude,
    )

    request.session["webauthn_registration_challenge"] = _base64url_from_bytes(options.challenge)
    request.session["webauthn_registration_nickname"] = nickname
    request.session.modified = True

    return JsonResponse(json.loads(options_to_json(options)))


@login_required
@require_POST
def webauthn_register_verify(request):
    expected_challenge = request.session.get("webauthn_registration_challenge")
    if not expected_challenge:
        return JsonResponse({"error": "missing_challenge"}, status=400)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid_payload"}, status=400)

    try:
        credential = RegistrationCredential.parse_raw(json.dumps(payload))
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": "invalid_credential", "detail": str(exc)}, status=400)

    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGIN,
            require_user_verification=True,
            allow_insecure_localhost=settings.WEBAUTHN_ALLOW_INSECURE_LOCALHOST,
        )
    except Exception as exc:  # noqa: BLE001
        request.session.pop("webauthn_registration_challenge", None)
        request.session.pop("webauthn_registration_nickname", None)
        request.session.modified = True
        return JsonResponse({"error": "registration_failed", "detail": str(exc)}, status=400)

    transports = getattr(credential.response, "transports", None) or []
    nickname = request.session.pop("webauthn_registration_nickname", "").strip()

    credential_obj, _ = WebAuthnCredential.objects.update_or_create(
        user=request.user,
        credential_id=verification.credential_id,
        defaults={
            "public_key": verification.credential_public_key,
            "sign_count": verification.sign_count,
            "transports": transports,
            "nickname": nickname,
        },
    )

    request.session.pop("webauthn_registration_challenge", None)
    request.session.modified = True

    return JsonResponse(
        {
            "status": "ok",
            "credential_id": _base64url_from_bytes(verification.credential_id),
            "credential_pk": credential_obj.pk,
        }
    )


@require_POST
def webauthn_authenticate_options(request):
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (TypeError, ValueError):
        payload = {}

    identifier = payload.get("username") or payload.get("email")
    user = _find_user_by_identifier(identifier)

    if not user or not user.is_active:
        return JsonResponse({"error": "user_not_found"}, status=404)

    credentials = list(WebAuthnCredential.objects.filter(user=user))
    if not credentials:
        return JsonResponse({"error": "no_passkeys"}, status=400)

    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=cred.credential_id)
            for cred in credentials
        ],
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    request.session["webauthn_authentication_challenge"] = _base64url_from_bytes(options.challenge)
    request.session["webauthn_authentication_user_id"] = user.pk
    request.session.modified = True

    return JsonResponse(json.loads(options_to_json(options)))


@require_POST
def webauthn_authenticate_verify(request):
    expected_challenge = request.session.get("webauthn_authentication_challenge")
    user_id = request.session.get("webauthn_authentication_user_id")

    if not expected_challenge or not user_id:
        return JsonResponse({"error": "missing_challenge"}, status=400)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid_payload"}, status=400)

    remember_me = bool(payload.get("remember_me"))
    next_url = payload.get("next") or ""

    try:
        credential = AuthenticationCredential.parse_raw(json.dumps(payload))
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": "invalid_credential", "detail": str(exc)}, status=400)

    UserModel = get_user_model()
    try:
        user = UserModel.objects.get(pk=user_id, is_active=True)
    except UserModel.DoesNotExist:
        request.session.pop("webauthn_authentication_challenge", None)
        request.session.pop("webauthn_authentication_user_id", None)
        request.session.modified = True
        return JsonResponse({"error": "user_not_found"}, status=404)

    raw_id = payload.get("rawId")
    if not raw_id:
        return JsonResponse({"error": "missing_credential_id"}, status=400)

    credential_id = _bytes_from_base64url(raw_id)

    try:
        stored_credential = WebAuthnCredential.objects.get(user=user, credential_id=credential_id)
    except WebAuthnCredential.DoesNotExist:
        return JsonResponse({"error": "credential_not_found"}, status=404)

    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGIN,
            credential_public_key=stored_credential.public_key,
            credential_current_sign_count=stored_credential.sign_count,
            require_user_verification=True,
            allow_insecure_localhost=settings.WEBAUTHN_ALLOW_INSECURE_LOCALHOST,
        )
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": "authentication_failed", "detail": str(exc)}, status=400)

    stored_credential.sign_count = verification.new_sign_count
    stored_credential.last_used_at = timezone.now()
    stored_credential.save(update_fields=["sign_count", "last_used_at", "updated_at"])

    request.session.pop("webauthn_authentication_challenge", None)
    request.session.pop("webauthn_authentication_user_id", None)
    request.session.modified = True

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")

    if remember_me:
        session_age_seconds = getattr(settings, "REMEMBER_ME_SESSION_AGE", 60 * 60 * 24 * 30)
        request.session.set_expiry(session_age_seconds)
    else:
        request.session.set_expiry(0)

    redirect_to = settings.LOGIN_REDIRECT_URL
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        redirect_to = next_url

    return JsonResponse({"status": "ok", "redirect_url": redirect_to})


@login_required
@require_POST
def webauthn_delete_credential(request, credential_id):
    try:
        credential = request.user.webauthn_credentials.get(pk=credential_id)
    except WebAuthnCredential.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)

    credential.delete()
    return JsonResponse({"status": "ok"})
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

@login_required
def designer_design_detail_api(request, design_id):
    design = get_object_or_404(Design, id=design_id, designer=request.user)

    gallery = [
        {
            "id": image.id,
            "url": image.image.url,
            "caption": image.caption or "",
        }
        for image in design.images.order_by("order", "created_at")
    ]

    data = {
        "id": design.id,
        "title": design.title,
        "description": design.description or "",
        "season": design.season or "",
        "year": design.year,
        "is_public": design.published,
        "is_featured": False,
        "cover_image_url": design.cover_image.url if design.cover_image else "",
        "fabric_type": design.fabric_details or "",
        "target_price": str(design.target_price) if design.target_price is not None else "",
        "color_palette": design.color_palette or "",
        "size_range": design.size_range or "",
        "techpack_pdf_url": design.techpack_pdf.url if design.techpack_pdf else "",
        "techpack_excel_url": design.techpack_excel.url if design.techpack_excel else "",
        "design_notes": design.production_notes or "",
        "created_at": design.created_at.isoformat(),
        "updated_at": design.updated_at.isoformat(),
        "edit_url": reverse("designer_design_edit", args=[design.id]),
        "gallery": gallery,
        "category": "",
    }

    return JsonResponse(data)

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
        trial_end = timezone.now() + timedelta(days=30)
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
        trial_end = timezone.now() + timedelta(days=30)
        UserSubscription.objects.create(
            user=request.user,
            plan=None,
            status="free_trial",
            payment_method=None,
            trial_end_date=trial_end,
            next_billing_date=trial_end,
        )

    if request.method == "POST":
        form_values = request.POST
        files = request.FILES
        errors = []

        title = (form_values.get("title") or "").strip()
        season = (form_values.get("season") or "").strip()
        slug_value = (form_values.get("slug") or "").strip()
        year_raw = (form_values.get("year") or "").strip()

        if not title:
            errors.append("Design title is required.")

        if not season:
            errors.append("Season is required.")

        try:
            year = int(year_raw) if year_raw else timezone.now().year
        except ValueError:
            errors.append("Year must be a valid number.")
            year = timezone.now().year

        target_price = None
        target_price_raw = (form_values.get("target_price") or "").strip()
        if target_price_raw:
            try:
                target_price = Decimal(target_price_raw)
            except InvalidOperation:
                errors.append("Target price must be a valid number.")

        techpack_file = files.get("techpack_file")
        techpack_pdf = None
        techpack_excel = None
        if techpack_file:
            ext = os.path.splitext(techpack_file.name)[1].lower()
            if ext == ".pdf":
                techpack_pdf = techpack_file
            elif ext in {".xls", ".xlsx"}:
                techpack_excel = techpack_file
            else:
                errors.append("Tech pack must be a PDF or Excel file.")

        if errors:
            for error in errors:
                messages.error(request, error)
            if request.headers.get("x-requested-with", "").lower() == "xmlhttprequest":
                return JsonResponse({"status": "error", "errors": errors}, status=400)
            context = {
                "current_section": "designs",
                "current_year": timezone.now().year,
                "form_values": form_values.dict(),
            }
            return render(
                request,
                "designer_portfolio/designer_design_create.html",
                context,
            )

        published_flag = str(form_values.get("published", "")).lower()
        published = published_flag in {"true", "1", "on"}
        is_draft = not published

        fabric_type = (form_values.get("fabric_type") or "").strip()
        color_palette = (form_values.get("color_palette") or "").strip()
        size_range = (form_values.get("size_range") or "").strip()
        description = (form_values.get("description") or "").strip()
        technical_notes = (form_values.get("technical_notes") or "").strip()
        fabric_weight = (form_values.get("fabric_weight") or "").strip()
        target_market = (form_values.get("target_market") or "").strip()
        category = (form_values.get("category") or "").strip()

        production_notes_parts = []
        if technical_notes:
            production_notes_parts.append(technical_notes)
        if fabric_weight:
            production_notes_parts.append(f"Fabric weight: {fabric_weight}")
        if target_market:
            production_notes_parts.append(f"Target market: {target_market}")
        if category:
            production_notes_parts.append(f"Category: {category}")

        production_notes = "\n\n".join(production_notes_parts).strip()

        cover_image = files.get("cover_image")

        with transaction.atomic():
            design = Design(
                title=title,
                season=season,
                year=year,
                designer=request.user,
                description=description,
                published=published,
                fabric_details=fabric_type,
                color_palette=color_palette,
                size_range=size_range,
                target_price=target_price,
                production_notes=production_notes,
            )

            if slug_value:
                design.slug = slug_value

            if cover_image:
                design.cover_image = cover_image

            if techpack_pdf:
                design.techpack_pdf = techpack_pdf

            if techpack_excel:
                design.techpack_excel = techpack_excel

            design.save()

            additional_images = files.getlist("additional_images")
            for order, image_file in enumerate(additional_images):
                DesignImage.objects.create(
                    design=design,
                    image=image_file,
                    order=order,
                )

        success_message = "Draft saved successfully." if is_draft else "Design uploaded successfully."
        messages.success(request, success_message)

        if request.headers.get("x-requested-with", "").lower() == "xmlhttprequest":
            return JsonResponse(
                {
                    "status": "ok",
                    "redirect_url": reverse("designer_designs"),
                    "design_id": design.id,
                    "message": success_message,
                    "draft": is_draft,
                }
            )

        return redirect("designer_designs")

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
    user = request.user
    profile, _ = DesignerProfile.objects.get_or_create(user=user)

    # Ensure a subscription record exists (for templates using it)
    if not hasattr(user, "subscription"):
        trial_end = timezone.now() + timedelta(days=30)
        UserSubscription.objects.create(
            user=user,
            plan=None,
            status="free_trial",
            payment_method=None,
            trial_end_date=trial_end,
            next_billing_date=trial_end,
        )

    passkeys = list(user.webauthn_credentials.order_by("created_at"))

    if request.method == "POST":
        # Update basic user fields
        first_name = (request.POST.get("first_name") or user.first_name).strip()
        last_name = (request.POST.get("last_name") or user.last_name).strip()
        email = (request.POST.get("email") or user.email).strip()

        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.save()

        # Update profile fields (map template inputs to model fields)
        profile.bio = request.POST.get("bio", profile.bio)
        profile.location = request.POST.get("location", profile.location)
        profile.education = request.POST.get("education", profile.education)
        # years_of_experience may be empty; coerce safely
        years_val = request.POST.get("years_of_experience", "").strip()
        try:
            profile.years_of_experience = int(years_val) if years_val != "" else profile.years_of_experience
        except ValueError:
            # leave unchanged on bad input
            pass

        # Social/portfolio links
        profile.portfolio_website = request.POST.get("portfolio_website", request.POST.get("website", profile.portfolio_website))
        profile.instagram_handle = request.POST.get("instagram_handle", request.POST.get("instagram", profile.instagram_handle))
        profile.linkedin_profile = request.POST.get("linkedin_profile", request.POST.get("linkedin", profile.linkedin_profile))
        profile.specialization = request.POST.get("specialization", request.POST.get("specializations", profile.specialization))
        profile.contact_email = request.POST.get("contact_email", profile.contact_email)

        # Collaboration preference (support old and corrected field names)
        available_flag = request.POST.get("available_for_collaborations") or request.POST.get("available_for_collaboration")
        profile.available_for_collaborations = bool(available_flag)

        # Handle profile image upload
        if "profile_image" in request.FILES:
            profile.profile_image = request.FILES["profile_image"]

        profile.save()

        messages.success(request, "Your profile was updated successfully.")
        return redirect("designer_about_me")

    # Stats for header widgets
    try:
        total_designs = Design.objects.filter(designer=user).count()
    except Exception:
        total_designs = 0

    return render(
        request,
        "designer_portfolio/designer_about_me.html",
        {
            "current_section": "about",
            "designer_profile": profile,
            "total_designs": total_designs,
            "passkeys": passkeys,
        },
    )

@login_required
def designer_contact_view(request):
    profile, _ = DesignerProfile.objects.get_or_create(user=request.user)
    if not hasattr(request.user, "subscription"):
        trial_end = timezone.now() + timedelta(days=30)
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


# --- Security/Errors ---
@requires_csrf_token
def csrf_failure(request, reason=""):
    """Custom handler for CSRF failures.

    Returns JSON for AJAX/JSON requests and a friendly HTML page otherwise.
    """
    accepts_header = (request.headers.get("Accept") or "").lower()
    is_ajax = (request.headers.get("x-requested-with") or "").lower() == "xmlhttprequest"
    wants_json = "application/json" in accepts_header

    if is_ajax or wants_json:
        payload = {
            "error": "csrf_failed",
            "message": "Your session expired or the form is stale. Please refresh the page and try again.",
        }
        if settings.DEBUG:
            payload["reason"] = reason or ""
        return JsonResponse(payload, status=403)

    context = {
        "reason": reason or "",
        "debug": settings.DEBUG,
    }
    return render(request, "errors/403_csrf.html", context=context, status=403)
