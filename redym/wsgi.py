import os
from django.core.wsgi import get_wsgi_application

# Tell Django which settings file to use
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "redym.settings")

# The WSGI application Django’s servers (and Gunicorn) use
application = get_wsgi_application()
