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


def _normalize_recipe_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "Producto": "producto",
        "Insumo": "insumo",
        "Cantidad_Por_Unidad": "cantidad_por_unidad",
        "Unidad_Medida": "unidad_medida",
    }
    existing_map = {src: dst for src, dst in rename_map.items() if src in df.columns}
    return df.rename(columns=existing_map)


def load_inventory(filepath: str) -> pd.DataFrame:
    """Carga el inventario físico actual.

    Args:
        filepath: Ruta al CSV con columnas ['Insumo', 'Stock_Fisico'].

    Returns:
        DataFrame normalizado con columnas ['insumo', 'stock_fisico'].
    """
    df = pd.read_csv(filepath)
    required_cols = {"Insumo", "Stock_Fisico"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Columnas faltantes en el inventario: {missing}")

    inventory = df[["Insumo", "Stock_Fisico"]].copy()
    inventory = inventory.rename(columns={"Insumo": "insumo", "Stock_Fisico": "stock_fisico"})
    inventory["insumo"] = inventory["insumo"].astype(str).str.strip()
    inventory["stock_fisico"] = pd.to_numeric(inventory["stock_fisico"], errors="coerce").fillna(0.0)
    return inventory


def load_standard_recipe(filepath: str) -> pd.DataFrame:
    """Carga el archivo CSV de la receta estándar.

    Args:
        filepath: Ruta al archivo CSV con la receta estándar.

    Returns:
        DataFrame con columnas ['producto', 'insumo', 'cantidad_por_unidad', 'unidad_medida'].
    """
    df = pd.read_csv(filepath)
    df = _normalize_recipe_columns(df)
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


def add_inventory_context(
    requirements_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
) -> pd.DataFrame:
    """Agrega el contexto de inventario físico a los requerimientos.

    Args:
        requirements_df: DataFrame con columnas ['insumo', 'unidad_medida', 'cantidad_requerida'].
        inventory_df: DataFrame con columnas ['insumo', 'stock_fisico'].

    Returns:
        DataFrame con columnas adicionales:
            - stock_fisico
            - faltante_vs_stock
            - alerta_stock
    """
    required_cols = {"insumo", "unidad_medida", "cantidad_requerida"}
    missing = required_cols - set(requirements_df.columns)
    if missing:
        raise ValueError(f"Columnas faltantes en requirements_df: {missing}")

    inventory_required_cols = {"insumo", "stock_fisico"}
    missing_inventory = inventory_required_cols - set(inventory_df.columns)
    if missing_inventory:
        raise ValueError(f"Columnas faltantes en inventory_df: {missing_inventory}")

    enriched = requirements_df.copy()
    inventory = inventory_df.copy()
    inventory["insumo"] = inventory["insumo"].astype(str).str.strip()

    enriched = enriched.merge(inventory, on="insumo", how="left")
    enriched["stock_fisico"] = pd.to_numeric(enriched["stock_fisico"], errors="coerce").fillna(0.0)
    enriched["faltante_vs_stock"] = (enriched["cantidad_requerida"] - enriched["stock_fisico"]).round(2)
    enriched["alerta_stock"] = enriched["faltante_vs_stock"] > 0
    return enriched
