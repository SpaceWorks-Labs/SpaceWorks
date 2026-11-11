"""Parity O-B4: member-card numbering, title-change reissue and desk printing (all OFF by default).

* `membership.card_numbering` -- number schemes (prefix + pattern) per space and per title, published with the
  design. Without a scheme (or with this off) cards keep the membership-number display. Data kept when off.
* `membership.title_card_reissue` -- changing a member's primary title reissues their live card (same number,
  new QR and verify token).
* `membership.card_desk_print` -- print a member card face straight from the desk at the chosen stock.
* `membership.staff_cards` -- staff ID cards: one card per active staff membership with the held roles and machine
  scope, its own number scheme and design, a public check page (name, "Staff", roles, valid/revoked). OFF by default;
  data kept when off. `membership.staff_cards_auto_issue` issues one when a staff role is granted (OFF by default).
"""


def definitions(feature):
    return (
        feature("membership.card_numbering", "membership", "Card numbering schemes",
                "Print numbers like TNK-2026-0042 on member cards from a pattern per space or per title, "
                "published together with the card design."),
        feature("membership.title_card_reissue", "membership", "Reissue the card when the title changes",
                "A new primary title gives the member a fresh QR on the same card number."),
        feature("membership.card_desk_print", "membership", "Desk card printing",
                "Print a member card face from the desk at A6, 4x6, 3x4 or CR80, portrait or landscape."),
        feature("membership.staff_cards", "membership", "Staff ID cards",
                "Give every staff member an ID card showing their roles and machine scope, with a public check "
                "page that shows name, Staff and roles only. The card ends when their staff access ends."),
        feature("membership.staff_cards_auto_issue", "membership", "Issue staff cards automatically",
                "Issue a staff card as soon as a staff role is granted.",
                requires_features=("membership.staff_cards",)),
    )
