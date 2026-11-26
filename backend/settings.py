

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

import environ
env = environ.Env()
environ.Env.read_env(BASE_DIR/ ".env")

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-s97)uae0_n5x+^6%l)u7b=*2qi#(0@5k@6-b1uoqf9*_9bfrtv'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # unbox apps
    'apps.accounts',
    'apps.videos',
    'apps.blogs',
    'apps.categories',
    'apps.moderation',
    'apps.uploads',
    'apps.media_assets',
    'apps.core',
    'apps.reviews',

    # Third party
    'rest_framework',
    'corsheaders',
    'drf_spectacular',
    "rest_framework_simplejwt.token_blacklist",
    'django_filters'
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

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

WSGI_APPLICATION = 'backend.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

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


AUTH_USER_MODEL = 'accounts.User'

# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = 'static/'


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES':[
        "apps.accounts.authentication.CookieJWTAuthentication",
    ],
    'DEFAULT_PERMISSION_CLASSES':[
        "rest_framework.permissions.IsAuthenticated",
    ],
     "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Unbox API",
    "DESCRIPTION": "API documentation for the Unbox platform.",
    "VERSION": "1.0.0",
}

# token blacklisting and rotation

from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),

    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=[]
)

CSRF_TRUSTED_ORIGINS = env.list(
    'CSRF_TRUSTED_ORIGINS',
    default=[]
)

CORS_ALLOW_CREDENTIALS = env.bool(
    'CORS_ALLOW_CREDENTIALS',
    default=True
)


# AWS CREDENTIALS
AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID',default='')
AWS_SECRET_ACCESS_KEY  = env('AWS_SECRET_ACCESS_KEY',default='')
AWS_S3_REGION = env('AWS_S3_REGION', default='')
AWS_S3_BUCKET = env('AWS_S3_BUCKET', default='')

# cloudFront domain 
MEDIA_CDN_URL = env('MEDIA_CDN_URL', default='').rstrip('/')

# How long a presigned upload form stays valid
MEDIA_UPLOAD_URL_EXPIRY_SECONDS = 600

# Images
MEDIA_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
MEDIA_ALLOWED_IMAGE_TYPES = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
}
# generated versions: name -> max width in pixels (WebP)
MEDIA_IMAGE_VARIANTS = {
    'thumb': 400,
    'large': 1600,
}

# Embedded videos: check links exist via each platform's oEmbed lookup.
# Turn off for offline development or automated tests.
VIDEO_EMBED_CHECK = os.getenv('VIDEO_EMBED_CHECK','True') == 'True'

# Meta versions its Graph API; update here when Meta retires this version.
INSTAGRAM_OEMBED_URL = os.getenv(
    'INSTAGRAM_OEMBED_URL',
    'https://graph.facebook.com/v26.0/instagram_oembed',
)

# videos (multipart upload straight to S3)
MEDIA_MAX_VIDEO_BYTES = 500 * 1024 * 1024   #500 MB
MEDIA_ALLOWED_VIDEO_TYPES = {
    'video/mp4' : 'mp4',
    'video/quicktime' : 'mov'   #iphone recordings
}
MEDIA_VIDEO_PART_SIZE = 10 * 1024 * 1024    #10 MB (S3 minimum is 5 MB)
MEDIA_VIDEO_PART_URL_EXPIRY_SECONDS = 3600  # 1 hour per signed part URL

# media convert (video processing)
MEDIACONVERT_ROLE_ARN = os.getenv('MEDIACONVERT_ROLE_ARN','')
MEDIA_VIDEO_STATUS_CHECK_SECONDS = 15  # at most one AWS check per asset per 15 s

# CLOUDFRONT 
CLOUDFRONT_DISTRIBUTION_ID = os.getenv('CLOUDFRONT_DISTRIBUTION_ID','')
MEDIA_PREVIEW_URL_EXPIRY_SECONDS = 3600   # signed links for unpublished videos