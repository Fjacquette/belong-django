from django.urls import path

from .views import ServeImageAssetView

app_name = "media_assets"

urlpatterns = [
    path("images/<uuid:pk>/", ServeImageAssetView.as_view(), name="serve"),
]
