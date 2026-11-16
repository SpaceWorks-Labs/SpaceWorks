"""Static collection only: no DB, Celery, deployment secrets or runtime settings."""
SECRET_KEY = "build-only-static-collection"
INSTALLED_APPS = ["unfold", "django.contrib.admin", "django.contrib.auth",
                  "django.contrib.contenttypes", "django.contrib.sessions",
                  "django.contrib.messages", "django.contrib.staticfiles",
                  "rest_framework", "drf_spectacular", "unfold.contrib.filters"]
STATIC_URL = "/static/"
STATIC_ROOT = "/app/staticfiles"
STORAGES = {"staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}
DATABASES = {}
