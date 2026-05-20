"""
Main Entry Point — HU-01 / HU-02 (Mejorado)
============================================
Pipeline con:
  1. Validación de histórico
  2. Predicción por sede (Manila, Poblado, Laureles)
  3. Seasonality con Prophet
  4. Cálculo de requerimientos de insumos
  5. Exportación a CSV

Uso:
    python main.py --source sheets [--sedes S-01,S-02,S-03] [--weeks 4]
    python main.py --source csv --sales data/historico_ventas_sample.csv [--weeks 4]
    python main.py --source sheets --review
"""

import argparse
import os
import sys

import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.data_cleaning import clean_dataframe, clean_historical_data
from src.validation import validate_historical_data, print_validation_report
from src.seasonal_predictor import generate_predictions_seasonal
from src.ingredient_calculator import (
    add_inventory_context,
    load_inventory,
    normalize_inventory_dataframe,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_SALES_PATH = os.path.join(BASE_DIR, "data", "historico_ventas_sample.csv")
DEFAULT_INVENTORY_PATH = os.path.join(BASE_DIR, "data", "inventarioActual.csv")
DEFAULT_OUTPUT_DIR = os.path.join(BASE_DIR, "data")
DEFAULT_HORIZON_WEEKS = 4
DEFAULT_SEDES = ["S-01", "S-02", "S-03"]


def run_pipeline(
    sales_path: str = DEFAULT_SALES_PATH,
    inventory_path: str = DEFAULT_INVENTORY_PATH,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    horizon_weeks: int = DEFAULT_HORIZON_WEEKS,
    sedes: list = None,
    source: str = "csv",
) -> None:
    """Pipeline completo con validación, predicción por sede y seasonality.
    
    Args:
        sales_path: Ruta al CSV del histórico (solo si source=csv)
        inventory_path: Ruta al CSV del inventario
        output_dir: Directorio para guardar CSVs
        horizon_weeks: Semanas a proyectar
        sedes: Lista de sedes a procesar (default: todas)
        source: 'csv' o 'sheets'
    """
    
    if sedes is None:
        sedes = DEFAULT_SEDES
    
    print("=" * 70)
    print("  HU-01: Generación de Predicciones (con Sedes y Seasonality)")
    print(f"  Fuente: {source.upper()} | Sedes: {len(sedes)} | Horizonte: {horizon_weeks}w")
    print("=" * 70)
    
    # ── PASO 1: Limpieza de datos ──────────────────────────────
    print("\n[1/4] Limpiando histórico de ventas…")
    
    if source == "sheets":
        from src.sheets_loader import load_historical_from_sheets, load_inventory_from_sheets
        df_raw = load_historical_from_sheets()
        df_clean, report = clean_dataframe(df_raw)
    else:
        df_clean, report = clean_historical_data(sales_path)
    
    print(f"      Registros iniciales : {report['registros_iniciales']:,}")
    print(f"      Duplicados eliminados: {report['duplicados_eliminados']:,}")
    print(f"      Inválidos eliminados : {report['invalidos_eliminados']:,}")
    print(f"      Registros finales    : {report['registros_finales']:,}")
    
    # ── PASO 2: Validación de histórico ────────────────────────
    print("\n[2/4] Validando histórico…")
    validation = validate_historical_data(df_clean)
    print_validation_report(validation)
    
    # ADVERTENCIA: Si hay huecos significativos
    if validation["huecos_detectados"] > (validation["dias_cobertura"] * 0.2):
        print("\n  ⚠️  ADVERTENCIA: Más del 20% de huecos en fechas.")
        print("     Las predicciones pueden ser menos precisas.")
    
    # ── PASO 3: Predicción por Sede con Seasonality ────────────
    print(f"\n[3/4] Generando predicciones (Prophet + Seasonality)…")
    
    # Verificar si hay columna de sede
    has_sede = "sucursal" in df_clean.columns
    sedes_a_procesar = sedes if has_sede else [None]
    
    all_predictions = []
    
    for sede in sedes_a_procesar:
        sede_label = f" [{sede}]" if sede else ""
        
        try:
            predictions = generate_predictions_seasonal(
                df_clean,
                horizon_weeks=horizon_weeks,
                sede=sede,
                use_prophet=True
            )
            
            if len(predictions) > 0:
                predictions["sede"] = sede or "CONSOLIDADO"
                all_predictions.append(predictions)
                
                print(f"      {sede_label}: {len(predictions)} productos predichos")
                print(f"        Top 3: {predictions.head(3)['producto'].tolist()}")
        
        except Exception as e:
            print(f"      {sede_label}: Error en predicción - {str(e)[:50]}")
    
    if not all_predictions:
        print("  [ERROR] No se generaron predicciones.")
        sys.exit(1)
    
    predictions_combined = pd.concat(all_predictions, ignore_index=True)
    
    # ── PASO 4: Cálculo de requerimientos y exportación ─────────
    print(f"\n[4/4] Calculando requerimientos e inventario…")
    
    # Cargar inventario
    try:
        if source == "sheets":
            inventory_raw = load_inventory_from_sheets()
            inventory = normalize_inventory_dataframe(inventory_raw)
        elif os.path.exists(inventory_path):
            inventory = load_inventory(inventory_path)
        else:
            inventory = pd.DataFrame()
    except Exception as e:
        print(f"      [AVISO] No se cargó inventario: {str(e)[:50]}")
        inventory = pd.DataFrame()
    
    # Preparar requerimientos finales
    requirements = predictions_combined.copy()
    requirements = requirements.rename(columns={
        "producto": "insumo",
        "ventas_proyectadas": "cantidad_requerida"
    })
    
    if "metodo" not in requirements.columns:
        requirements["metodo"] = "Prophet"
    
    requirements["unidad_medida"] = "UNIDAD"
    
    # Agregar contexto de inventario
    if len(inventory) > 0:
        requirements = add_inventory_context(requirements, inventory)
        print(f"      Inventario cargado: {len(inventory)} insumos")
    else:
        print(f"      [AVISO] Sin inventario para comparación")
    
    # Exportar por sede
    if has_sede:
        for sede in sedes_a_procesar:
            if sede:
                requirements_sede = requirements[requirements["sede"] == sede].copy()
                output_path = os.path.join(
                    output_dir,
                    f"sugerencia_insumos_{sede}.csv"
                )
            else:
                requirements_sede = requirements[requirements["sede"] == "CONSOLIDADO"].copy()
                output_path = os.path.join(
                    output_dir,
                    f"sugerencia_insumos_CONSOLIDADO.csv"
                )
            
            # Mantener solo columnas relevantes
            cols = ["insumo", "unidad_medida", "cantidad_requerida", "metodo", "sede"]
            if "stock_fisico" in requirements_sede.columns:
                cols.append("stock_fisico")
            if "faltante_vs_stock" in requirements_sede.columns:
                cols.append("faltante_vs_stock")
            
            requirements_sede = requirements_sede[[c for c in cols if c in requirements_sede.columns]]
            requirements_sede = requirements_sede.sort_values("cantidad_requerida", ascending=False)
            
            requirements_sede.to_csv(output_path, index=False)
            print(f"      ✓ {sede or 'CONSOLIDADO'}: {len(requirements_sede)} insumos → {output_path}")
    
    else:
        # Exportación única (sin sedes)
        output_path = os.path.join(output_dir, "sugerencia_insumos.csv")
        
        cols = ["insumo", "unidad_medida", "cantidad_requerida", "metodo"]
        if "stock_fisico" in requirements.columns:
            cols.append("stock_fisico")
        if "faltante_vs_stock" in requirements.columns:
            cols.append("faltante_vs_stock")
        
        requirements = requirements[[c for c in cols if c in requirements.columns]]
        requirements = requirements.sort_values("cantidad_requerida", ascending=False)
        
        requirements.to_csv(output_path, index=False)
        print(f"      ✓ {len(requirements)} insumos → {output_path}")
    
    print("\n" + "=" * 70)
    print("  ✓ Pipeline completado exitosamente")
    print("=" * 70)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Pipeline mejorado: Sedes + Seasonality + Validación"
    )
    parser.add_argument(
        "--source", choices=["csv", "sheets"], default="csv",
        help="'csv' (archivos) o 'sheets' (Google Sheets API)"
    )
    parser.add_argument(
        "--sales", default=DEFAULT_SALES_PATH,
        help="Ruta al CSV de histórico (si source=csv)"
    )
    parser.add_argument(
        "--inventory", default=DEFAULT_INVENTORY_PATH,
        help="Ruta al CSV de inventario"
    )
    parser.add_argument(
        "--output-dir", default=DEFAULT_OUTPUT_DIR,
        help="Directorio para guardar CSVs de salida"
    )
    parser.add_argument(
        "--weeks", type=int, default=DEFAULT_HORIZON_WEEKS,
        help="Semanas a proyectar (default: 4)"
    )
    parser.add_argument(
        "--sedes", default="S-01,S-02,S-03",
        help="Sedes a procesar, separadas por coma (default: S-01,S-02,S-03)"
    )
    parser.add_argument(
        "--review", action="store_true",
        help="Activar interfaz de revisión humana (HU-02)"
    )
    
    args = parser.parse_args(argv)
    
    # Parsear sedes
    sedes_list = [s.strip() for s in args.sedes.split(",")]
    
    # Ejecutar pipeline
    run_pipeline(
        sales_path=args.sales,
        inventory_path=args.inventory,
        output_dir=args.output_dir,
        horizon_weeks=args.weeks,
        sedes=sedes_list,
        source=args.source,
    )
    
    # Opcional: ejecutar revisión
    if args.review:
        print("\n[NOTA] Interfaz de revisión: pendiente de implementar en versión siguiente")


if __name__ == "__main__":
    main()
