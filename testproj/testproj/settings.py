# -*- coding: utf-8 -*-
""" Django settings for testproj project. """
import logging
import sys

import environ

env = environ.Env(
    DEBUG=(bool, False),
    DEBUG_LEVEL=(int, logging.WARNING),
    SECRET_KEY=(str, "SECRET_KEY"),
    MYSQL_DATABASE=(str, "db"),
    MYSQL_USER=(str, "root"),
    MYSQL_PASSWORD=(str, "password"),
    MYSQL_HOST=(str, "127.0.0.1"),
    MYSQL_PORT=(str, "3306"),
)

# Things available to override in settings modules
DEBUG = env("DEBUG")

ALLOWED_HOSTS = []
INPUT_COLLECTEDINPUT_MODEL = "django_input_collection.CollectedInput"
INPUT_BOUNDSUGGESTEDRESPONSE_MODEL = "django_input_collection.BoundSuggestedResponse"


# Things overridden at your own peril
INSTALLED_APPS = [
    # Framework
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "django_input_collection",
    # Project
    "testproj.core",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("MYSQL_DATABASE"),
        "USER": env("MYSQL_USER"),
        "PASSWORD": env("MYSQL_PASSWORD"),
        "HOST": env("MYSQL_HOST"),
        "PORT": env("DOCKER_MYSQL_PORT", default=env("MYSQL_PORT", default="3306")),
    }
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
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
            ],
        },
    },
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PARSER_CLASSES": ("rest_framework.parsers.JSONParser",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] - %(message)s",
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "null": {
            "level": "DEBUG",
            "class": "logging.NullHandler",
        },
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "standard",
            "stream": sys.stdout,
        },
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": True},
        "django.request": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.server": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.db.backends": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.template": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "multiprocessing": {"handlers": ["console"], "level": "WARNING"},
        "py.warnings": {"handlers": ["console"], "level": "WARNING"},
        "testproj": {
            "handlers": ["console"],
            "level": env("DEBUG_LEVEL", "ERROR"),
            "propagate": False,
        },
        "": {"handlers": ["console"], "level": env("DEBUG_LEVEL", "ERROR"), "propagate": True},
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Things you should leave alone
SECRET_KEY = env("SECRET_KEY")
ROOT_URLCONF = "testproj.urls"
WSGI_APPLICATION = "testproj.wsgi.application"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True
STATIC_URL = "/static/"
