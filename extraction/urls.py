from django.urls import path
from .views import (
    ExtractView,
)

urlpatterns = [
    path('extract/', ExtractView.as_view(), name='extract'),
]
