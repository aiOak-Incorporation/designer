@echo off
REM Local development server script
REM This sets the correct environment variables for local development

set DEBUG=True
set SECRET_KEY=P;35^4+cV=@*kXYexh==?wyH}a8b6k01H#,CUZ<X1PEFzmMqy%
set SECURE_SSL_REDIRECT=False
set SESSION_COOKIE_SECURE=False
set CSRF_COOKIE_SECURE=False
set SOCIAL_AUTH_REDIRECT_IS_HTTPS=False

echo Starting Django development server with local settings...
echo Access your site at: http://127.0.0.1:8000
echo NOTE: Use HTTP (not HTTPS) to avoid SSL protocol errors!
python manage.py runserver