from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from datetime import timedelta
from .models import SubscriptionPlan, UserSubscription, DesignerProfile

class DesignerSignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

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
        # New designer accounts are inactive until approved by admin
        user.is_active = False
        if commit:
            user.save()

        # Ensure a profile exists for template access patterns
        DesignerProfile.objects.get_or_create(user=user)

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
