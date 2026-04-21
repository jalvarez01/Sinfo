"""
Main Entry Point — HU-01: Generación de Predicciones Basadas en Históricos
===========================================================================
Ejecuta el pipeline completo:
  1. Limpieza de datos del histórico de ventas.
  2. Generación de predicciones de ventas por producto.
  3. Cálculo de requerimientos de insumos basado en la receta estándar.
  4. Exportación de resultados a CSV.

Uso:
    python main.py [--sales <ruta_csv>] [--recipe <ruta_csv>] [--weeks <n>] [--output <ruta_csv>]

Argumentos opcionales:
    --sales   Ruta al CSV del histórico de ventas
              (default: data/historico_ventas_sample.csv)
    --recipe  Ruta al CSV de la receta estándar
              (default: data/receta_estandar.csv)
    --weeks   Número de semanas a proyectar (default: 4)
    --output  Ruta donde se guardará el CSV de resultados
              (default: data/sugerencia_insumos.csv)
"""

import argparse
import os
import sys

from src.data_cleaning import clean_historical_data
from src.ingredient_calculator import calculate_ingredient_requirements, load_standard_recipe
from src.prediction_engine import generate_predictions

DEFAULT_SALES_PATH = os.path.join("data", "historico_ventas_sample.csv")
DEFAULT_RECIPE_PATH = os.path.join("data", "receta_estandar.csv")
DEFAULT_OUTPUT_PATH = os.path.join("data", "sugerencia_insumos.csv")
DEFAULT_HORIZON_WEEKS = 4


def run_pipeline(
    sales_path: str = DEFAULT_SALES_PATH,
    recipe_path: str = DEFAULT_RECIPE_PATH,
    output_path: str = DEFAULT_OUTPUT_PATH,
    horizon_weeks: int = DEFAULT_HORIZON_WEEKS,
) -> None:
    """Ejecuta el pipeline completo de predicción e imprime un resumen en consola.

    Args:
        sales_path: Ruta al CSV con el histórico de ventas.
        recipe_path: Ruta al CSV con la receta estándar.
        output_path: Ruta donde se guardará el CSV con la sugerencia de insumos.
        horizon_weeks: Número de semanas a proyectar.
    """
    print("=" * 60)
    print("  HU-01: Generación de Predicciones Basadas en Históricos")
    print("=" * 60)

    # ── Paso 1: Limpieza de datos ──────────────────────────────
    print("\n[1/3] Limpiando histórico de ventas…")
    df_clean, report = clean_historical_data(sales_path)
    print(f"      Registros iniciales : {report['registros_iniciales']:,}")
    print(f"      Duplicados eliminados: {report['duplicados_eliminados']:,}")
    print(f"      Inválidos eliminados : {report['invalidos_eliminados']:,}")
    print(f"      Registros finales    : {report['registros_finales']:,}")

    # ── Paso 2: Predicción de ventas ───────────────────────────
    print(f"\n[2/3] Generando predicciones para {horizon_weeks} semana(s)…")
    predictions = generate_predictions(df_clean, horizon_weeks=horizon_weeks)
    print(f"      Productos proyectados: {len(predictions)}")
    print("\n      Top 5 productos por volumen proyectado:")
    print(predictions.head(5).to_string(index=False))

    # ── Paso 3: Cálculo de insumos ─────────────────────────────
    print("\n[3/3] Calculando requerimientos de insumos…")
    recipe = load_standard_recipe(recipe_path)
    requirements = calculate_ingredient_requirements(predictions, recipe)
    print(f"      Insumos identificados: {len(requirements)}")

    # ── Exportar resultados ────────────────────────────────────
    requirements.to_csv(output_path, index=False)
    print(f"\n✔  Sugerencia de insumos exportada a: {output_path}")
    print("\n      Resumen de insumos críticos:")
    print(requirements.to_string(index=False))
    print("\n" + "=" * 60)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Pipeline de predicción de insumos — Inversiones Pulso S.A.S."
    )
    parser.add_argument("--sales", default=DEFAULT_SALES_PATH, help="Ruta al CSV del histórico de ventas")
    parser.add_argument("--recipe", default=DEFAULT_RECIPE_PATH, help="Ruta al CSV de la receta estándar")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH, help="Ruta de salida para el CSV de sugerencias")
    parser.add_argument("--weeks", type=int, default=DEFAULT_HORIZON_WEEKS, help="Semanas a proyectar")
    args = parser.parse_args(argv)

    run_pipeline(
        sales_path=args.sales,
        recipe_path=args.recipe,
        output_path=args.output,
        horizon_weeks=args.weeks,
    )


if __name__ == "__main__":
    main()
