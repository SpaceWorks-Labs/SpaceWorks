"""Shared SQLSTATE extraction across driver versions and wrapper chains."""
import pytest

from apps.core.db import sqlstate


@pytest.mark.parametrize("attribute", ["pgcode", "sqlstate"])
@pytest.mark.parametrize("links", [(), ("__cause__",), ("__context__",),
                                  ("__cause__", "__context__", "__cause__")])
def test_sqlstate_reads_each_driver_at_any_chain_depth(attribute, links):
    driver = Exception("driver")
    setattr(driver, attribute, "55P03")
    outer = driver
    for link in links:
        wrapper = Exception("wrapper")
        setattr(wrapper, link, outer)
        outer = wrapper
    assert sqlstate(outer) == "55P03"


def test_sqlstate_checks_context_when_explicit_cause_has_no_code():
    outer = Exception("outer")
    outer.__cause__ = Exception("unrelated wrapper")
    outer.__context__ = Exception("driver")
    outer.__context__.pgcode = "57014"
    assert sqlstate(outer) == "57014"


def test_sqlstate_prefers_outer_code_then_cause_before_context():
    outer = Exception("outer")
    outer.sqlstate = "23505"
    outer.__cause__ = Exception("cause")
    outer.__cause__.pgcode = "55P03"
    outer.__context__ = Exception("context")
    outer.__context__.sqlstate = "57014"
    assert sqlstate(outer) == "23505"
    outer.sqlstate = None
    assert sqlstate(outer) == "55P03"
    outer.pgcode = "40P01"
    assert sqlstate(outer) == "40P01"


def test_sqlstate_cycles_terminate_and_still_visit_other_links():
    outer, cause, context = Exception("outer"), Exception("cause"), Exception("context")
    outer.__cause__, cause.__cause__ = cause, outer
    outer.__context__ = context
    assert sqlstate(outer) is None
    context.pgcode = "23505"
    assert sqlstate(outer) == "23505"
    assert sqlstate(None) is None
    assert sqlstate(Exception("no driver metadata")) is None
