from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.utils import timezone
from datetime import timedelta
from .models import SubscriptionPlan, UserSubscription, DesignerProfile

class DesignerSignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    # Optional portfolio website URL
    website_url = forms.URLField(
        required=False,
        label="Portfolio website",
        help_text="Add your website or portfolio link (optional)",
    )

    # Subscription plan selection (by plan "name" string to match template radios)
    subscription_plan = forms.ChoiceField(
        choices=[('', 'Free Trial (1 Week)')] + SubscriptionPlan.PLAN_TYPES,
        required=False,
        widget=forms.RadioSelect,
        help_text="Start with a free trial, then choose your subscription plan"
    )

    # Payment method selection
    payment_method = forms.ChoiceField(
        choices=[('', 'Choose payment method after trial')] + UserSubscription.PAYMENT_METHODS,
        required=False,
        widget=forms.RadioSelect,
        help_text="Payment will be charged after your free trial ends"
    )

    # Terms and conditions
    agree_to_terms = forms.BooleanField(
        required=True,
        label="I agree to the Terms of Service and Privacy Policy"
    )

    # Newsletter subscription
    subscribe_newsletter = forms.BooleanField(
        required=False,
        initial=True,
        label="Subscribe to our newsletter for updates and special offers"
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "website_url",
            "password1",
            "password2",
            "subscription_plan",
            "payment_method",
            "agree_to_terms",
            "subscribe_newsletter",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add CSS classes and styling
        self.fields["username"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Enter username",
        })
        self.fields["email"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Enter email address",
        })
        self.fields["website_url"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "https://your-portfolio.example (optional)",
            "autocomplete": "url",
        })
        self.fields["password1"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Enter password",
        })
        self.fields["password2"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Confirm password",
        })

    def clean(self):
        cleaned_data = super().clean()
        plan_name = cleaned_data.get("subscription_plan") or ""
        payment_method = cleaned_data.get("payment_method") or ""

        # If a paid plan is selected, payment method should be chosen
        if plan_name and payment_method == "":
            self.add_error(
                "payment_method",
                "Please select a payment method for your chosen subscription plan.",
            )

        return cleaned_data

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "")
        # Activate designer accounts immediately
        user.is_active = True
        if commit:
            user.save()

        # Ensure a profile exists for template access patterns
        profile, _ = DesignerProfile.objects.get_or_create(user=user)

        # Persist optional website URL to profile
        website_url: str = self.cleaned_data.get("website_url") or ""
        if website_url:
            profile.portfolio_website = website_url
            profile.save()

        # Create a default trial subscription
        plan_name = self.cleaned_data.get("subscription_plan") or ""
        payment_method = self.cleaned_data.get("payment_method") or None

        trial_days = 7
        trial_end = timezone.now() + timedelta(days=trial_days)

        plan_instance = None
        if plan_name:
            plan_instance = SubscriptionPlan.objects.filter(name=plan_name, is_active=True).first()

        UserSubscription.objects.create(
            user=user,
            plan=plan_instance,
            status="free_trial",
            payment_method=payment_method if payment_method else None,
            trial_end_date=trial_end,
            next_billing_date=trial_end,
        )

        return user


class DesignerLoginForm(AuthenticationForm):
    """Custom login form that adds a Remember Me option.

    The view will read the remember_me field to control session expiry.
    """

    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        label="Keep me signed in",
        help_text="Stay signed in on this device",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Improve field widgets and placeholders
        self.fields["username"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Username or Email",
                "autocomplete": "username",
            }
        )
        self.fields["password"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Password",
                "autocomplete": "current-password",
            }
        )
        # Lightweight styling hint for remember me checkbox
        self.fields["remember_me"].widget.attrs.update({"class": "form-check-input"})


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].widget.attrs.update(
            {"class": "form-control", "placeholder": "First name"}
        )
        self.fields["last_name"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Last name"}
        )
        self.fields["email"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Email address"}
        )


class DesignerProfileForm(forms.ModelForm):
    class Meta:
        model = DesignerProfile
        fields = (
            "bio",
            "profile_image",
            "portfolio_website",
            "instagram_handle",
            "linkedin_profile",
            "years_of_experience",
            "specialization",
            "education",
            "location",
            "available_for_collaborations",
            "contact_email",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply consistent styling
        common_text_inputs = [
            "bio",
            "portfolio_website",
            "instagram_handle",
            "linkedin_profile",
            "years_of_experience",
            "specialization",
            "education",
            "location",
            "contact_email",
        ]
        for field_name in common_text_inputs:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({"class": "form-control"})

        # This screen does not edit template selection

    def clean_instagram_handle(self):
        handle = self.cleaned_data.get("instagram_handle", "").strip()
        if handle.startswith("https://") or handle.startswith("http://"):
            # If a URL is provided, try to extract the handle from the path
            # e.g. https://instagram.com/username -> username
            try:
                handle = handle.rstrip("/").split("/")[-1]
            except Exception:
                pass
        if handle.startswith("@"):
            handle = handle[1:]
        return handle
