"""Characterization of the legacy cleaner. Pins current behaviour; endorses none.

`clean_dataframe` is the pre-governance path that `run_workflow` still calls.
The governed cleaning engine will be built beside it, and the legacy path must
stay behaviourally unchanged while that happens. These tests are the golden
record that makes "unchanged" provable rather than asserted.

Two of the behaviours pinned here are the reason governance is being built:

- silent coercion: `["100", ..., "ABC"]` becomes an Int64 column with a NA
  where "ABC" was, with no count, lineage, or blocker;
- silent reinterpretation: valid ISO dates in a column whose sample is under
  80% ISO are parsed with dayfirst=True, which under the installed pandas turns
  2024-01-05 into 2024-05-01.

Inputs use explicit dtypes so the pinned behaviour is deterministic across the
declared pandas range. See docs/governed-cleaning.md.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from data_ops_lab.cleaner import BLANK_VALUES, clean_dataframe


def obj(values: list) -> pd.Series:
    return pd.Series(values, dtype=object)


def test_legacy_pins_column_name_normalization():
    out = clean_dataframe(pd.DataFrame({"Order Date": obj(["x"]), "Amount (EUR)": obj(["1"])}))
    assert list(out.columns) == ["order_date", "amount_eur"]


def test_legacy_pins_silent_numeric_coercion_when_ninety_percent_parse():
    """The case governance must replace: one bad value becomes NA, silently."""
    out = clean_dataframe(pd.DataFrame({"amount": obj(["100", "200", "300", "400", "500", "600", "700", "800", "900", "ABC"])}))
    assert str(out["amount"].dtype) == "Int64"
    assert out["amount"].tolist()[:9] == [100, 200, 300, 400, 500, 600, 700, 800, 900]
    assert pd.isna(out["amount"].iloc[9])


def test_legacy_pins_no_numeric_coercion_below_ninety_percent():
    out = clean_dataframe(pd.DataFrame({"amount": obj(["100", "200", "300", "400", "500", "600", "700", "800", "ABC", "DEF"])}))
    assert out["amount"].tolist() == ["100", "200", "300", "400", "500", "600", "700", "800", "ABC", "DEF"]


def test_legacy_pins_blank_sentinel_set_and_its_effect():
    """'-', '--', 'NA', 'n/a', 'none' are all erased to NA on object columns.
    Under the governed contract this operation is CONFIGURED_ONLY because these
    can be legitimate business values."""
    assert BLANK_VALUES == {"", " ", "na", "n/a", "none", "null", "-", "--"}
    out = clean_dataframe(pd.DataFrame({"code": obj(["A-1", "-", "--", "NA", "n/a", "none", "B"])}))
    values = out["code"].tolist()
    assert values[0] == "A-1" and values[6] == "B"
    assert all(pd.isna(v) for v in values[1:6])


def test_legacy_pins_whitespace_trim_on_object_columns():
    out = clean_dataframe(pd.DataFrame({"note": obj(["  padded  ", "x"])}))
    assert out["note"].tolist() == ["padded", "x"]


def test_legacy_pins_date_detection_by_column_name_only():
    """A column is parsed as dates because of its *name*, not its content."""
    dates = obj(["2024-01-05", "2024-02-06", "2024-03-07"])
    named = clean_dataframe(pd.DataFrame({"order_date": dates}))
    unnamed = clean_dataframe(pd.DataFrame({"reference": dates}))
    assert named["order_date"].tolist() == [dt.date(2024, 1, 5), dt.date(2024, 2, 6), dt.date(2024, 3, 7)]
    assert unnamed["reference"].tolist() == ["2024-01-05", "2024-02-06", "2024-03-07"]


def test_legacy_pins_iso_dates_are_reinterpreted_when_sample_iso_ratio_is_below_threshold():
    """Silent day/month swap: 7 of 9 sampled values are ISO, which is under the
    0.8 threshold, so dayfirst=True is applied to the whole column and every
    valid ISO date is reinterpreted. This is pinned so the legacy path can be
    proven unchanged; it is the strongest single argument for governance."""
    out = clean_dataframe(pd.DataFrame({"order_date": obj([
        "2024-01-05", "2024-02-06", "05/03/2024", "x",
        "2024-06-01", "2024-07-01", "2024-08-01", "2024-09-01", "2024-10-01",
    ])}))
    values = out["order_date"].tolist()
    assert values[0] == dt.date(2024, 5, 1)   # was 2024-01-05
    assert values[1] == dt.date(2024, 6, 2)   # was 2024-02-06
    assert pd.isna(values[2]) and pd.isna(values[3])
    assert values[4] == dt.date(2024, 1, 6)   # was 2024-06-01


def test_legacy_pins_iso_dates_are_kept_when_sample_is_iso():
    out = clean_dataframe(pd.DataFrame({"order_date": obj(["2024-01-05", "2024-02-06", "2024-03-07"])}))
    assert out["order_date"].tolist() == [dt.date(2024, 1, 5), dt.date(2024, 2, 6), dt.date(2024, 3, 7)]


@pytest.mark.skipif(int(pd.__version__.split(".")[0]) < 3, reason="pandas 3 default string dtype only")
def test_legacy_pins_that_pandas3_default_string_dtype_bypasses_object_branches():
    """Under pandas 3 the default string dtype is `str`, so the legacy checks
    `dtype == "object"` and `str(dtype) == "string"` are both false: blank
    normalization, trimming, and numeric coercion do not fire on freshly-read
    string columns, while name-based date parsing still does. The legacy
    cleaner's behaviour therefore depends on the pandas major version, which
    pyproject leaves unpinned (>=2.2.0)."""
    default = pd.DataFrame({
        "amount": ["100", "200", "300", "400", "500", "600", "700", "800", "900", "ABC"],
        "code": ["A-1", "-", "--", "NA", "n/a", "none", "B", "C", "D", "E"],
        "note": ["  padded  ", "x", "y", "z", "w", "v", "u", "t", "s", "r"],
    })
    out = clean_dataframe(default)
    assert str(out["amount"].dtype) == "str"
    assert out["amount"].tolist()[9] == "ABC"          # not coerced
    assert out["code"].tolist()[1:6] == ["-", "--", "NA", "n/a", "none"]  # not blanked
    assert out["note"].tolist()[0] == "  padded  "     # not trimmed
