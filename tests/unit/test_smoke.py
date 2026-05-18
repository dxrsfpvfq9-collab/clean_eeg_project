"""Smoke tests — verify pytest is wired up and the lightweight, non-GUI
modules can be imported without side effects.

These are intentionally trivial. Their job is to fail loudly if
`pytest` can't discover/run tests, or if a basic import path breaks.
Real behavior tests live in sibling files (test_tfcfilters.py, etc.).
"""


def test_arithmetic_works():
    """If this fails, pytest itself is broken."""
    assert 2 + 2 == 4


def test_import_tfcfilters():
    """tfcfilters is pure numpy/scipy — should import with no side effects."""
    from process import tfcfilters

    assert hasattr(tfcfilters, "filts")
    assert hasattr(tfcfilters, "tfcfilterall")
    assert hasattr(tfcfilters, "get_statistics")
    assert hasattr(tfcfilters, "tfcentropy")


def test_import_allocate_data_array():
    """Trivial helper with no third-party deps."""
    from files import allocate_data_array

    arr = allocate_data_array.allocate_data_array(3, 4)
    assert len(arr) == 3
    assert len(arr[0]) == 4
    assert arr[0][0] == 0.0
