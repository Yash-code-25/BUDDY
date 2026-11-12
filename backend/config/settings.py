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

def env_flag(name, default):
    return os.environ.get(name, default).strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name):
    return [item.strip() for item in os.environ.get(name, '').split(',') if item.strip()]


# Live (e.g. on Vercel) these come from the host's environment variables. Without them, COMPASS runs
# as the development setup on a laptop: a development key, DEBUG on, localhost only.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or 'django-insecure-4_$x-ck&b$!*5d+8z-h3=ll68fwi==55sf%cr*nsa&h$42w-+('
DEBUG = env_flag('DJANGO_DEBUG', 'True')

# The addresses COMPASS answers on, e.g. "compass.united-group.in,.vercel.app". Empty means localhost
# only (fine while DEBUG is on).
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS')

# Sites allowed to send forms (sign in, save). The live addresses over HTTPS, plus `npm run dev`
# (Vite on port 5173) for editing the screens on a laptop.
CSRF_TRUSTED_ORIGINS = ['http://localhost:5173', 'http://127.0.0.1:5173'] + [
    f"https://{'*' + host if host.startswith('.') else host}" for host in ALLOWED_HOSTS
]

if not DEBUG:
    # Behind the host's HTTPS: trust its "this was HTTPS" header, and send cookies over HTTPS only.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# On Vercel each request runs in a short-lived function (the VERCEL variable is set there).
ON_VERCEL = bool(os.environ.get('VERCEL'))

# Email. With no EMAIL_USER in backend/.env, emails are printed in the terminal running `runserver`
# instead of sent (see MAILERS further down). With it, they are sent through that mail account.
DEFAULT_FROM_EMAIL = f"Team United <{os.environ.get('EMAIL_USER') or 'compass@united-group.local'}>"
# Never email these domains: the demo people's addresses are made up (see seed_demo).
EMAIL_SKIP_DOMAINS = ['test.com']
ALERT_EMAIL = 'compass-admin@united-group.local'  # alerts go here when no Program admin has an email
# The base address used in links inside emails, e.g. https://compass.united-group.in when live.
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:8000').rstrip('/')
# Vercel's daily cron calls /api/cron/daily/ with this secret; without it the address refuses everyone.
CRON_SECRET = os.environ.get('CRON_SECRET', '')

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
    'whitenoise.middleware.WhiteNoiseMiddleware',  # serves the Django admin's styles when live
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
            # A normal server reuses a connection for a minute; a Vercel function closes it after each
            # request, because many short-lived functions would otherwise hold too many open.
            conn_max_age=0 if ON_VERCEL else 60,
            conn_health_checks=True,  # check a reused connection is still alive before using it
            ssl_require=True,         # Supabase only accepts encrypted connections
        ),
    }
    # Supabase's "Transaction pooler" (port 6543, the one to use on Vercel) cannot keep server-side
    # cursors between statements.
    if DATABASES['default'].get('PORT') in (6543, '6543'):
        DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True
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
# The Django admin's styles. WhiteNoise serves them straight from the installed apps, so no
# collectstatic step is needed on the host. (The React screens are separate, in frontend/dist.)
WHITENOISE_USE_FINDERS = True

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
