from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.auth import views as auth_views
from redym_portfolio.views import signup_view  # Import the signup_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/password_reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("accounts/", include("django.contrib.auth.urls")),  # includes reset/confirm/complete routes
    path("accounts/signup/", signup_view, name="signup"),
    path("", include("redym_portfolio.urls")),  # your app
]