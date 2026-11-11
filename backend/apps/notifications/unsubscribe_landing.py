"""Server-rendered unsubscribe pages for installs with no website (API-only).

Opening the link changes nothing: the form POSTs the RFC 8058 one-click body back to the
same path, so only a person pressing the button opts out (mail scanners prefetch links).
"""

from django.http import HttpResponse
from django.utils.html import escape
from django.utils.translation import gettext

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>{title}</title></head>
<body style="font-family:Arial,sans-serif;max-width:480px;margin:48px auto;padding:0 16px;color:#16181d;">
<h1 style="font-size:22px;">{title}</h1><p>{body}</p>{form}</body></html>"""


def _page(title, body, form="", status=200):
    response = HttpResponse(_PAGE.format(title=escape(title), body=escape(body), form=form),
                            content_type="text/html; charset=utf-8", status=status)
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


def confirm_form():
    # action="" posts to this same path; the signed token in it stays the only authority.
    form = ('<form method="post" action=""><input type="hidden" name="List-Unsubscribe" value="One-Click">'
            f'<button type="submit" style="padding:10px 18px;font-size:16px;">{escape(gettext("Unsubscribe"))}</button></form>')
    return _page(gettext("Stop these emails?"), gettext(
        "You'll stop getting optional emails of this kind from this makerspace. "
        "Safety and account emails still arrive."), form)


def invalid():
    return _page(gettext("This link didn't work"), gettext(
        "The link may have expired. You can change email settings from your account instead."), status=400)
