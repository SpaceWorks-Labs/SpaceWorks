"""Parity E-B8: a space's own sender identity and its own privacy / terms text (both ON by default).

* `email.sender_identity` -- the space's display name and Reply-To on the email it sends. Off = mail goes out with
  the plain sender; the saved values are kept. (The own-SMTP test is a safety gate, not a switch: it is always on.)
* `legal.space_pages` -- a space may replace the platform's privacy / terms text with its own on its public pages.
  Off = visitors see the platform text and the editor answers 404; the saved text is kept.
"""


def definitions(feature):
    return (
        feature("email.sender_identity", "email", "Sender name and reply-to",
                "Email from this space carries its own display name and a Reply-To address.",
                default_enabled=True),
        feature("legal.space_pages", None, "Own privacy and terms pages",
                "Replace the platform's privacy and terms text with this space's own on its public pages.",
                default_enabled=True),
    )
