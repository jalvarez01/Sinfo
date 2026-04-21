"""
Prediction Engine
=================
Motor de predicción de ventas para Inversiones Pulso S.A.S.

Estrategia:
- Agrega las ventas históricas por semana y por producto.
- Calcula la tendencia usando regresión lineal sobre la serie temporal.
- Proyecta las ventas para un horizonte futuro configurable (por defecto 4 semanas).
- Devuelve las cantidades predichas por producto.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


def aggregate_weekly_sales(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega las ventas históricas a nivel semanal por producto.

    Args:
        df: DataFrame limpio con columnas 'fecha', 'producto', 'cantidad'.

    Returns:
        DataFrame con columnas ['semana', 'producto', 'cantidad_total'].
    """
    df = df.copy()
    df["semana"] = df["fecha"].dt.to_period("W").dt.to_timestamp()
    weekly = (
        df.groupby(["semana", "producto"], as_index=False)["cantidad"]
        .sum()
        .rename(columns={"cantidad": "cantidad_total"})
    )
    return weekly


def predict_product_sales(
    weekly_df: pd.DataFrame,
    producto: str,
    horizon_weeks: int = 4,
) -> float:
    """Predice las ventas totales de un producto para las próximas *horizon_weeks* semanas.

    Usa regresión lineal sobre el historial semanal del producto. Si hay menos de
    2 semanas de datos, retorna el promedio histórico simple.

    Args:
        weekly_df: DataFrame con ventas semanales (salida de aggregate_weekly_sales).
        producto: Nombre del producto a predecir.
        horizon_weeks: Número de semanas a proyectar.

    Returns:
        Cantidad total proyectada (float ≥ 0).
    """
    product_data = weekly_df[weekly_df["producto"] == producto].sort_values("semana")

    if product_data.empty:
        return 0.0

    if len(product_data) < 2:
        return float(product_data["cantidad_total"].mean()) * horizon_weeks

    y = product_data["cantidad_total"].values
    x = np.arange(len(y)).reshape(-1, 1)

    model = LinearRegression()
    model.fit(x, y)

    future_x = np.arange(len(y), len(y) + horizon_weeks).reshape(-1, 1)
    predictions = model.predict(future_x)
    total = float(np.maximum(predictions, 0).sum())
    return total


def generate_predictions(
    df: pd.DataFrame,
    horizon_weeks: int = 4,
) -> pd.DataFrame:
    """Genera predicciones de ventas para todos los productos del histórico.

    Args:
        df: DataFrame limpio con columnas 'fecha', 'producto', 'cantidad'.
        horizon_weeks: Número de semanas a proyectar (default: 4).

    Returns:
        DataFrame con columnas ['producto', 'ventas_proyectadas'] ordenado de mayor
        a menor volumen proyectado.
    """
    weekly_df = aggregate_weekly_sales(df)
    productos = weekly_df["producto"].unique()

    results = []
    for producto in productos:
        projected = predict_product_sales(weekly_df, producto, horizon_weeks)
        results.append({"producto": producto, "ventas_proyectadas": round(projected, 2)})

    predictions_df = (
        pd.DataFrame(results)
        .sort_values("ventas_proyectadas", ascending=False)
        .reset_index(drop=True)
    )
    return predictions_df
