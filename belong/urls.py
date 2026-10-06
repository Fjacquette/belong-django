"""
URL configuration for belong project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', views.BrandLoginView.as_view(), name='login'),
    path('accounts/signup/', views.signup, name='signup'),
    path('accounts/verification/', views.verification_status, name='verification_status'),
    path('accounts/verify/<str:token>/', views.verify_email, name='verify_email'),
    path('accounts/interests/', views.account_interests, name='account_interests'),
    path('accounts/settings/', views.account_settings, name='account_settings'),
    path('accounts/password_change/', views.BrandPasswordChangeView.as_view(), name='password_change'),
    path('accounts/password_change/done/', views.BrandPasswordChangeDoneView.as_view(), name='password_change_done'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('groups/', include('groups.urls')),
    path('', include('media_assets.urls')),
    path('', include('activities.urls')),
]
