from django.urls import path
from . import views

app_name = "groups"
urlpatterns = [
    path("new/", views.create, name="create"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/join/", views.join, name="join"),
    path("<int:pk>/leave/", views.leave, name="leave"),
    path("<int:pk>/members/<int:member_pk>/", views.membership_action, name="membership_action"),
]
