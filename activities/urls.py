from django.urls import path

from . import views
from . import polls
from . import email_invitations
from . import group_offers
from .announcements import activity_announce

app_name = "activities"

urlpatterns = [
    path('activities/<int:pk>/poll/answer/', polls.vote, name='poll_vote'),
    path('activities/<int:pk>/poll/finalize/', polls.finalize, name='poll_finalize'),
    path('activities/<int:pk>/group-offer/', group_offers.answer, name='answer_group_offer'),
    path('activity-invitations/pending/', email_invitations.pending_invitation_view, name='pending_email_invitation'),
    path('activity-invitations/<str:token>/', email_invitations.invitation, name='email_invitation'),
    path('activities/<int:pk>/email-invitations/', email_invitations.send_invitation, name='send_email_invitation'),
    path('activities/<int:pk>/email-invitations/<int:invitation_pk>/revoke/', email_invitations.revoke_invitation, name='revoke_email_invitation'),
    path('activities/<int:pk>/announce/', activity_announce, name='announce'),
    path('series/new/', views.series_create, name='series_create'),
    path('series/<int:pk>/', views.series_detail, name='series_detail'),
    path('series/<int:pk>/edit/', views.series_edit, name='series_edit'),
    path("", views.index, name="index"),
    path("discover/categories/", views.category_explore, name="categories"),
    path("activities/new", views.create, name="create"),
    path('activities/<int:pk>/invitations/', views.manage_invitations, name='manage_invitations'),
    path("activities/<int:pk>/roster/", views.roster, name="roster"),
    path("activities/<int:pk>/cancel/", views.cancel, name="cancel"),
    path("activities/<int:pk>/", views.detail, name="detail"),
    path("activities/<int:pk>/respond", views.respond, name="respond"),
    path("activities/<int:pk>/join", views.join, name="join"),
    path("activities/<int:pk>/hide-organizer", views.hide_organizer, name="hide_organizer"),
    path("activities/<int:pk>/hide", views.hide, name="hide"),
    path("activities/<int:pk>/leave", views.leave, name="leave"),
]
