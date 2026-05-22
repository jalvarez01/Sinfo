"""
Sales Loader - Auto-detector de estructura
=============================================
Carga ventas desde Google Sheets adaptándose a cualquier estructura
que Los Birria nos entregue, sin importar nombres de columnas.

Detecta automáticamente:
  - Columna de fecha (cualquier formato)
  - Columna de producto/plato (texto largo)
  - Columna de cantidad (numérico)
  - Columna de sede (opcional)
"""

import os
import re
import pandas as pd
from typing import Optional, Dict


# Patrones de detección (orden de prioridad)
FECHA_PATTERNS = [
    r"fecha", r"date", r"fec", r"día", r"day", r"timestamp", r"created"
]

PRODUCTO_PATTERNS = [
    r"plato", r"producto", r"item", r"nombre.*plato", r"nombre.*producto",
    r"descripcion", r"description", r"name", r"nombre"
]

CANTIDAD_PATTERNS = [
    r"cantidad.*vend", r"vendid", r"qty", r"cantidad", r"unidades",
    r"quantity", r"total.*vent", r"ventas", r"count"
]

SEDE_PATTERNS = [
    r"sede", r"sucursal", r"local", r"tienda", r"branch", r"ubicacion",
    r"location", r"store"
]

PRECIO_PATTERNS = [
    r"precio", r"price", r"valor", r"total", r"importe"
]


def detect_column(df: pd.DataFrame, patterns: list, required_type: str = None) -> Optional[str]:
    """Detecta columna por patrones regex + tipo de dato.
    
    Args:
        df: DataFrame
        patterns: Lista de regex a buscar en nombres de columnas
        required_type: 'numeric', 'date', 'text', o None
    
    Returns:
        Nombre de columna detectada o None
    """
    candidates = []
    
    for col in df.columns:
        col_clean = str(col).lower().strip()
        
        for pattern in patterns:
            if re.search(pattern, col_clean, re.IGNORECASE):
                # Verificar tipo si es requerido
                if required_type == "numeric":
                    if pd.api.types.is_numeric_dtype(df[col]) or _can_be_numeric(df[col]):
                        candidates.append(col)
                        break
                elif required_type == "date":
                    if pd.api.types.is_datetime64_any_dtype(df[col]) or _can_be_date(df[col]):
                        candidates.append(col)
                        break
                elif required_type == "text":
                    if df[col].dtype == "object":
                        candidates.append(col)
                        break
                else:
                    candidates.append(col)
                    break
    
    return candidates[0] if candidates else None


def _can_be_numeric(series: pd.Series) -> bool:
    """Verifica si una serie puede convertirse a numérico."""
    try:
        pd.to_numeric(series.dropna().head(10), errors="raise")
        return True
    except (ValueError, TypeError):
        return False


def _can_be_date(series: pd.Series) -> bool:
    """Verifica si una serie puede convertirse a fecha."""
    try:
        pd.to_datetime(series.dropna().head(10), errors="raise")
        return True
    except (ValueError, TypeError):
        return False


def auto_detect_schema(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """Auto-detecta el esquema de un DataFrame de ventas.
    
    Returns:
        dict con columnas detectadas: {fecha, producto, cantidad, sede, precio}
    """
    schema = {
        "fecha": detect_column(df, FECHA_PATTERNS, "date"),
        "producto": detect_column(df, PRODUCTO_PATTERNS, "text"),
        "cantidad": detect_column(df, CANTIDAD_PATTERNS, "numeric"),
        "sede": detect_column(df, SEDE_PATTERNS, "text"),
        "precio": detect_column(df, PRECIO_PATTERNS, "numeric"),
    }
    
    return schema


def load_sales_from_sheets(
    sheet_name: Optional[str] = None,
    sheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
    column_mapping: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """Carga ventas desde Google Sheets con auto-detección de columnas.
    
    Args:
        sheet_name: Nombre de la pestaña (default: env SHEET_VENTAS o "Ventas")
        sheet_id: ID del Sheet
        credentials_path: Ruta a credenciales
        column_mapping: Override manual del auto-detect, ej:
            {"fecha": "Mi_Fecha", "producto": "Plato_Vendido", "cantidad": "Qty"}
    
    Returns:
        DataFrame normalizado con columnas: fecha, producto, cantidad, sede (opcional)
    """
    from src.sheets_loader import load_sheet_as_dataframe
    
    name = sheet_name or os.getenv("SHEET_VENTAS", "Ventas")
    df_raw = load_sheet_as_dataframe(name, sheet_id, credentials_path)
    df_raw.columns = df_raw.columns.str.strip()
    
    # Auto-detect o usar mapping manual
    if column_mapping:
        schema = column_mapping
    else:
        schema = auto_detect_schema(df_raw)
    
    print(f"\n[SALES LOADER] Esquema detectado en pestaña '{name}':")
    for key, value in schema.items():
        marker = "✓" if value else "✗"
        print(f"  {marker} {key}: {value}")
    
    # Validar campos críticos
    missing = [k for k in ["fecha", "producto", "cantidad"] if not schema.get(k)]
    if missing:
        raise ValueError(
            f"No se detectaron columnas críticas: {missing}\n"
            f"Columnas disponibles: {list(df_raw.columns)}\n"
            f"Pasa column_mapping manual o define en .env:\n"
            f"  SHEET_VENTAS_COL_FECHA=nombre_real\n"
            f"  SHEET_VENTAS_COL_PRODUCTO=nombre_real\n"
            f"  SHEET_VENTAS_COL_CANTIDAD=nombre_real"
        )
    
    # Normalizar
    rename_map = {schema["fecha"]: "fecha",
                  schema["producto"]: "producto",
                  schema["cantidad"]: "cantidad"}
    
    if schema.get("sede"):
        rename_map[schema["sede"]] = "sede"
    
    if schema.get("precio"):
        rename_map[schema["precio"]] = "precio"
    
    df = df_raw.rename(columns=rename_map)
    
    # Conversiones
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce")
    
    # Limpiar nulos
    df = df.dropna(subset=["fecha", "producto", "cantidad"])
    df = df[df["cantidad"] > 0]
    
    print(f"  Registros cargados: {len(df):,}")
    print(f"  Rango: {df['fecha'].min().date()} → {df['fecha'].max().date()}")
    print(f"  Productos únicos: {df['producto'].nunique()}")
    if "sede" in df.columns:
        print(f"  Sedes: {df['sede'].unique().tolist()}")
    
    return df
