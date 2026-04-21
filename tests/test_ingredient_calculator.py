"""Tests para el calculador de insumos (ingredient_calculator.py)."""

import os
import tempfile

import pandas as pd
import pytest

from src.ingredient_calculator import (
    calculate_ingredient_requirements,
    load_standard_recipe,
)


def _make_recipe_csv(rows) -> str:
    df = pd.DataFrame(rows)
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    df.to_csv(f.name, index=False)
    f.close()
    return f.name


class TestLoadStandardRecipe:
    def test_loads_valid_csv(self):
        tmp = _make_recipe_csv([
            {"producto": "A", "insumo": "X", "cantidad_por_unidad": 100, "unidad_medida": "gramos"},
        ])
        try:
            df = load_standard_recipe(tmp)
            assert len(df) == 1
        finally:
            os.unlink(tmp)

    def test_raises_on_missing_columns(self):
        tmp = _make_recipe_csv([
            {"producto": "A", "insumo": "X"},  # missing columns
        ])
        try:
            with pytest.raises(ValueError, match="Columnas faltantes"):
                load_standard_recipe(tmp)
        finally:
            os.unlink(tmp)


class TestCalculateIngredientRequirements:
    def _base_recipe(self):
        return pd.DataFrame([
            {"producto": "Hamburguesa", "insumo": "Pan", "cantidad_por_unidad": 1, "unidad_medida": "unidad"},
            {"producto": "Hamburguesa", "insumo": "Carne", "cantidad_por_unidad": 150, "unidad_medida": "gramos"},
            {"producto": "Papas Fritas", "insumo": "Papa", "cantidad_por_unidad": 200, "unidad_medida": "gramos"},
        ])

    def _base_predictions(self, hamburguesa=100, papas=50):
        return pd.DataFrame([
            {"producto": "Hamburguesa", "ventas_proyectadas": hamburguesa},
            {"producto": "Papas Fritas", "ventas_proyectadas": papas},
        ])

    def test_returns_dataframe_with_expected_columns(self):
        result = calculate_ingredient_requirements(self._base_predictions(), self._base_recipe())
        assert set(result.columns) == {"insumo", "unidad_medida", "cantidad_requerida"}

    def test_multiplies_correctly(self):
        result = calculate_ingredient_requirements(self._base_predictions(hamburguesa=10, papas=5), self._base_recipe())
        carne = result[result["insumo"] == "Carne"]["cantidad_requerida"].values[0]
        assert carne == pytest.approx(150 * 10)
        papa = result[result["insumo"] == "Papa"]["cantidad_requerida"].values[0]
        assert papa == pytest.approx(200 * 5)

    def test_sorted_descending(self):
        result = calculate_ingredient_requirements(self._base_predictions(hamburguesa=100, papas=100), self._base_recipe())
        vals = result["cantidad_requerida"].tolist()
        assert vals == sorted(vals, reverse=True)

    def test_no_matching_products_returns_empty(self):
        predictions = pd.DataFrame([{"producto": "ProductoInexistente", "ventas_proyectadas": 100}])
        result = calculate_ingredient_requirements(predictions, self._base_recipe())
        assert len(result) == 0

    def test_same_ingredient_from_multiple_products_is_aggregated(self):
        recipe = pd.DataFrame([
            {"producto": "A", "insumo": "Sal", "cantidad_por_unidad": 5, "unidad_medida": "gramos"},
            {"producto": "B", "insumo": "Sal", "cantidad_por_unidad": 3, "unidad_medida": "gramos"},
        ])
        predictions = pd.DataFrame([
            {"producto": "A", "ventas_proyectadas": 10},
            {"producto": "B", "ventas_proyectadas": 10},
        ])
        result = calculate_ingredient_requirements(predictions, recipe)
        sal = result[result["insumo"] == "Sal"]["cantidad_requerida"].values[0]
        assert sal == pytest.approx((5 * 10) + (3 * 10))

    def test_zero_sales_produce_zero_ingredient(self):
        result = calculate_ingredient_requirements(self._base_predictions(hamburguesa=0, papas=0), self._base_recipe())
        assert (result["cantidad_requerida"] == 0).all()
