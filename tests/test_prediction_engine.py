"""Tests para el motor de predicción (prediction_engine.py)."""

import pandas as pd
import pytest

from src.prediction_engine import (
    aggregate_weekly_sales,
    generate_predictions,
    predict_product_sales,
)


def _weekly_df_from_dict(data: dict) -> pd.DataFrame:
    """Crea un DataFrame semanal de prueba desde un dict {semana_str: cantidad}."""
    rows = []
    for semana_str, cantidad in data.items():
        rows.append({"semana": pd.Timestamp(semana_str), "producto": "TestProducto", "cantidad_total": cantidad})
    return pd.DataFrame(rows)


class TestAggregateWeeklySales:
    def test_aggregates_by_week_and_product(self):
        df = pd.DataFrame({
            "fecha": pd.to_datetime(["2024-01-01", "2024-01-03", "2024-01-08"]),
            "producto": ["A", "A", "A"],
            "cantidad": [5, 3, 7],
        })
        weekly = aggregate_weekly_sales(df)
        assert "semana" in weekly.columns
        assert "cantidad_total" in weekly.columns
        # Week 1: 5+3=8, Week 2: 7
        week1 = weekly[weekly["semana"] == weekly["semana"].min()]["cantidad_total"].values[0]
        assert week1 == 8

    def test_multiple_products(self):
        df = pd.DataFrame({
            "fecha": pd.to_datetime(["2024-01-01", "2024-01-01"]),
            "producto": ["A", "B"],
            "cantidad": [4, 6],
        })
        weekly = aggregate_weekly_sales(df)
        assert set(weekly["producto"].unique()) == {"A", "B"}

    def test_returns_dataframe(self):
        df = pd.DataFrame({
            "fecha": pd.to_datetime(["2024-01-01"]),
            "producto": ["A"],
            "cantidad": [2],
        })
        result = aggregate_weekly_sales(df)
        assert isinstance(result, pd.DataFrame)


class TestPredictProductSales:
    def test_returns_float(self):
        weekly = _weekly_df_from_dict({
            "2024-01-01": 10, "2024-01-08": 12, "2024-01-15": 14,
        })
        result = predict_product_sales(weekly, "TestProducto", horizon_weeks=4)
        assert isinstance(result, float)

    def test_non_negative_prediction(self):
        # Declining trend — prediction should not go below 0
        weekly = _weekly_df_from_dict({
            "2024-01-01": 100, "2024-01-08": 1, "2024-01-15": 0,
        })
        result = predict_product_sales(weekly, "TestProducto", horizon_weeks=4)
        assert result >= 0.0

    def test_unknown_product_returns_zero(self):
        weekly = _weekly_df_from_dict({"2024-01-01": 5})
        result = predict_product_sales(weekly, "ProductoInexistente", horizon_weeks=4)
        assert result == 0.0

    def test_single_week_uses_average(self):
        weekly = _weekly_df_from_dict({"2024-01-01": 20})
        result = predict_product_sales(weekly, "TestProducto", horizon_weeks=4)
        assert result == pytest.approx(20 * 4, rel=1e-3)

    def test_increasing_trend_gives_higher_prediction(self):
        weekly = _weekly_df_from_dict({
            "2024-01-01": 10, "2024-01-08": 20, "2024-01-15": 30,
            "2024-01-22": 40, "2024-01-29": 50,
        })
        result = predict_product_sales(weekly, "TestProducto", horizon_weeks=4)
        historical_avg = (10 + 20 + 30 + 40 + 50) / 5
        assert result > historical_avg * 4 * 0.9  # at least close to or above average


class TestGeneratePredictions:
    def _make_clean_df(self):
        rng = pd.date_range("2024-01-01", periods=52, freq="W")
        rows = []
        for date in rng:
            rows.append({"fecha": date, "producto": "Hamburguesa", "cantidad": 50})
            rows.append({"fecha": date, "producto": "Papas Fritas", "cantidad": 80})
        return pd.DataFrame(rows)

    def test_returns_dataframe_with_expected_columns(self):
        df = self._make_clean_df()
        predictions = generate_predictions(df, horizon_weeks=4)
        assert set(predictions.columns) == {"producto", "ventas_proyectadas"}

    def test_all_products_present(self):
        df = self._make_clean_df()
        predictions = generate_predictions(df, horizon_weeks=4)
        assert set(predictions["producto"].unique()) == {"Hamburguesa", "Papas Fritas"}

    def test_predictions_are_non_negative(self):
        df = self._make_clean_df()
        predictions = generate_predictions(df, horizon_weeks=4)
        assert (predictions["ventas_proyectadas"] >= 0).all()

    def test_sorted_descending(self):
        df = self._make_clean_df()
        predictions = generate_predictions(df, horizon_weeks=4)
        vals = predictions["ventas_proyectadas"].tolist()
        assert vals == sorted(vals, reverse=True)
