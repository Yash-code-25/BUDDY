import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Secrets such as the email password go in backend/.env (never committed), one NAME=value a line.
# backend/.env.example lists them.
if (BASE_DIR / '.env').exists():
    for line in (BASE_DIR / '.env').read_text(encoding='utf-8').splitlines():
        name, sep, value = line.partition('=')
        if sep and not line.lstrip().startswith('#'):
            os.environ.setdefault(name.strip(), value.strip())

# Development settings - unsuitable for production

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-4_$x-ck&b$!*5d+8z-h3=ll68fwi==55sf%cr*nsa&h$42w-+('

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Only needed if you use `npm run dev` (Vite on port 5173) to edit the screens. It proxies /api to Django,
# so its origin must be trusted for POSTs. Normal use is one server on port 8000 and needs none of this.
CSRF_TRUSTED_ORIGINS = ['http://localhost:5173', 'http://127.0.0.1:5173']

# Email. With no EMAIL_USER in backend/.env, emails are printed in the terminal running `runserver`
# instead of sent (see MAILERS further down). With it, they are sent through that mail account.
DEFAULT_FROM_EMAIL = f"Team United <{os.environ.get('EMAIL_USER') or 'compass@united-group.local'}>"
# Never email these domains: the demo people's addresses are made up (see seed_demo).
EMAIL_SKIP_DOMAINS = ['test.com']
ALERT_EMAIL = 'compass-admin@united-group.local'  # alerts go here when no Program admin has an email
FRONTEND_URL = 'http://localhost:8000'     # base address used in links inside emails

# Development only: a list of every joiner and buddy under the login form, signing them in with one
# click (no login code). It follows DEBUG, so it is off in production. Never set it True there.
DEMO_SIGN_IN = DEBUG

# Django serves the built React app from here, so `runserver` alone runs the whole application.
FRONTEND_DIST = BASE_DIR.parent / 'frontend' / 'dist'

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'compass_app',
    'hr_portal',
    'notifications',
    'feedback',
    'employee_portal',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'config.middleware.never_cache_api',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database. With DATABASE_URL in backend/.env (e.g. Supabase's "Session pooler" connection string),
# COMPASS uses that PostgreSQL database; without it, the SQLite file next to manage.py. Tests always
# use their own throwaway SQLite database, so they never touch the real one.
SQLITE = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}
if os.environ.get('DATABASE_URL') and 'test' not in sys.argv:
    import dj_database_url

    DATABASES = {
        'default': dj_database_url.parse(
            os.environ['DATABASE_URL'],
            conn_max_age=60,          # reuse a connection for a minute instead of opening one per request
            conn_health_checks=True,  # and check it is still alive before using it
            ssl_require=True,         # Supabase only accepts encrypted connections
        ),
    }
else:
    DATABASES = {'default': SQLITE}

# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)

STATIC_URL = 'static/'

# Sign-in attempts per minute from one address. Login codes are short, so guessing must be slow.
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_RATES': {'login': '10/minute'},
}

# The test run: a fast password hasher (hashing login codes for real is slow on purpose), and a
# sign-in limit the many test logins never hit. One test checks the real limit on its own.
if 'test' in sys.argv:
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['login'] = '10000/minute'

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}
if os.environ.get('EMAIL_USER') and 'test' not in sys.argv:
    MAILERS['default'] = {
        'BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
        'OPTIONS': {
            'host': os.environ.get('EMAIL_HOST', 'smtp.gmail.com'),
            'port': int(os.environ.get('EMAIL_PORT', '587')),
            'username': os.environ['EMAIL_USER'],
            'password': os.environ.get('EMAIL_PASSWORD', ''),
            'use_tls': True,
            'timeout': 20,
        },
    }
