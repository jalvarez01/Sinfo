"""
Ingredient Calculator
=====================
Calcula las cantidades de materia prima necesarias vinculando las predicciones
de ventas con la receta estándar de Inversiones Pulso S.A.S.

Flujo:
- Carga la receta estándar (producto → insumo → cantidad_por_unidad).
- Multiplica las ventas proyectadas de cada producto por la cantidad de cada insumo
  que requiere su receta.
- Agrupa por insumo para obtener el total de cada materia prima requerida.
"""

import pandas as pd


def load_standard_recipe(filepath: str) -> pd.DataFrame:
    """Carga el archivo CSV de la receta estándar.

    Args:
        filepath: Ruta al archivo CSV con la receta estándar.

    Returns:
        DataFrame con columnas ['producto', 'insumo', 'cantidad_por_unidad', 'unidad_medida'].
    """
    df = pd.read_csv(filepath)
    required_cols = {"producto", "insumo", "cantidad_por_unidad", "unidad_medida"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Columnas faltantes en la receta estándar: {missing}")
    return df


def calculate_ingredient_requirements(
    predictions_df: pd.DataFrame,
    recipe_df: pd.DataFrame,
) -> pd.DataFrame:
    """Calcula las cantidades totales de insumos requeridas.

    Vincula las ventas proyectadas con la receta estándar para calcular la
    cantidad de cada insumo necesaria para el horizonte de predicción.

    Args:
        predictions_df: DataFrame con columnas ['producto', 'ventas_proyectadas'].
        recipe_df: DataFrame con columnas ['producto', 'insumo', 'cantidad_por_unidad',
                   'unidad_medida'].

    Returns:
        DataFrame con columnas ['insumo', 'unidad_medida', 'cantidad_requerida']
        ordenado de mayor a menor cantidad requerida.
    """
    merged = recipe_df.merge(predictions_df, on="producto", how="inner")

    merged["cantidad_requerida"] = merged["cantidad_por_unidad"] * merged["ventas_proyectadas"]

    ingredient_totals = (
        merged.groupby(["insumo", "unidad_medida"], as_index=False)["cantidad_requerida"]
        .sum()
    )

    ingredient_totals["cantidad_requerida"] = ingredient_totals["cantidad_requerida"].round(2)

    ingredient_totals = ingredient_totals.sort_values(
        "cantidad_requerida", ascending=False
    ).reset_index(drop=True)

    return ingredient_totals
