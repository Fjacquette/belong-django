from django.urls import path

from . import views

app_name = "activities"

urlpatterns = [
    path("", views.index, name="index"),
    path("discover/categories/", views.category_explore, name="categories"),
    path("activities/new", views.create, name="create"),
    path("activities/<int:pk>/", views.detail, name="detail"),
    path("activities/<int:pk>/respond", views.respond, name="respond"),
    path("activities/<int:pk>/join", views.join, name="join"),
    path("activities/<int:pk>/leave", views.leave, name="leave"),
]
