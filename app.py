"""
SIPS API — Cloud Run
=====================
Expone el pipeline de predicción como API REST para AppSheet.

Endpoints:
  POST /predict              - Genera predicciones por sede
  POST /predict/sede/<sede>  - Predicción de una sola sede
  GET  /health               - Health check
  GET  /                     - Info general
"""

import os
from datetime import datetime
from flask import Flask, jsonify, request

from src.data_cleaning import clean_dataframe
from src.validation import validate_historical_data
from src.seasonal_predictor import generate_predictions_seasonal
from src.sheets_loader import (
    load_historical_from_sheets,
    load_inventory_from_sheets,
)
from src.ingredient_calculator import (
    add_inventory_context,
    normalize_inventory_dataframe,
)

import gspread
from google.oauth2.service_account import Credentials
import json
import pandas as pd

app = Flask(__name__)

# ─────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────

DEFAULT_SEDES = ["S-01", "S-02", "S-03", "S-04"]
DEFAULT_WEEKS = 4

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials", "google_service_account.json")


# ─────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def home():
    """Página principal con info del API."""
    return jsonify({
        "service": "SIPS - Sistema de Pedido Sugerido",
        "version": "1.0",
        "endpoints": {
            "POST /predict": "Genera predicciones para todas las sedes",
            "POST /predict/sede/<sede>": "Predicción una sola sede (ej: S-01)",
            "GET /health": "Health check"
        },
        "status": "online"
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check para Cloud Run."""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.route("/predict", methods=["POST"])
def predict_all():
    """Genera predicciones para todas las sedes.
    
    Body (opcional):
      {
        "weeks": 4,
        "sedes": ["S-01", "S-02", "S-03"],
        "write_to_sheets": true
      }
    
    Returns:
      JSON con predicciones por sede.
    """
    try:
        data = request.get_json(silent=True) or {}
        weeks = data.get("weeks", DEFAULT_WEEKS)
        sedes = data.get("sedes", DEFAULT_SEDES)
        write_to_sheets = data.get("write_to_sheets", True)
        
        # Pipeline completo
        result = run_prediction_pipeline(weeks=weeks, sedes=sedes)
        
        # Escribir resultados al Sheet (opcional)
        if write_to_sheets:
            write_predictions_to_sheets(result["predictions"])
        
        return jsonify({
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "summary": result["summary"],
            "predictions": result["predictions"][:50],  # Top 50 para respuesta
            "total_records": len(result["predictions"])
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route("/predict/sede/<sede>", methods=["POST"])
def predict_sede(sede):
    """Predicción de una sola sede.
    
    Args:
        sede: ID de sede (ej: S-01, S-02, S-03, S-04)
    """
    try:
        data = request.get_json(silent=True) or {}
        weeks = data.get("weeks", DEFAULT_WEEKS)
        
        result = run_prediction_pipeline(weeks=weeks, sedes=[sede])
        
        return jsonify({
            "status": "success",
            "sede": sede,
            "timestamp": datetime.now().isoformat(),
            "predictions": result["predictions"],
            "total_records": len(result["predictions"])
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ─────────────────────────────────────────────────────────
# LÓGICA DE NEGOCIO
# ─────────────────────────────────────────────────────────

def run_prediction_pipeline(weeks: int, sedes: list) -> dict:
    """Ejecuta el pipeline completo de predicción.
    
    Returns:
        dict con summary y predictions.
    """
    # 1. Cargar histórico
    df_raw = load_historical_from_sheets()
    df_clean, report = clean_dataframe(df_raw)
    
    # 2. Validar
    validation = validate_historical_data(df_clean)
    
    # 3. Predicciones (con o sin sede)
    has_sede = "sucursal" in df_clean.columns
    sedes_a_procesar = sedes if has_sede else [None]
    
    all_predictions = []
    
    for sede in sedes_a_procesar:
        predictions = generate_predictions_seasonal(
            df_clean,
            horizon_weeks=weeks,
            sede=sede,
            use_prophet=True
        )
        
        if len(predictions) > 0:
            predictions["sede"] = sede or "CONSOLIDADO"
            all_predictions.append(predictions)
    
    if not all_predictions:
        raise ValueError("No se generaron predicciones")
    
    predictions_combined = pd.concat(all_predictions, ignore_index=True)
    predictions_combined = predictions_combined.rename(columns={
        "producto": "insumo",
        "ventas_proyectadas": "cantidad_requerida"
    })
    
    # 4. Agregar inventario si existe
    try:
        inventory_raw = load_inventory_from_sheets()
        inventory = normalize_inventory_dataframe(inventory_raw)
        predictions_combined = add_inventory_context(predictions_combined, inventory)
    except Exception:
        pass
    
    # Convertir a JSON-friendly
    predictions_list = predictions_combined.to_dict(orient="records")
    
    return {
        "summary": {
            "registros_iniciales": report["registros_iniciales"],
            "registros_finales": report["registros_finales"],
            "productos_predichos": len(predictions_combined),
            "sedes_procesadas": len(sedes_a_procesar),
            "horizonte_semanas": weeks,
            "validacion": {
                "fecha_minima": str(validation["fecha_minima"]),
                "fecha_maxima": str(validation["fecha_maxima"]),
                "huecos_detectados": validation["huecos_detectados"],
                "outliers": validation["outliers_detectados"]
            }
        },
        "predictions": predictions_list
    }


def write_predictions_to_sheets(predictions: list) -> None:
    """Escribe las predicciones a una pestaña del Google Sheet.
    
    Crea/actualiza la pestaña 'SIPS_Sugerencias' con las predicciones.
    AppSheet leerá de esta pestaña.
    """
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
    
    # Crear o limpiar pestaña
    sheet_name = "SIPS_Sugerencias"
    try:
        ws = sh.worksheet(sheet_name)
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=10)
    
    # Escribir datos
    if predictions:
        df = pd.DataFrame(predictions)
        # Columnas a exportar
        cols = ["sede", "insumo", "cantidad_requerida", "metodo"]
        if "stock_fisico" in df.columns:
            cols.append("stock_fisico")
        if "faltante_vs_stock" in df.columns:
            cols.append("faltante_vs_stock")
        
        df = df[[c for c in cols if c in df.columns]]
        df["fecha_generacion"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        df["estado"] = "PENDIENTE_REVISION"  # Para que Chef apruebe en AppSheet
        
        # Headers + data
        ws.update([df.columns.values.tolist()] + df.values.tolist())


# ─────────────────────────────────────────────────────────
# CLOUD RUN ENTRY
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
