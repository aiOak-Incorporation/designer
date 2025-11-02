from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.utils import timezone
from datetime import timedelta
from .models import SubscriptionPlan, UserSubscription, DesignerProfile, Design


class DesignUploadForm(forms.ModelForm):
    SEASON_CHOICES = [
        ("Spring", "Spring"),
        ("Summer", "Summer"),
        ("Fall", "Fall"),
        ("Winter", "Winter"),
        ("Resort", "Resort"),
        ("Pre-Fall", "Pre-Fall"),
    ]

    season = forms.ChoiceField(choices=[("", "Select Season")] + SEASON_CHOICES)
    published = forms.BooleanField(required=False, initial=True)

    class Meta:
        model = Design
        fields = [
            "title",
            "season",
            "year",
            "description",
            "cover_image",
            "color_palette",
            "size_range",
            "target_price",
            "fabric_details",
            "production_notes",
            "published",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "fabric_details": forms.Textarea(attrs={"rows": 3}),
            "production_notes": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_year(self):
        year = self.cleaned_data.get("year")
        if year and (year < 1900 or year > 2100):
            raise forms.ValidationError("Please enter a valid year.")
        return year

    def clean_season(self):
        season = self.cleaned_data.get("season")
        if not season:
            raise forms.ValidationError("Please choose a season.")
        return season

    def clean_target_price(self):
        value = self.cleaned_data.get("target_price")
        if value is not None and value < 0:
            raise forms.ValidationError("Target price cannot be negative.")
        return value

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
        choices=[("", "Free Trial (until you're ready)")] + SubscriptionPlan.PLAN_TYPES,
        required=False,
        widget=forms.RadioSelect,
        help_text="Feel free to upload designs and pick a subscription plan whenever you're satisfied."
    )

    # Payment method selection
    payment_method = forms.ChoiceField(
        choices=[("", "Choose payment method when you upgrade")] + UserSubscription.PAYMENT_METHODS,
        required=False,
        widget=forms.RadioSelect,
        help_text="Set up payment details only when you decide to upgrade from the free trial."
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

        trial_days = 30
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
