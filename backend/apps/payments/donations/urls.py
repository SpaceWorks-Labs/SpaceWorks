"""Lane L18 routes: public giving, guest links, staff donations and sponsors (`api/v1/`), plus
the giver's own member routes (`MEMBER_PATTERNS`, mounted under `api/v1/member/`)."""

from django.urls import path

from . import views_guest as guest, views_member as member, views_public as public
from . import views_sponsor_logo as logo, views_sponsors as sponsors, views_staff as staff

SPACE = "admin/makerspace/<int:makerspace_id>"
PUBLIC = "public/<slug:makerspace_slug>"

DONATION_PATTERNS = [
    path(f"{PUBLIC}/donations", public.DonationPageView.as_view(), name="public-donation-page"),
    path(f"{PUBLIC}/donations/give", public.DonationCreateView.as_view(), name="public-donations"),
    path(f"{PUBLIC}/donations/email-code", public.DonationEmailCodeView.as_view(), name="public-donation-email-code"),
    path(f"{PUBLIC}/donations/pledges", public.PledgeCreateView.as_view(), name="public-donation-pledges"),
    path(f"{PUBLIC}/sponsors", public.SponsorWallView.as_view(), name="public-sponsor-wall"),
    path(f"{PUBLIC}/events/<uuid:public_token>/sponsors", public.EventSponsorWallView.as_view(),
         name="public-event-sponsors"),
    path("public/donation-links/<str:token>", guest.GuestGiftView.as_view(), name="public-donation-status"),
    path("public/donation-links/<str:token>/checkout", guest.GuestGiftCheckoutView.as_view(),
         name="public-donation-checkout"),
    path("public/donation-links/<str:token>/claim", guest.GuestGiftClaimView.as_view(),
         name="public-donation-claim"),
    path("public/donation-links/<str:token>/tax-receipt.pdf", guest.GuestTaxReceiptView.as_view(),
         name="public-donation-tax-receipt"),
    path("public/pledge-links/<str:token>", guest.GuestPledgeView.as_view(), name="public-pledge-manage"),
    path(f"{SPACE}/donations", staff.DonationListView.as_view(), name="admin-donations"),
    path(f"{SPACE}/donations/settings", staff.DonationSettingsView.as_view(), name="admin-donation-settings"),
    path(f"{SPACE}/donations/campaigns", staff.CampaignListView.as_view(), name="admin-donation-campaigns"),
    path(f"{SPACE}/donations/campaigns/<int:pk>", staff.CampaignDetailView.as_view(), name="admin-donation-campaign"),
    path(f"{SPACE}/donations/pledges", staff.PledgeListView.as_view(), name="admin-donation-pledges"),
    path(f"{SPACE}/donations/pledges/<int:pk>", staff.PledgeActionView.as_view(), name="admin-donation-pledge"),
    path(f"{SPACE}/donations/<int:pk>/cancel", staff.DonationActionView.as_view(action="cancel"),
         name="admin-donation-cancel"),
    path(f"{SPACE}/donations/<int:pk>/return", staff.DonationActionView.as_view(action="return"),
         name="admin-donation-return"),
    path(f"{SPACE}/donations/<int:pk>/tax-receipt.pdf", staff.StaffTaxReceiptView.as_view(),
         name="admin-donation-tax-receipt"),
    path(f"{SPACE}/sponsors", sponsors.SponsorListView.as_view(), name="admin-sponsors"),
    path(f"{SPACE}/sponsors/tiers", sponsors.TierListView.as_view(), name="admin-sponsor-tiers"),
    path(f"{SPACE}/sponsors/tiers/<int:pk>", sponsors.TierDetailView.as_view(), name="admin-sponsor-tier"),
    path(f"{SPACE}/sponsors/perks", sponsors.PerkListView.as_view(), name="admin-sponsor-perks"),
    path(f"{SPACE}/sponsors/perks/<int:pk>/fulfil", sponsors.PerkFulfilView.as_view(), name="admin-sponsor-perk-fulfil"),
    path(f"{SPACE}/sponsors/charges/<int:pk>/return", sponsors.ChargeReturnView.as_view(),
         name="admin-sponsor-charge-return"),
    path(f"{SPACE}/sponsors/event-links/<int:pk>", sponsors.EventLinkDetailView.as_view(),
         name="admin-sponsor-event-link"),
    path(f"{SPACE}/sponsors/event-sponsors", sponsors.EventSponsorChoicesView.as_view(),
         name="admin-sponsor-event-sponsors"),
    path(f"{SPACE}/sponsors/<int:pk>", sponsors.SponsorDetailView.as_view(), name="admin-sponsor"),
    path(f"{SPACE}/sponsors/<int:pk>/archive", sponsors.SponsorArchiveView.as_view(archived=True),
         name="admin-sponsor-archive"),
    path(f"{SPACE}/sponsors/<int:pk>/restore", sponsors.SponsorArchiveView.as_view(archived=False),
         name="admin-sponsor-restore"),
    path(f"{SPACE}/sponsors/<int:pk>/logo", logo.SponsorLogoView.as_view(), name="admin-sponsor-logo"),
    path(f"{SPACE}/sponsors/<int:pk>/charges", sponsors.ChargeListView.as_view(), name="admin-sponsor-charges"),
    path(f"{SPACE}/sponsors/<int:pk>/event-links", sponsors.EventLinkListView.as_view(),
         name="admin-sponsor-event-links"),
]

MEMBER_PATTERNS = [
    path("makerspaces/<int:makerspace_id>/donations", member.MemberDonationListView.as_view(), name="member-donations"),
    path("makerspaces/<int:makerspace_id>/donations/<int:pk>/tax-receipt.pdf", member.MemberTaxReceiptView.as_view(),
         name="member-donation-tax-receipt"),
    path("makerspaces/<int:makerspace_id>/pledges", member.MemberPledgeListView.as_view(), name="member-pledges"),
    path("makerspaces/<int:makerspace_id>/pledges/<int:pk>", member.MemberPledgeActionView.as_view(),
         name="member-pledge"),
]
