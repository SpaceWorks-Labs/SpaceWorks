"""Integrator attaches under public/organizations after global route admission."""

from django.urls import path
from .views_public import PublicOrganizationMakerspacesView

urlpatterns = [path("<slug:slug>/makerspaces/", PublicOrganizationMakerspacesView.as_view(), name="public-organization-makerspaces")]
