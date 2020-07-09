"""
Django settings for manager project.

Generated by 'django-admin startproject' using Django 2.2.6.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.2/ref/settings/
"""

import os

from dotenv import load_dotenv, find_dotenv

# This should read in variables stored in the env files of the parent directores.
# This is used in container mode to load auto generated values like SECRET_KEY
# and ALLOWED_HOSTS. While developing outside of the container you can place
# development values for the variables in the .env file next to docker-compose.yml
# it is also found here.
load_dotenv(find_dotenv(), verbose=True, override=True)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load custom configuration variables from environment variable
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT"))
MODE = os.getenv("MODE")

# Settings for connection to MQTT broker.
MQTT_BROKER = {
    'host': MQTT_BROKER_HOST,
    'port': MQTT_BROKER_PORT,
}

# Also set some config variables used by django
ALLOWED_HOSTS = eval(os.getenv("ALLOWED_HOSTS"))
DJANGO_ADMINS = os.getenv("DJANGO_ADMINS")
if DJANGO_ADMINS:
    ADMINS = eval(DJANGO_ADMINS)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY=os.getenv("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
if MODE == "DEVL":
    DEBUG = True
else:
    DEBUG = False

# Logging inspired by practical django book
if MODE == "DEVL":
    loglevel = "DEBUG"
else:
    loglevel = "INFO"
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': loglevel,
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
    },
    'loggers': {
        'core': {
            'handlers': ['console'],
            'level': loglevel,
            'propagate': True,
        },
        'manager': {
            'handlers': ['console'],
            'level': loglevel,
            'propagate': True,
        },
    },
}


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'channels',
    'main.apps.MainConfig',
    'admin_ui.apps.AdminUIConfig',
    'rest_api.apps.RESTApiConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'general_configuration.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Settings for channels server
ASGI_APPLICATION = "general_configuration.routing.application"

# The bemcom api should not see to much data. The sqlite should
# be sufficient thus. The folder for the DB is exepcted under /bemcom/db
# if executed in the container or in a db folder next to django_code if 
# developing outside of the container.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, os.pardir, 'db', 'db.sqlite3'),
    }
}

# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators
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
# https://docs.djangoproject.com/en/2.2/topics/i18n/
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, os.pardir, 'static')

# Setup Auth and Permissions for DRF.
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
            'rest_framework.permissions.IsAuthenticated',
        ]
}

# Finally some security related stuff, that is only relevant for production 
# where we don't offer a plain HTTP page. The first two are suggested by 
# Django's deployment checklist, the remaining by the check --deploy result.
#
# Don't activate SECURE_HSTS_SECONDS and SECURE_SSL_REDIRECT, they will break
# the tests but don't provide anything useful as the API does not expose a non
# SSL endpoint in PROD mode.
if MODE != "DEVL":
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = "DENY"
