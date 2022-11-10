"""
Django settings for api_main project.

Generated by 'django-admin startproject' using Django 3.1.5.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""
import os
import json
import random
import string
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

# This should read in variables stored in the env files of the parent
# directores. While developing outside of the container you can place
# development values for the variables in the .env file next to
# docker-compose.yml which then will be used as environment variables here.
load_dotenv(find_dotenv(), verbose=False, override=True)

# ------------------------------------------------------------------------------
# Global flags that determine the functionality provided by the API service.
# ------------------------------------------------------------------------------

ACTIVATE_CONTROL_EXTENSION = False
if (os.getenv("ACTIVATE_CONTROL_EXTENSION") or "FALSE").lower() == "true":
    ACTIVATE_CONTROL_EXTENSION = True

ACTIVATE_HISTORY_EXTENSION = False
if (os.getenv("ACTIVATE_HISTORY_EXTENSION") or "FALSE").lower() == "true":
    ACTIVATE_HISTORY_EXTENSION = True

# ------------------------------------------------------------------------------
# Settings for mqtt_integration.py
# ------------------------------------------------------------------------------

# Load custom configuration variables from environment variable
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT") or 1883)
N_MTD_WRITE_THREADS = int(os.getenv("N_MTD_WRITE_THREADS") or 1)

# Settings for connection to MQTT broker.
MQTT_BROKER = {"host": MQTT_BROKER_HOST, "port": MQTT_BROKER_PORT}

# ------------------------------------------------------------------------------
# Here settings that configure Django itself.
# ------------------------------------------------------------------------------

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
if not os.getenv("DJANGO_SECRET_KEY"):
    # This generates a new random key every time we start the application or
    # run anything from manage.py. This also invalidates all cookies which
    # makes users login again. Thus, it is a good idea to fix the key in
    # production.
    # However, this only works if we have only a single worker. If there are
    # more then one, each will get a dedicated SECRET_KEY which will cause
    # permanent suspicious session warnings.
    if int(os.getenv("N_WORKER_PROCESSES") or 1) == 1:
        SECRET_KEY = "".join(
            random.choice(string.ascii_letters) for i in range(64)
        )
    else:
        raise ValueError(
            "DJANGO_SECRET_KEY must be set explicitly if django-api is "
            "run with N_WORKER_PROCESSES > 1."
        )
else:
    SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False
if (os.getenv("DJANGO_DEBUG") or "FALSE").lower() == "true":
    DEBUG = True

ALLOWED_HOSTS = json.loads(os.getenv("DJANGO_ALLOWED_HOSTS") or '["localhost"]')
if os.getenv("DJANGO_ADMINS"):
    ADMINS = json.loads(os.getenv("DJANGO_ADMINS"))


# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "django_filters",
    "django_prometheus",
    "api_main.apps.ApiMainConfig",
    "api_admin_ui.apps.ApiAdminUiConfig",
    "api_rest_interface.apps.ApiRestInterfaceConfig",
]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = "api_main.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

ASGI_APPLICATION = "api_main.asgi.application"


# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases
if os.getenv("DJANGOAPIDB_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "timescale.db.backends.postgresql",
            "HOST": os.getenv("DJANGOAPIDB_HOST"),
            "PORT": int(os.getenv("DJANGOAPIDB_PORT") or 5432),
            "USER": os.getenv("DJANGOAPIDB_USER") or "bemcom",
            "PASSWORD": os.getenv("DJANGOAPIDB_PASSWORD") or "bemcom",
            "NAME": os.getenv("DJANGOAPIDB_DBNAME") or "bemcom",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR.parent / "db.sqlite3",
        }
    }

# This is just here to silence some warnings and make explicit what
# django < 3.2 has always done. See:
# https://docs.djangoproject.com/en/3.2/ref/settings/#std:setting-DEFAULT_AUTO_FIELD
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)s-%(name)s-%(levelname)s: %(message)s"}
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "api_main.loggers.StreamHandlerPlusIPs",
            "formatter": "simple",
        },
        "prometheus": {
            "level": "DEBUG",
            "class": "api_main.loggers.PrometheusHandler",
        },
    },
    "root": {
        "handlers": ["console", "prometheus"],
        "level": os.getenv("LOGLEVEL") or "INFO",
    },
}

# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        )
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        )
    },
]

# The default value (1000) prevents us from deleting larger number of items
# with Django Admin. See also:
# https://docs.djangoproject.com/en/3.1/ref/settings/#data-upload-max-number-fields
DATA_UPLOAD_MAX_NUMBER_FIELDS = None

# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Root path aka. base url. In theory django doesn't need to know the
# root path and works as expected behind a reverse proxy. Here the
# main issue is that we use a lot of absolute URLs, which need to be
# fixed manually.
# **NOTE**: ROOT_PATH must be without a leading slash but with a trailing
# slash if not empty, e.g. `bemcom/`
ROOT_PATH = os.getenv("ROOT_PATH") or ""

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/
STATIC_ROOT = BASE_DIR.parent / "static"
STATIC_URL = "/" + ROOT_PATH + "static/"

# Finally some security related stuff, that is only relevant for production
# where we don't offer a plain HTTP page.
if (os.getenv("HTTPS_ONLY") or "FALSE").lower() == "true":
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ------------------------------------------------------------------------------
# Special settings for REST API
# ------------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.BasicAuthentication",
        "api_rest_interface.authentication.TokenAuthenticationBearer",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "api_rest_interface.permissions.DjangoModelPermissionWithViewRestricted"
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "BEMCom API",
    "DESCRIPTION": (
        "Allows to send/receive data from/to diverse devices. "
        "Please consult the [official documentation of the BEMCom framework]"
        "(https://github.com/fzi-forschungszentrum-informatik/"
        "BEMCom/blob/master/documentation/Readme.md) for more information."
    ),
    "LICENSE": {"name": "Licensed under MIT"},
    "VERSION": "0.8.6",
}
