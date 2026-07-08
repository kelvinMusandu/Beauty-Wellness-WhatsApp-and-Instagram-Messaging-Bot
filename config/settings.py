# Python's standard library module for interacting with the operating system
# reading environment variables like DJANGO_SECRET_KEY or WHATSAPP_VERIFY_TOKEN, 
# with a fallback default if that variable isn't set.
import os 
# Modern, object-oriented way to handle filesystem paths 
# (replacing older string-based os.path operations). Used at 
from pathlib import Path
# reads a .env
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Meta sends this in the GET verification request — must match what you set
# in the Meta developer dashboard when registering the webhook URL.
WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', '')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'webhooks',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


"""
My notes:

Settings.py - this is the hub of the project which controls how the app runs
all apps are registered here. 
In this projects case we have: webhooks app. All tokens are saved here as well. In 
this case we have WHATSAPP_VERIFY_TOKEN which is a critical piece of Whatsapp Integration
when registering a webhook URL on the Meta Developer Dashboard. Meta sends a Get request
for verification and it must match this value during the request.
load_dotenv is used to load secrets from the .env file. Secrets such as DJANGO_SECRET_KEY, 
DEBUG, ALLOWED_HOSTS, and WHATSAPP_VERIFY_TOKEN, DATABASE information
are stored in .env


A Django project can be compartmentalised into apps. There can therefore be one mother app
that carries all of the settings/controls in settings.py that are used across the project
and this is where apps are registered. Other things like Security config, middleware order, 
timezone, static files can also be found here. Then that apps settings.py is saved in manage.py 
or wsgi.py as DJANGO_SETTINGS_MODULE to be used globally.

Apps then access the settings by pulling from the mother app using
from django.conf import settings
to access for example WHATSAPP_VERIFY_TOKEN using
settings.WHATSAPP_VERIFY_TOKEN


WSGI Web Server Gateway Interface is a protocol that defines how web servers communicate
with Python web applications. ASGI Asynchronous Server Gateway Interface is the official 
standard for connecting asynchronous Python web servers, frameworks and applications

Synchronous operations happen in real-time or sequentially, meaning an action waits for the 
previous one to finish before moving on. Asynchronous operations happen independently; tasks
are triggered, but the system continues other work without waiting for an immediate response

Why it matters for a WhatsApp bot specifically:

If the app just receives a webhook POST, does some sync work (hit a DB, maybe call an LLM API),
and responds — plain WSGI is perfectly fine and simpler to deploy.
If you ever want to do things like hold a connection open, stream responses, or make concurrent 
outbound calls (calling Meta's Graph API without blocking each other)
efficiently under load, ASGI + async views become useful.

Concurrency bottlenecks occur when multiple threads or processes compete for shared resources,
causing system slowdowns instead of performance gains. Common culprits include excessive
lock contention (threads waiting on locks), I/O blocking, and context switching
"""