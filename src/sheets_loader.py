"""
Google Sheets Loader — Doble fuente de credenciales
====================================================
Prioridad para encontrar credenciales:
  1. Parámetro explícito en función
  2. Variable de entorno GOOGLE_CREDENTIALS_PATH (.env)
  3. Default: credentials/google_service_account.json
"""

import os
import json
from typing import Optional

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials


# Ruta default a credenciales locales
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials", "google_service_account.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


def _resolve_credentials_path(credentials_path: Optional[str] = None) -> str:
    """Resuelve la ruta de credenciales según prioridad.
    
    Prioridad:
      1. Parámetro explícito (credentials_path)
      2. Variable de entorno GOOGLE_CREDENTIALS_PATH
      3. Default: credentials/google_service_account.json
    """
    # 1. Parámetro explícito
    if credentials_path:
        path = credentials_path
    # 2. Variable de entorno
    elif os.getenv("GOOGLE_CREDENTIALS_PATH"):
        path = os.getenv("GOOGLE_CREDENTIALS_PATH")
        # Si es ruta relativa, hacerla absoluta
        if not os.path.isabs(path):
            path = os.path.join(BASE_DIR, path)
    # 3. Default
    else:
        path = DEFAULT_CREDENTIALS_PATH
    
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No se encontraron credenciales en: {path}\n"
            f"Opciones:\n"
            f"  1. Coloca el archivo en: {DEFAULT_CREDENTIALS_PATH}\n"
            f"  2. O define GOOGLE_CREDENTIALS_PATH en .env\n"
            f"  3. O pásalo como parámetro a la función"
        )
    
    return path


def _get_gspread_client(credentials_path: Optional[str] = None) -> gspread.Client:
    """Crea cliente gspread autenticado."""
    path = _resolve_credentials_path(credentials_path)
    
    with open(path) as f:
        creds_dict = json.load(f)
    
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def _resolve_sheet_id(sheet_id: Optional[str] = None) -> str:
    """Resuelve el ID del Google Sheet."""
    resolved = sheet_id or os.getenv("GOOGLE_SHEET_ID")
    if not resolved:
        raise ValueError(
            "GOOGLE_SHEET_ID no definido.\n"
            "Defínelo en .env o pásalo como parámetro."
        )
    return resolved


def load_sheet_as_dataframe(
    sheet_name: str,
    sheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> pd.DataFrame:
    """Carga una pestaña como DataFrame.
    
    Args:
        sheet_name: Nombre de la pestaña.
        sheet_id: ID del Google Sheet (opcional, lee de .env si no se da).
        credentials_path: Ruta al JSON de credenciales (opcional).
    
    Returns:
        DataFrame con los datos de la pestaña.
    """
    gc = _get_gspread_client(credentials_path)
    sh = gc.open_by_key(_resolve_sheet_id(sheet_id))
    ws = sh.worksheet(sheet_name)
    df = pd.DataFrame(ws.get_all_records())
    df.columns = df.columns.str.strip()
    return df


def load_historical_from_sheets(
    sheet_name: Optional[str] = None,
    sheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> pd.DataFrame:
    """Carga el histórico de ventas desde Google Sheets."""
    name = sheet_name or os.getenv("SHEET_HISTORICO", "Consolidado_productos")
    df = load_sheet_as_dataframe(name, sheet_id, credentials_path)
    df.columns = df.columns.str.strip()
    
    rename_map = {
        "ID_Consolidado": "id",
        "Producto": "producto",
        "Cantidad_Total": "cantidad",
        "Fecha_Registro": "fecha",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    if "cantidad" in df.columns:
        df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce")
    
    return df


def load_recipe_from_sheets(
    sheet_name: Optional[str] = None,
    sheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> pd.DataFrame:
    """Carga la receta estándar desde Google Sheets."""
    name = sheet_name or os.getenv("SHEET_RECETA", "Recetas_")
    df = load_sheet_as_dataframe(name, sheet_id, credentials_path)
    df.columns = df.columns.str.strip()
    return df


def load_inventory_from_sheets(
    sheet_name: Optional[str] = None,
    sheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> pd.DataFrame:
    """Carga el inventario físico desde Google Sheets."""
    name = sheet_name or os.getenv("SHEET_INVENTARIO", "Inventario")
    df = load_sheet_as_dataframe(name, sheet_id, credentials_path)
    df.columns = df.columns.str.strip()
    
    if "Stock_Fisico" in df.columns:
        df["Stock_Fisico"] = pd.to_numeric(df["Stock_Fisico"], errors="coerce").fillna(0.0)
    return df