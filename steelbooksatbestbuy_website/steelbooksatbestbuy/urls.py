from django.urls import path

from steelbooksatbestbuy.views import Index

urlpatterns = [
    path('', Index.as_view(), name="index"),
]
