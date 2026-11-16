"""Release-2 lane L23: metered machine sessions (owner decision #158).

`machines.sessions` -- off by default, under the machines module, with nothing else
required. On: a checked-in, certified member starts a timed session by scanning the
machine's QR (or staff start one for them, or an integrated machine's own reports open
and close one), and it stops on Stop, at the type's maximum length, at check-out or at
closing time. Billing applies only while `charges.machines` is also on.

Off: every session route answers 404, no sweep runs and today's manual-hours usage log
is unchanged. Every session, amendment and charge already recorded is kept.
"""


def definitions(feature):
    return (
        feature(
            "machines.sessions", "machines", "Machine sessions",
            "Members start and stop timed sessions on a machine by scanning its QR; staff start, stop and "
            "correct them; integrated machines report their own. Sessions bill the type's hourly rate when "
            "machine charges are on.",
        ),
    )
