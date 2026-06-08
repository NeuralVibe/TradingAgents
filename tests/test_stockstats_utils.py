import pandas as pd

from tradingagents.dataflows.stockstats_utils import _clean_dataframe


def test_clean_dataframe_forward_fills_without_backfilling_leading_prices():
    raw = pd.DataFrame(
        {
            "Date": ["2026-05-01", "2026-05-04"],
            "Open": [None, 101.0],
            "High": [None, 103.0],
            "Low": [None, 99.0],
            "Close": [100.0, 102.0],
            "Volume": [None, 1000.0],
        }
    )

    cleaned = _clean_dataframe(raw)

    assert pd.isna(cleaned.iloc[0]["Open"])
    assert pd.isna(cleaned.iloc[0]["High"])
    assert pd.isna(cleaned.iloc[0]["Low"])
    assert pd.isna(cleaned.iloc[0]["Volume"])
    assert cleaned.iloc[1]["Open"] == 101.0
