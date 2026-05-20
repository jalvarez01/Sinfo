"""
Predictor con Seasonality usando Prophet
==========================================
Captura tendencias, estacionalidad semanal y anual de consumo de insumos.
"""

import pandas as pd
import warnings
warnings.filterwarnings("ignore")

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False


def predict_with_seasonality(df: pd.DataFrame, producto: str, horizon_weeks: int = 4) -> float:
    """Predice consumo futuro con seasonality usando Prophet.
    
    Si hay <14 registros o Prophet no está disponible, retorna None.
    
    Args:
        df: DataFrame con columnas: fecha, producto, cantidad
        producto: Nombre del producto a predecir
        horizon_weeks: Semanas a proyectar (default: 4)
        
    Returns:
        float: cantidad proyectada para el horizonte, o None si no se puede predecir
    """
    
    if not PROPHET_AVAILABLE:
        return None
    
    # Filtrar datos del producto
    df_producto = df[df["producto"] == producto].copy()
    
    if len(df_producto) < 14:
        return None
    
    # Agrupar por día y sumar
    df_daily = df_producto.groupby("fecha")["cantidad"].sum().reset_index()
    df_daily.columns = ["ds", "y"]
    
    try:
        # Crear modelo Prophet
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.95,
            changepoint_prior_scale=0.05
        )
        
        # Entrenar sin verbose
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit(df_daily)
        
        # Hacer predicción
        future = model.make_future_dataframe(periods=horizon_weeks * 7)
        forecast = model.predict(future)
        
        # Tomar solo las últimas horizon_weeks
        forecast_period = forecast.tail(horizon_weeks * 7)
        proyectado = forecast_period["yhat"].sum()
        
        # Asegurar que sea positivo
        return max(proyectado, 0)
    
    except Exception:
        return None


def generate_predictions_seasonal(
    df: pd.DataFrame,
    horizon_weeks: int = 4,
    sede: str = None,
    use_prophet: bool = True
) -> pd.DataFrame:
    """Genera predicciones con seasonality.
    
    Args:
        df: DataFrame con histórico limpio
        horizon_weeks: Semanas a proyectar
        sede: Filtrar por sucursal (opcional)
        use_prophet: Usar Prophet si está disponible, sino usar regresión lineal
        
    Returns:
        DataFrame con columnas: producto, ventas_proyectadas
    """
    
    # Filtrar por sede si es especificada
    if sede and "sucursal" in df.columns:
        df_filtered = df[df["sucursal"] == sede].copy()
    else:
        df_filtered = df.copy()
    
    productos = df_filtered["producto"].unique()
    predictions_list = []
    
    for producto in productos:
        # Intentar Prophet primero
        if use_prophet and PROPHET_AVAILABLE:
            qty = predict_with_seasonality(df_filtered, producto, horizon_weeks)
            if qty is not None:
                predictions_list.append({
                    "producto": producto,
                    "ventas_proyectadas": qty,
                    "metodo": "Prophet"
                })
                continue
        
        # Fallback: regresión lineal simple
        try:
            from sklearn.linear_model import LinearRegression
            import numpy as np
            
            df_producto = df_filtered[df_filtered["producto"] == producto].copy()
            
            if len(df_producto) < 3:
                continue
            
            # Agrupar por semana
            df_producto["semana"] = df_producto["fecha"].dt.isocalendar().week
            weekly_sales = df_producto.groupby("semana")["cantidad"].sum()
            
            if len(weekly_sales) < 2:
                continue
            
            # Fit lineal
            X = np.array(range(len(weekly_sales))).reshape(-1, 1)
            y = weekly_sales.values
            model = LinearRegression()
            model.fit(X, y)
            
            # Predecir
            future_X = np.array(range(len(weekly_sales), len(weekly_sales) + horizon_weeks)).reshape(-1, 1)
            future_y = model.predict(future_X)
            proyectado = np.sum(future_y)
            
            predictions_list.append({
                "producto": producto,
                "ventas_proyectadas": max(proyectado, 0),
                "metodo": "LinearRegression"
            })
        except Exception:
            continue
    
    result = pd.DataFrame(predictions_list)
    result = result.sort_values("ventas_proyectadas", ascending=False).reset_index(drop=True)
    
    return result
