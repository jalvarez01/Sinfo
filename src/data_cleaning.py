"""
Data Cleaning Module
====================
Limpieza y normalización del histórico de ventas de Inversiones Pulso S.A.S.

Operaciones realizadas:
- Eliminación de registros duplicados exactos.
- Eliminación de registros con cantidades negativas o nulas (errores de captura).
- Normalización de fechas al tipo datetime.
- Eliminación de espacios adicionales en nombres de producto/sucursal.
- Informe de registros eliminados para trazabilidad.
"""

import pandas as pd


def _normalize_historical_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "ID": "id",
        "Fecha": "fecha",
        "Producto": "producto",
        "Sucursal": "sucursal",
        "Cantidad": "cantidad",
        "Precio_Unitario": "precio_unitario",
        "nota": "nota",
        "Nota": "nota",
    }
    existing_map = {src: dst for src, dst in rename_map.items() if src in df.columns}
    return df.rename(columns=existing_map)


def load_historical_data(filepath: str) -> pd.DataFrame:
    """Carga el archivo CSV del histórico de ventas.

    Args:
        filepath: Ruta al archivo CSV con el histórico de ventas.

    Returns:
        DataFrame con los datos cargados.
    """
    df = pd.read_csv(filepath)
    df = _normalize_historical_columns(df)
    if "fecha" not in df.columns:
        raise ValueError("El histórico de ventas debe incluir una columna de fecha.")
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    return df


def remove_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Elimina filas duplicadas exactas del DataFrame.

    Args:
        df: DataFrame con el histórico de ventas.

    Returns:
        Tupla (DataFrame limpio, número de duplicados eliminados).
    """
    original_len = len(df)
    df_clean = df.drop_duplicates()
    removed = original_len - len(df_clean)
    return df_clean, removed


def remove_invalid_quantities(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Elimina registros con cantidades inválidas (≤ 0 o nulas).

    Args:
        df: DataFrame con el histórico de ventas.

    Returns:
        Tupla (DataFrame limpio, número de registros inválidos eliminados).
    """
    original_len = len(df)
    df_clean = df[df["cantidad"].notna() & (df["cantidad"] > 0)].copy()
    removed = original_len - len(df_clean)
    return df_clean, removed


def normalize_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza columnas de texto: elimina espacios extra y unifica capitalización.

    Args:
        df: DataFrame con el histórico de ventas.

    Returns:
        DataFrame con columnas de texto normalizadas.
    """
    text_cols = ["producto", "sucursal", "nota"] if "nota" in df.columns else ["producto", "sucursal"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Pipeline de limpieza aplicado a un DataFrame ya cargado.

    Útil cuando los datos provienen de Google Sheets API en lugar de CSV.
    """
    df = _normalize_historical_columns(df.copy())
    if "fecha" not in df.columns:
        raise ValueError("El histórico debe incluir una columna de fecha.")
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

    initial_count = len(df)
    df = normalize_text_columns(df)
    df, duplicates_removed = remove_duplicates(df)
    df, invalid_removed = remove_invalid_quantities(df)
    df = df.sort_values("fecha").reset_index(drop=True)

    report = {
        "registros_iniciales": initial_count,
        "duplicados_eliminados": duplicates_removed,
        "invalidos_eliminados": invalid_removed,
        "registros_finales": len(df),
    }
    return df, report


def clean_historical_data(filepath: str) -> tuple[pd.DataFrame, dict]:
    """Pipeline completo de limpieza del histórico de ventas desde CSV."""
    df = load_historical_data(filepath)
    return clean_dataframe(df)
