from django.urls import path
from .views import (
    ExtractView,DebugView
)

urlpatterns = [
    path('extract/', ExtractView.as_view(), name='extract'),
    path('debug/', DebugView.as_view(), name='debug'),  # Add this

]
