import os

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / f'{os.environ["BOT_DATABASE_PATH"]}db.sqlite3',
    }
}

INSTALLED_APPS = (
    'steelbooksatbestbuy',
)

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

TIME_ZONE = 'Canada/Pacific'

USE_TZ = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ['SECRET_KEY']