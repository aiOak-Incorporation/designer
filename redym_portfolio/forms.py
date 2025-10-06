from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import SubscriptionPlan, UserSubscription

class DesignerSignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    # Subscription plan selection
    subscription_plan = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.filter(is_active=True),
        required=False,
        empty_label="Free Trial (1 Week)",
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
        fields = ("username", "email", "password1", "password2", "subscription_plan", 
                 "payment_method", "agree_to_terms", "subscribe_newsletter")
        
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)
        
        # Add CSS classes and styling
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter username'
        })
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter email address'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
        
        # Add help text for subscription plans
        for plan in SubscriptionPlan.objects.filter(is_active=True):
            help_text = f"${plan.price} every {plan.get_name_display().lower()}"
            if plan.name == 'yearly':
                help_text += " (Best Value - Save 58%!)"
            elif plan.name == '6months':
                help_text += " (Save 20%!)"
            plan.help_text = help_text
    
    def clean(self):
        cleaned_data = super().clean()
        subscription_plan = cleaned_data.get('subscription_plan')
        payment_method = cleaned_data.get('payment_method')
        
        # If a paid plan is selected, payment method should be chosen
        if subscription_plan and not payment_method:
            self.add_error('payment_method', 
                          'Please select a payment method for your chosen subscription plan.')
        
        return cleaned_data
    