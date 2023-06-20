# -*- coding: utf-8 -*-
"""
Django settings for demo_app project.

Generated by 'django-admin startproject' using Django 4.0.4.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.0/ref/settings/
"""
import logging
import sys
import os
from pathlib import Path
import environ

env = environ.Env(
    DEBUG=(bool, False),
    DEBUG_LEVEL=(int, logging.WARNING),
    SECRET_KEY=(str, "SECRET_KEY"),
    MARIADB_DATABASE=(str, "db"),
    MARIADB_USER=(str, "root"),
    MARIADB_PASSWORD=(str, "password"),
    MARIADB_HOST=(str, "127.0.0.1"),
    MARIADB_PORT=(str, "3306"),
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "django_input_collection",
    # Project
    "demo_app",
    "core",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "demo_app.urls"

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

WSGI_APPLICATION = "demo_app.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("MARIADB_DATABASE"),
        "USER": env("MARIADB_USER"),
        "PASSWORD": env("MARIADB_PASSWORD"),
        "HOST": env("MARIADB_HOST"),
        "PORT": env("DOCKER_MYSQL_PORT", default=env("MARIADB_PORT", default="3306")),
        "OPTIONS": {"charset": "utf8mb4"},
        "TEST": {
            "MIGRATE": False,
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_unicode_520_ci",
        },
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

STATIC_URL = "static/"

# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

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
        "demo_app": {
            "handlers": ["console"],
            "level": env("DEBUG_LEVEL", "ERROR"),
            "propagate": False,
        },
        "": {"handlers": ["console"], "level": env("DEBUG_LEVEL", "ERROR"), "propagate": True},
    },
}

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PARSER_CLASSES": ("rest_framework.parsers.JSONParser",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
}

# Point to our defaults
INPUT_COLLECTEDINPUT_MODEL = "django_input_collection.CollectedInput"
INPUT_BOUNDSUGGESTEDRESPONSE_MODEL = "django_input_collection.BoundSuggestedResponse"
