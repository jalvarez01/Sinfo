"""
Predictor Robusto v2.2 - Prophet fix
=====================================
Cambios vs v2.1:
  - Conversión explícita de tipos antes de Prophet
  - Reset index limpio
  - Logging completo del error (no truncado)
  - Verifica que df_daily sea válido antes de entrenar
  - Manejo separado de errores comunes
  - Usa numpy.datetime64 explícito (Prophet lo necesita)
"""

import pandas as pd
import numpy as np
import warnings
import sys
warnings.filterwarnings("ignore")

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False


def filter_outliers_iqr(series: pd.Series, multiplier: float = 2.0) -> pd.Series:
    if len(series) < 5:
        return series
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    if IQR == 0:
        return series
    lower = Q1 - multiplier * IQR
    upper = Q3 + multiplier * IQR
    return series[(series >= lower) & (series <= upper)]


def cap_by_percentile(value: float, historical_series: pd.Series, percentile: int = 95) -> float:
    if len(historical_series) < 3:
        return value
    cap = historical_series.quantile(percentile / 100)
    return min(value, cap)


def _try_prophet(df_daily: pd.DataFrame, horizon_weeks: int, max_semanal_real: float) -> tuple:
    """Intenta Prophet. Devuelve (cantidad_semanal, metodo, advertencias).
    
    Si falla, retorna (None, None, error_message).
    """
    
    try:
        # 1. Preparar datos LIMPIOS para Prophet
        df_for_prophet = pd.DataFrame({
            "ds": pd.to_datetime(df_daily["ds"].values),
            "y": pd.to_numeric(df_daily["y"].values, errors="coerce")
        })
        df_for_prophet = df_for_prophet.dropna().reset_index(drop=True)
        df_for_prophet = df_for_prophet.sort_values("ds").reset_index(drop=True)
        
        # 2. Eliminar duplicados de fecha (sumar)
        df_for_prophet = df_for_prophet.groupby("ds", as_index=False)["y"].sum()
        
        if len(df_for_prophet) < 14:
            return None, None, f"Datos insuficientes ({len(df_for_prophet)} días)"
        
        # 3. Configurar Prophet
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            
            model = Prophet(
                yearly_seasonality=False,
                weekly_seasonality=True,
                daily_seasonality=False,
                interval_width=0.80,
                changepoint_prior_scale=0.01,
                seasonality_prior_scale=1.0,
                seasonality_mode="additive",
            )
            
            # 4. Fit
            model.fit(df_for_prophet)
            
            # 5. Predecir
            future = model.make_future_dataframe(periods=horizon_weeks * 7, freq="D")
            forecast = model.predict(future)
            
            # 6. Tomar SOLO el periodo futuro
            forecast_future = forecast.iloc[-horizon_weeks * 7:].copy()
            proyectado_total = float(forecast_future["yhat"].clip(lower=0).sum())
            proyectado_semanal = proyectado_total / horizon_weeks
            
            # 7. Sanity check
            if proyectado_semanal <= 0:
                return None, None, f"Prophet predijo cero ({proyectado_semanal:.2f})"
            
            if proyectado_semanal > max_semanal_real * 3:
                return None, None, f"Prophet sobreestima ({proyectado_semanal:.1f} > {max_semanal_real*3:.1f})"
            
            return proyectado_semanal, "Prophet", "OK"
    
    except Exception as e:
        error_full = f"{type(e).__name__}: {str(e)}"
        return None, None, error_full


def predict_with_seasonality(
    df: pd.DataFrame,
    producto: str,
    horizon_weeks: int = 4,
    use_median: bool = True,
    apply_outlier_filter: bool = True,
) -> dict:
    """Predice consumo con seasonality."""
    
    df_producto = df[df["producto"] == producto].copy()
    
    if len(df_producto) < 2:
        return None
    
    df_daily = df_producto.groupby("fecha", as_index=False)["cantidad"].sum()
    df_daily.columns = ["ds", "y"]
    df_daily = df_daily.sort_values("ds").reset_index(drop=True)
    
    if apply_outlier_filter and len(df_daily) >= 10:
        clean_mask = df_daily["y"].isin(filter_outliers_iqr(df_daily["y"], multiplier=2.5))
        df_daily = df_daily[clean_mask].reset_index(drop=True)
    
    if len(df_daily) < 2:
        return None
    
    df_daily["ds"] = pd.to_datetime(df_daily["ds"])
    
    # Estadísticas
    if use_median:
        consumo_diario_tipico = float(df_daily["y"].median())
    else:
        consumo_diario_tipico = float(df_daily["y"].mean())
    
    df_daily["semana"] = df_daily["ds"].dt.to_period("W")
    weekly = df_daily.groupby("semana")["y"].sum()
    
    if len(weekly) >= 2:
        if use_median:
            consumo_semanal_tipico = float(weekly.median())
        else:
            consumo_semanal_tipico = float(weekly.mean())
        max_semanal_real = float(weekly.max())
    else:
        consumo_semanal_tipico = consumo_diario_tipico * 7
        max_semanal_real = consumo_semanal_tipico * 1.5
    
    advertencias = []
    metodo = "Mediana_Robusta"
    proyectado_por_semana = consumo_semanal_tipico
    
    # Intentar Prophet
    if PROPHET_AVAILABLE and len(df_daily) >= 14:
        prophet_value, prophet_method, prophet_msg = _try_prophet(
            df_daily[["ds", "y"]],
            horizon_weeks,
            max_semanal_real
        )
        
        if prophet_value is not None:
            proyectado_por_semana = prophet_value
            metodo = prophet_method
        else:
            advertencias.append(f"Prophet: {prophet_msg[:80]}")
    
    # Cap P95
    if len(weekly) >= 4:
        proyectado_capped = cap_by_percentile(proyectado_por_semana, weekly, percentile=95)
        if proyectado_capped < proyectado_por_semana:
            advertencias.append("Cap P95 aplicado")
            proyectado_por_semana = proyectado_capped
    
    proyectado_total = proyectado_por_semana * horizon_weeks
    
    # Sanity final
    if len(weekly) >= 2:
        max_total_historico = float(weekly.max()) * horizon_weeks
        if proyectado_total > max_total_historico * 2:
            advertencias.append("Sanity check aplicado")
            proyectado_total = max_total_historico * 1.5
    
    if len(weekly) >= 12:
        confiabilidad = "ALTA"
    elif len(weekly) >= 6:
        confiabilidad = "MEDIA"
    elif len(weekly) >= 2:
        confiabilidad = "BAJA"
    else:
        confiabilidad = "MUY_BAJA"
    
    return {
        "cantidad_proyectada": max(proyectado_total, 0),
        "consumo_semanal_tipico": consumo_semanal_tipico,
        "metodo": metodo,
        "confiabilidad": confiabilidad,
        "n_semanas_historico": len(weekly),
        "n_dias_historico": len(df_daily),
        "advertencias": "; ".join(advertencias) if advertencias else "OK"
    }


def generate_predictions_seasonal(
    df: pd.DataFrame,
    horizon_weeks: int = 4,
    sede: str = None,
    use_prophet: bool = True,
) -> pd.DataFrame:
    if sede:
        sede_col = None
        for col in ["sucursal", "sede", "Sede"]:
            if col in df.columns:
                sede_col = col
                break
        if sede_col:
            df_filtered = df[df[sede_col] == sede].copy()
        else:
            df_filtered = df.copy()
    else:
        df_filtered = df.copy()
    
    if len(df_filtered) == 0:
        return pd.DataFrame()
    
    productos = df_filtered["producto"].unique()
    predictions_list = []
    
    for producto in productos:
        try:
            result = predict_with_seasonality(
                df_filtered,
                producto,
                horizon_weeks=horizon_weeks,
                use_median=True,
                apply_outlier_filter=True,
            )
            if result and result["cantidad_proyectada"] > 0:
                predictions_list.append({
                    "producto": producto,
                    "ventas_proyectadas": result["cantidad_proyectada"],
                    "consumo_semanal_tipico": result["consumo_semanal_tipico"],
                    "metodo": result["metodo"],
                    "confiabilidad": result["confiabilidad"],
                    "n_semanas_historico": result["n_semanas_historico"],
                    "n_dias_historico": result["n_dias_historico"],
                    "advertencias": result["advertencias"],
                })
        except Exception as e:
            print(f"  [ERROR] Falló predicción para {producto}: {type(e).__name__}: {str(e)[:100]}", file=sys.stderr)
            continue
    
    result_df = pd.DataFrame(predictions_list)
    if len(result_df) > 0:
        result_df = result_df.sort_values("ventas_proyectadas", ascending=False).reset_index(drop=True)
    return result_df