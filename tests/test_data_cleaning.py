"""Tests para el módulo de limpieza de datos (data_cleaning.py)."""

import os
import tempfile

import pandas as pd
import pytest

from src.data_cleaning import (
    clean_historical_data,
    load_historical_data,
    normalize_text_columns,
    remove_duplicates,
    remove_invalid_quantities,
)


def _make_df(rows):
    return pd.DataFrame(rows)


class TestRemoveDuplicates:
    def test_removes_exact_duplicates(self):
        df = _make_df([
            {"fecha": "2024-01-01", "producto": "A", "cantidad": 2},
            {"fecha": "2024-01-01", "producto": "A", "cantidad": 2},
            {"fecha": "2024-01-02", "producto": "B", "cantidad": 3},
        ])
        clean, removed = remove_duplicates(df)
        assert removed == 1
        assert len(clean) == 2

    def test_no_duplicates_unchanged(self):
        df = _make_df([
            {"fecha": "2024-01-01", "producto": "A", "cantidad": 2},
            {"fecha": "2024-01-02", "producto": "B", "cantidad": 3},
        ])
        clean, removed = remove_duplicates(df)
        assert removed == 0
        assert len(clean) == 2

    def test_all_duplicates(self):
        row = {"fecha": "2024-01-01", "producto": "A", "cantidad": 1}
        df = _make_df([row, row, row])
        clean, removed = remove_duplicates(df)
        assert removed == 2
        assert len(clean) == 1


class TestRemoveInvalidQuantities:
    def test_removes_negative_quantities(self):
        df = _make_df([
            {"fecha": "2024-01-01", "producto": "A", "cantidad": -5},
            {"fecha": "2024-01-02", "producto": "B", "cantidad": 3},
        ])
        clean, removed = remove_invalid_quantities(df)
        assert removed == 1
        assert (clean["cantidad"] > 0).all()

    def test_removes_zero_quantities(self):
        df = _make_df([
            {"fecha": "2024-01-01", "producto": "A", "cantidad": 0},
            {"fecha": "2024-01-02", "producto": "B", "cantidad": 1},
        ])
        clean, removed = remove_invalid_quantities(df)
        assert removed == 1

    def test_removes_null_quantities(self):
        df = _make_df([
            {"fecha": "2024-01-01", "producto": "A", "cantidad": None},
            {"fecha": "2024-01-02", "producto": "B", "cantidad": 2},
        ])
        clean, removed = remove_invalid_quantities(df)
        assert removed == 1
        assert len(clean) == 1

    def test_valid_data_unchanged(self):
        df = _make_df([
            {"fecha": "2024-01-01", "producto": "A", "cantidad": 1},
            {"fecha": "2024-01-02", "producto": "B", "cantidad": 10},
        ])
        clean, removed = remove_invalid_quantities(df)
        assert removed == 0
        assert len(clean) == 2


class TestNormalizeTextColumns:
    def test_strips_whitespace(self):
        df = _make_df([{"producto": "  Hamburguesa  ", "sucursal": " Centro "}])
        clean = normalize_text_columns(df)
        assert clean["producto"].iloc[0] == "Hamburguesa"
        assert clean["sucursal"].iloc[0] == "Centro"

    def test_handles_missing_nota_column(self):
        df = _make_df([{"producto": " A ", "sucursal": " B "}])
        clean = normalize_text_columns(df)
        assert "nota" not in clean.columns


class TestCleanHistoricalData:
    def test_full_pipeline_with_csv(self):
        rows = [
            {"fecha": "2024-01-01", "producto": "A", "sucursal": "Centro", "cantidad": 5, "precio_unitario": 10000, "nota": ""},
            {"fecha": "2024-01-01", "producto": "A", "sucursal": "Centro", "cantidad": 5, "precio_unitario": 10000, "nota": ""},  # duplicate
            {"fecha": "2024-01-02", "producto": "B", "sucursal": "Norte", "cantidad": -1, "precio_unitario": 8000, "nota": "error"},  # invalid
            {"fecha": "2024-01-03", "producto": "C", "sucursal": "Sur", "cantidad": 3, "precio_unitario": 12000, "nota": ""},
        ]
        df = pd.DataFrame(rows)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            tmp_path = f.name
        try:
            clean, report = clean_historical_data(tmp_path)
            assert report["registros_iniciales"] == 4
            assert report["duplicados_eliminados"] == 1
            assert report["invalidos_eliminados"] == 1
            assert report["registros_finales"] == 2
        finally:
            os.unlink(tmp_path)

    def test_output_sorted_by_date(self):
        rows = [
            {"fecha": "2024-03-01", "producto": "A", "sucursal": "S1", "cantidad": 2, "precio_unitario": 5000, "nota": ""},
            {"fecha": "2024-01-01", "producto": "B", "sucursal": "S2", "cantidad": 1, "precio_unitario": 5000, "nota": ""},
        ]
        df = pd.DataFrame(rows)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            tmp_path = f.name
        try:
            clean, _ = clean_historical_data(tmp_path)
            assert clean["fecha"].iloc[0] <= clean["fecha"].iloc[1]
        finally:
            os.unlink(tmp_path)
