from django.urls import path

from . import views
from .announcements import activity_announce

app_name = "activities"

urlpatterns = [
    path('activities/<int:pk>/announce/', activity_announce, name='announce'),
    path('series/new/', views.series_create, name='series_create'),
    path('series/<int:pk>/', views.series_detail, name='series_detail'),
    path('series/<int:pk>/edit/', views.series_edit, name='series_edit'),
    path("", views.index, name="index"),
    path("discover/categories/", views.category_explore, name="categories"),
    path("activities/new", views.create, name="create"),
    path("activities/<int:pk>/roster/", views.roster, name="roster"),
    path("activities/<int:pk>/cancel/", views.cancel, name="cancel"),
    path("activities/<int:pk>/", views.detail, name="detail"),
    path("activities/<int:pk>/respond", views.respond, name="respond"),
    path("activities/<int:pk>/join", views.join, name="join"),
    path("activities/<int:pk>/hide-organizer", views.hide_organizer, name="hide_organizer"),
    path("activities/<int:pk>/hide", views.hide, name="hide"),
    path("activities/<int:pk>/leave", views.leave, name="leave"),
]
