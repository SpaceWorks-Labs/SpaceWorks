"""Lane r2-idcards-best certificate routes (#199) and the native-app decision for each (#173).

Composed into `programme_route_catalog.ROUTES`, like the other programme lanes; classification
grants no domain authority. Admin routes target their event; the member routes act on the
member's own rows in one space; the public reads are anonymous and certificate-targeted.
"""

CERTIFICATE_ROUTES = (
    ('events-programme-admin-certificate-signatories', ('GET', 'HEAD', 'POST'), 'event'),
    ('events-programme-admin-certificate-signatory-candidates', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-certificate-signatory-policy', ('POST',), 'event'),
    ('events-programme-admin-certificate-signatory-detail', ('DELETE',), 'event'),
    ('events-programme-member-certificate-approvals', ('GET', 'HEAD'), 'tenant'),
    ('events-programme-member-certificate-approval-preview', ('GET', 'HEAD'), 'tenant'),
    ('events-programme-member-certificate-approve', ('POST',), 'tenant'),
    ('events-programme-admin-certificate-issue-plan', ('POST',), 'event'),
    ('events-programme-admin-certificate-issue-sample', ('POST',), 'event'),
    ('events-programme-admin-certificates-issued', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-certificate-png', ('GET', 'HEAD'), 'event'),
    ('events-programme-member-certificates', ('GET', 'HEAD'), 'tenant'),
    ('events-programme-member-certificate-png', ('GET', 'HEAD'), 'tenant'),
    ('events-programme-member-certificate-share-image', ('GET', 'HEAD'), 'tenant'),
    ('events-programme-member-certificate-holder-name', ('POST',), 'tenant'),
    ('events-programme-public-certificate-share-image', ('GET', 'HEAD'), 'certificate'),
    ('events-programme-public-certificate-share-card', ('GET', 'HEAD'), 'certificate'),
)
NATIVE = "native"
CERTIFICATE_NATIVE_DECISIONS = {name: NATIVE for name, methods, target in CERTIFICATE_ROUTES}
