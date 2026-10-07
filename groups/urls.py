from django.urls import path
from . import views
from activities.announcements import group_announce

app_name = "groups"
urlpatterns = [
    path("invitations/pending/", views.pending_invitation_view, name="pending_invitation"),
    path("invitations/<str:token>/", views.invitation, name="invitation"),
    path("<int:pk>/invite/", views.invite, name="invite"),
    path("<int:pk>/invitations/<int:invitation_pk>/revoke/", views.revoke_invitation, name="revoke_invitation"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/announce/", group_announce, name="announce"),
    path("new/", views.create, name="create"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/join/", views.join, name="join"),
    path("<int:pk>/leave/", views.leave, name="leave"),
    path("<int:pk>/members/<int:member_pk>/", views.membership_action, name="membership_action"),
]
