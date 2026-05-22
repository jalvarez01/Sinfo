"""
SIPS API v2 - Cloud Run
=========================
Endpoints:
  POST /predict                  → Modo COMPRAS (fallback, datos actuales)
  POST /predict-from-sales       → Modo VENTAS (preciso, cuando lleguen los datos)
  POST /predict/sede/<sede>      → Una sola sede (cualquier modo)
  GET  /health                   → Health check
  GET  /                         → Info
  GET  /detect-sales-schema      → Auto-detecta estructura de pestaña Ventas
"""

import os
from datetime import datetime
from flask import Flask, jsonify, request
import json
import pandas as pd

from src.data_cleaning import clean_dataframe
from src.validation import validate_historical_data
from src.seasonal_predictor import generate_predictions_seasonal
from src.sheets_loader import (
    load_historical_from_sheets,
    load_inventory_from_sheets,
    load_recipe_from_sheets,
    load_sheet_as_dataframe,
)
from src.sales_loader import load_sales_from_sheets, auto_detect_schema
from src.sales_to_consumption import convert_sales_to_consumption
from src.ingredient_calculator import (
    add_inventory_context,
    normalize_inventory_dataframe,
)

import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# ─────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────

DEFAULT_SEDES = ["S-01", "S-02", "S-03", "S-04"]
SEDES_NAMES = {
    "S-01": "Gastrobar",
    "S-02": "Express",
    "S-03": "Bistro",
    "S-04": "Mekato",
}
DEFAULT_WEEKS = 4

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials", "google_service_account.json")


# ─────────────────────────────────────────────────────────
# HOME / HEALTH
# ─────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "SIPS - Sistema de Pedido Sugerido",
        "version": "2.0",
        "sedes": SEDES_NAMES,
        "endpoints": {
            "POST /predict": "Modo COMPRAS (Consolidado_productos)",
            "POST /predict-from-sales": "Modo VENTAS (más preciso, requiere pestaña Ventas)",
            "POST /predict/sede/<sede>": "Una sola sede",
            "GET /detect-sales-schema": "Auto-detecta columnas de pestaña Ventas",
            "GET /health": "Health check",
        },
        "improvements_v2": [
            "Mediana en lugar de promedio (robusto a outliers)",
            "Cap por percentil P95",
            "Filtros IQR antes de entrenar",
            "Sanity checks (predicción no puede ser >2x el máximo histórico real)",
            "Auto-detección de columnas de Ventas",
            "Cruce ventas × recetas = consumo real",
            "Indicador de confiabilidad (ALTA/MEDIA/BAJA)",
        ],
        "status": "online"
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


# ─────────────────────────────────────────────────────────
# AUTO-DETECT
# ─────────────────────────────────────────────────────────

@app.route("/detect-sales-schema", methods=["GET"])
def detect_schema():
    """Detecta estructura de la pestaña de Ventas."""
    try:
        sheet_name = request.args.get("sheet", os.getenv("SHEET_VENTAS", "Ventas"))
        df = load_sheet_as_dataframe(sheet_name)
        schema = auto_detect_schema(df)
        
        return jsonify({
            "status": "success",
            "sheet_name": sheet_name,
            "columns_found": list(df.columns),
            "schema_detected": schema,
            "sample_rows": df.head(3).to_dict(orient="records"),
            "next_step": "Si los campos críticos (fecha, producto, cantidad) estan OK, usa POST /predict-from-sales"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────────────────────
# PREDICT v1 (modo COMPRAS — fallback)
# ─────────────────────────────────────────────────────────

@app.route("/predict", methods=["POST"])
def predict_compras():
    """Predice con datos de compras (Consolidado_productos)."""
    try:
        data = request.get_json(silent=True) or {}
        weeks = data.get("weeks", DEFAULT_WEEKS)
        sedes = data.get("sedes", DEFAULT_SEDES)
        write_to_sheets = data.get("write_to_sheets", True)
        
        result = run_pipeline_compras(weeks=weeks, sedes=sedes)
        
        if write_to_sheets:
            write_to_sheets_tab(result["predictions"], sheet_tab="SIPS_Sugerencias")
        
        return jsonify({
            "status": "success",
            "mode": "compras_v2",
            "timestamp": datetime.now().isoformat(),
            "summary": result["summary"],
            "predictions": result["predictions"][:50],
            "total_records": len(result["predictions"])
        })
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────────────────────
# PREDICT v2 (modo VENTAS — preciso)
# ─────────────────────────────────────────────────────────

@app.route("/predict-from-sales", methods=["POST"])
def predict_from_sales():
    """Predice convirtiendo ventas × recetas = consumo."""
    try:
        data = request.get_json(silent=True) or {}
        weeks = data.get("weeks", DEFAULT_WEEKS)
        sedes = data.get("sedes", DEFAULT_SEDES)
        column_mapping = data.get("column_mapping")
        write_to_sheets = data.get("write_to_sheets", True)
        
        result = run_pipeline_ventas(
            weeks=weeks, sedes=sedes, column_mapping=column_mapping
        )
        
        if write_to_sheets:
            write_to_sheets_tab(result["predictions"], sheet_tab="SIPS_Sugerencias")
        
        return jsonify({
            "status": "success",
            "mode": "ventas_v2_preciso",
            "timestamp": datetime.now().isoformat(),
            "summary": result["summary"],
            "predictions": result["predictions"][:50],
            "total_records": len(result["predictions"])
        })
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────────────────────
# PIPELINES
# ─────────────────────────────────────────────────────────

def run_pipeline_compras(weeks: int, sedes: list) -> dict:
    """Pipeline con datos de compras (Consolidado_productos)."""
    df_raw = load_historical_from_sheets()
    df_clean, report = clean_dataframe(df_raw)
    validation = validate_historical_data(df_clean)
    
    has_sede = "sucursal" in df_clean.columns
    sedes_a_procesar = sedes if has_sede else [None]
    
    all_predictions = []
    for sede in sedes_a_procesar:
        predictions = generate_predictions_seasonal(
            df_clean, horizon_weeks=weeks, sede=sede
        )
        if len(predictions) > 0:
            predictions["sede"] = sede or "CONSOLIDADO"
            all_predictions.append(predictions)
    
    if not all_predictions:
        raise ValueError("No se generaron predicciones")
    
    pred_combined = pd.concat(all_predictions, ignore_index=True)
    pred_combined = pred_combined.rename(columns={
        "producto": "insumo",
        "ventas_proyectadas": "cantidad_requerida"
    })
    
    try:
        inv_raw = load_inventory_from_sheets()
        inventory = normalize_inventory_dataframe(inv_raw)
        pred_combined = add_inventory_context(pred_combined, inventory)
    except Exception:
        pass
    
    return {
        "summary": {
            "modo": "COMPRAS",
            "registros_iniciales": report["registros_iniciales"],
            "registros_finales": report["registros_finales"],
            "productos_predichos": len(pred_combined),
            "sedes_procesadas": len(sedes_a_procesar),
            "horizonte_semanas": weeks,
            "validacion": {
                "huecos_detectados": validation["huecos_detectados"],
                "outliers": validation["outliers_detectados"],
                "advertencia": "Los datos son compras, no consumo real. Error esperado: 20-30%."
            }
        },
        "predictions": pred_combined.to_dict(orient="records")
    }


def run_pipeline_ventas(weeks: int, sedes: list, column_mapping: dict = None) -> dict:
    """Pipeline con datos de ventas (PRECISO)."""
    sales_df = load_sales_from_sheets(column_mapping=column_mapping)
    recipes_df = load_recipe_from_sheets()
    consumption_df = convert_sales_to_consumption(
        sales_df, recipes_df, fuzzy_matching=True
    )
    
    if len(consumption_df) == 0:
        raise ValueError("No se generó consumo. Verifica que recetas y ventas tengan nombres compatibles.")
    
    df_clean, report = clean_dataframe(consumption_df)
    validation = validate_historical_data(df_clean)
    
    has_sede = "sucursal" in df_clean.columns or "sede" in df_clean.columns
    sedes_a_procesar = sedes if has_sede else [None]
    
    all_predictions = []
    for sede in sedes_a_procesar:
        predictions = generate_predictions_seasonal(
            df_clean, horizon_weeks=weeks, sede=sede
        )
        if len(predictions) > 0:
            predictions["sede"] = sede or "CONSOLIDADO"
            all_predictions.append(predictions)
    
    if not all_predictions:
        raise ValueError("No se generaron predicciones")
    
    pred_combined = pd.concat(all_predictions, ignore_index=True)
    pred_combined = pred_combined.rename(columns={
        "producto": "insumo",
        "ventas_proyectadas": "cantidad_requerida"
    })
    
    try:
        inv_raw = load_inventory_from_sheets()
        inventory = normalize_inventory_dataframe(inv_raw)
        pred_combined = add_inventory_context(pred_combined, inventory)
    except Exception:
        pass
    
    return {
        "summary": {
            "modo": "VENTAS_PRECISO",
            "ventas_procesadas": len(sales_df),
            "registros_de_consumo": report["registros_iniciales"],
            "productos_predichos": len(pred_combined),
            "sedes_procesadas": len(sedes_a_procesar),
            "horizonte_semanas": weeks,
            "metodo": "ventas × recetas = consumo real",
            "error_esperado": "10-15%"
        },
        "predictions": pred_combined.to_dict(orient="records")
    }


# ─────────────────────────────────────────────────────────
# WRITE TO SHEETS
# ─────────────────────────────────────────────────────────

def write_to_sheets_tab(predictions: list, sheet_tab: str = "SIPS_Sugerencias") -> None:
    """Escribe predicciones a una pestaña."""
    with open(CREDENTIALS_PATH) as f:
        creds_dict = json.load(f)
    
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    
    gc = gspread.authorize(creds)
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    sh = gc.open_by_key(sheet_id)
    
    try:
        ws = sh.worksheet(sheet_tab)
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_tab, rows=1000, cols=15)
    
    if predictions:
        df = pd.DataFrame(predictions)
        df["fecha_generacion"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        df["estado"] = "PENDIENTE_REVISION"
        df["cantidad_final_aprobada"] = ""
        df["chef_aprobador"] = ""
        df["fecha_aprobacion"] = ""
        
        ordered = [
            "sede", "insumo", "cantidad_requerida",
            "consumo_semanal_tipico", "confiabilidad",
            "metodo", "n_semanas_historico", "advertencias",
            "estado", "cantidad_final_aprobada",
            "chef_aprobador", "fecha_aprobacion", "fecha_generacion"
        ]
        cols_final = [c for c in ordered if c in df.columns]
        df = df[cols_final]
        df = df.fillna("")
        
        ws.update([df.columns.values.tolist()] + df.values.tolist())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
