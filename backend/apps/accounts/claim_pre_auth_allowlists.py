"""Reviewed policy and lifecycle overrides on claim-reachable DRF views.

Split out of ``claim_pre_auth_guard`` (which re-exports both names) to keep it under the
file ceiling; the guard logic that reads these allowlists still lives there.
"""

# These are the normal extension hooks implemented by the custom policies currently
# configured on claim-reachable routes. Exact class+method matching makes a new hook a
# build failure instead of silently trusting executable pre-auth code.
POLICY_OVERRIDE_ALLOWLIST = {
    # Presence TV throttles only declare a scope/rate; DRF owns every hook.
    "apps.presence.views_public.PresenceTVThrottle": set(),
    "apps.presence.views_public.PresenceTVUserThrottle": set(),
    # Release 2 L5: claim and pay-link throttles only declare a scope; DRF owns every hook.
    "apps.payments.throttles_l5.PaymentClaimThrottle": set(),
    "apps.payments.throttles_l5.PayLinkThrottle": set(),
    # Release 2 L15: the price-preview throttle only declares a scope.
    "apps.payments.views_pricing_quote.PricingQuoteThrottle": set(),
    "apps.bookings.views_passes.BookingPassRenderThrottle": set(),
    "apps.bookings.views_confirmation.BookingConfirmationThrottle": set(),
    "apps.bookings.throttles_feed.BookingFeedTokenThrottle": {"get_cache_key"},
    "apps.bookings.throttles_feed.BookingFeedIpThrottle": {"get_cache_key"},
    "apps.accounts.throttles_mfa.MFAChallengeThrottle": {"get_cache_key"},
    "apps.accounts.throttles_mfa.MFAUserThrottle": {"get_cache_key"},
    # S-B: the login-code resend budgets, per address and per challenge.
    "apps.accounts.views_login_codes.LoginCodeIPThrottle": {"get_cache_key"},
    "apps.accounts.views_login_codes.LoginCodeResendThrottle": {"get_cache_key"},
    "apps.accounts.views_reauthentication.ReauthenticationThrottle": {"get_cache_key"},
    "apps.accounts.views_account_merge.AccountMergeStartThrottle": {"get_cache_key"},  # U-C, keyed per person
    "apps.accounts.views_account_merge.AccountMergeProveThrottle": {"get_cache_key"},  # U-C, keyed per person
    "apps.organizations.views_self_service.OrganizationCreationThrottle": {"get_cache_key"},
    "apps.organizations.views_self_service.OrganizationCreationIpThrottle": {"get_cache_key"},
    "apps.admin_api.permissions.IsActiveStaff": {"has_permission", "has_object_permission"},
    # `_authenticate_claim` is the sanctioned claim-session path added in D5. It is listed
    # deliberately: this guard exists so that a NEW method on a configured policy class is a
    # decision rather than an accident, and the claim authenticator is exactly such a decision.
    "apps.accounts.authentication.SpaceWorksJWTAuthentication": {
        "authenticate",
        "_authenticate_claim",
    },
    "apps.accounts.throttles.DeviceLoginThrottle": {"get_cache_key"},
    "apps.accounts.throttles.DeviceLoginUserThrottle": {"get_cache_key"},
    # Native social linking keys its budget only for device-grant POSTs.
    "apps.accounts.throttles.NativeSocialLinkThrottle": {"get_cache_key"},
    "apps.accounts.throttles.MemberVerificationEmailThrottle": {"get_cache_key"},
    "apps.accounts.throttles.PasswordResetEmailThrottle": {"get_cache_key"},
    # Phase 8: the per-email confirm budget, kept distinct from the request budget
    # so guessing a code cannot exhaust the ability to ask for a new one.
    "apps.accounts.throttles.PasswordResetConfirmEmailThrottle": {"get_cache_key"},
    "apps.accounts.throttles.PhoneConfirmNumberThrottle": {"get_cache_key"},
    "apps.accounts.throttles.PhoneLoginConfirmThrottle": {"get_cache_key"},
    "apps.accounts.throttles.PhoneOtpNumberThrottle": {"get_cache_key"},
    "apps.accounts.throttles.PhoneOtpRequestThrottle": {"get_cache_key"},
    # #196: the person-credential authenticators run first in DEFAULT_AUTHENTICATION_CLASSES.
    # Each returns None unless the bearer carries its own swpat_/swoa_ prefix, so a claim
    # JWT always falls through to SpaceWorksJWTAuthentication; a matched token goes through
    # admit_person, which refuses every /api/v1/auth/ and credential route. The header hook
    # only names the WWW-Authenticate realm. Neither ever authenticates a claim session.
    "apps.apiclients.person_auth.PersonalAccessTokenAuthentication": {"authenticate", "authenticate_header"},
    "apps.apiclients.person_auth.OAuthPersonAuthentication": {"authenticate", "authenticate_header"},
    "apps.apiclients.throttling.ClientTierRateThrottle": {"_tier", "allow_request", "get_cache_key"},
    "apps.apiclients.throttling.MemberPrincipalRateThrottle": {"_tier", "allow_request", "get_cache_key"},
    "apps.events.throttles.CollaborativeRegistrationThrottle": {
        "_tier", "allow_request", "get_cache_key"
    },
    # Public feedback reads and submissions take separate budgets. The scope is chosen in
    # `allow_request` rather than a view-level `get_throttles()` override precisely BECAUSE
    # this guard forbids a lifecycle-hook override on a pre-auth route; the override set is
    # therefore identical to its ClientTierRateThrottle base.
    "apps.events.throttles.PublicFeedbackRateThrottle": {
        "_tier", "allow_request", "get_cache_key"
    },
    # The account-less borrow-request budgets (#80). Both override `get_cache_key` only, to
    # return None for an authenticated caller, so a makerspace behind one NAT never
    # rate-limits its own signed-in staff by egress IP.
    "apps.hardware_requests.throttles.AnonymousRequestIpBurstThrottle": {"get_cache_key"},
    "apps.hardware_requests.throttles.AnonymousRequestIpHourThrottle": {"get_cache_key"},
    # The subscribable calendar feed is fetched by a calendar client with only its
    # bearer token, so the budget keys on that token rather than the caller.
    "apps.events.throttles.EventCalendarFeedTokenThrottle": {"get_cache_key"},
    "apps.events.throttles.EventCalendarFeedIpThrottle": {"get_cache_key"},
    # Ticket renders only set a per-user scope/rate; all lifecycle methods are DRF's.
    "apps.events.views_ticket.TicketRenderThrottle": set(),
    # Certificate downloads share a principal-keyed render budget. The only hook
    # selects that cache key; it never authenticates or grants claim authority.
    "apps.events.throttles.CredentialRenderThrottle": {"get_cache_key"},
    "apps.events.throttles.SpeakerClaimThrottle": {"get_cache_key"},
    "apps.machines.permissions.IsActiveRequester": {"has_permission"},
    "apps.accounts.views_device.IsDeviceAccessToken": {"has_permission"},
    "apps.makerspaces.throttles.MemberImagePresignThrottle": {"get_cache_key"},
    # Events programme and saved-detail budgets only declare scope/rate.
    "apps.accounts.saved_details.views.VaultThrottle": set(),
    "apps.events.contributions.api_common.ProgrammeThrottle": set(),
    "apps.events.certificates.verification.VerifyThrottle": set(),
    "apps.events.profile_photos.views_public.PublicPhotoThrottle": set(),
    # Card photo attachment spends the existing scoped budget only on PUT.
    "apps.card_designs.views_holder_photo.HolderPhotoAttachThrottle": {"allow_request"},
    # Keys the member command budget on the principal (or IP before login); grants nothing.
    "apps.events.hackathons.api_base.ProgrammeCommandThrottle": {"get_cache_key"},
}

# Reviewed lifecycle overrides on claim-reachable views, keyed by the class that defines
# them. Each listed hook only narrows access or shapes the response after DRF's own
# authentication; a hook on any other class, or a new hook on a listed class, stays a
# build failure.
LIFECYCLE_OVERRIDE_ALLOWLIST = {
    # initial: super().initial() first, then refuses API-client sessions and non-owners;
    # handle_exception: maps key-unavailable/fenced errors to typed 503/423 responses;
    # finalize_response: private no-store headers.
    "apps.accounts.saved_details.views.OwnerView": {"initial", "handle_exception", "finalize_response"},
    # handle_exception: reshapes DRF errors into the programme error envelope;
    # finalize_response: private no-store, Vary and nosniff headers.
    "apps.events.hackathons.api_base.ProgrammeView": {"handle_exception", "finalize_response"},
    # finalize_response: private no-store header only.
    "apps.events.contributions.api_common.ProgrammeView": {"finalize_response"},
    # initial: super().initial() first, then validates the command Idempotency-Key;
    # finalize_response: no-store and nosniff headers.
    "apps.events.judging.api_common.PrivateView": {"initial", "finalize_response"},
    # initial: super().initial() first, then refuses a foreign tenant/event pair and a
    # mismatched command header; finalize_response: private no-store headers.
    "apps.events.submissions.views_base.PrivateSubmissionView": {"initial", "finalize_response"},
    # finalize_response: private no-store headers on the public card image.
    "apps.events.profile_photos.views_public.PublicCardPhotoView": {"finalize_response"},
    # finalize_response: no-store and nosniff headers on public certificate verification.
    "apps.events.certificates.verification.CertificateVerificationView": {"finalize_response"},
    # Event reimbursements, finance payouts and staged forms: ``initial`` calls
    # ``super().initial()`` first and then refuses claim and API-client sessions;
    # ``handle_exception`` maps domain errors to typed API errors; ``finalize_response``
    # adds no-store/nosniff headers.
    "apps.payments.event_payouts.http.PrivateView": {"handle_exception", "finalize_response"},
    "apps.events.staged_forms.http.PrivateView": {"initial", "handle_exception", "finalize_response"},
    "apps.event_reimbursements.http.PrivateView": {"handle_exception"},
    # #196: the token and app-connection routes. ``initial`` calls ``super().initial()``
    # first, then demands a recent re-authentication for every unsafe method.
    "apps.accounts.reauthentication_permissions.RecentReauthenticationMixin": {"initial"},
}
