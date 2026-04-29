"""
Google Sheets Loader
====================
Carga datos directamente desde Google Sheets API en lugar de archivos CSV locales.
"""

import os
from typing import Optional

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_client(credentials_path: Optional[str] = None) -> gspread.Client:
    path = credentials_path or os.getenv("GOOGLE_CREDENTIALS_PATH")
    if not path:
        raise ValueError(
            "Credenciales no encontradas. Define GOOGLE_CREDENTIALS_PATH en .env"
        )
    if not os.path.exists(path):
        raise FileNotFoundError(f"Archivo de credenciales no encontrado: {path}")

    creds = Credentials.from_service_account_file(path, scopes=SCOPES)
    return gspread.authorize(creds)


def load_sheet_as_dataframe(
    sheet_name: str,
    sheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> pd.DataFrame:
    sid = sheet_id or os.getenv("GOOGLE_SHEET_ID")
    if not sid:
        raise ValueError("GOOGLE_SHEET_ID no definido en .env")

    client = _get_client(credentials_path)
    spreadsheet = client.open_by_key(sid)
    worksheet = spreadsheet.worksheet(sheet_name)
    records = worksheet.get_all_records()
    return pd.DataFrame(records)


def load_historical_from_sheets(
    sheet_name: Optional[str] = None,
    sheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> pd.DataFrame:
    name = sheet_name or os.getenv("SHEET_HISTORICO", "Consolidado_productos")
    df = load_sheet_as_dataframe(name, sheet_id, credentials_path)
    
    # Limpia espacios en blanco
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
    name = sheet_name or os.getenv("SHEET_RECETA", "Recetas_")
    df = load_sheet_as_dataframe(name, sheet_id, credentials_path)
    
    # Limpia espacios en blanco de los nombres de columnas
    df.columns = df.columns.str.strip()
    
    return df

def load_inventory_from_sheets(
    sheet_name: Optional[str] = None,
    sheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> pd.DataFrame:
    name = sheet_name or os.getenv("SHEET_INVENTARIO", "Inventario")
    df = load_sheet_as_dataframe(name, sheet_id, credentials_path)
    
    # Limpia espacios en blanco
    df.columns = df.columns.str.strip()
    
    if "Stock_Fisico" in df.columns:
        df["Stock_Fisico"] = pd.to_numeric(df["Stock_Fisico"], errors="coerce").fillna(0.0)
    return df