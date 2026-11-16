from django.urls import path

from .views_member import MemberMessagingConsentView, MemberMessagingView
from .views_settings import MessagingSettingsView
from .views_test import MessagingTestView
from .views_templates import WhatsAppTemplateCatalogView, WhatsAppTemplateDetailView, WhatsAppTemplateListView

member_urlpatterns = [
    path("me/messaging", MemberMessagingView.as_view(), name="member-messaging"),
    path("me/messaging/consent", MemberMessagingConsentView.as_view(), name="member-messaging-consent"),
]
staff_urlpatterns = [
    path("makerspace/<int:makerspace_id>/messaging-settings/test", MessagingTestView.as_view(), name="messaging-test"),
    path("makerspace/<int:makerspace_id>/messaging-settings", MessagingSettingsView.as_view(), name="messaging-settings"),
    path("makerspace/<int:makerspace_id>/whatsapp-templates", WhatsAppTemplateListView.as_view(), name="whatsapp-template-list"),
    path("makerspace/<int:makerspace_id>/whatsapp-templates/catalog", WhatsAppTemplateCatalogView.as_view(), name="whatsapp-template-catalog"),
    path("makerspace/<int:makerspace_id>/whatsapp-templates/<int:pk>", WhatsAppTemplateDetailView.as_view(), name="whatsapp-template-detail"),
]
