"""
Main Entry Point — HU-01 / HU-02: Generación de Predicciones y Validación Humana
==================================================================================
Ejecuta el pipeline completo:
  1. Limpieza de datos del histórico de ventas.
  2. Generación de predicciones de ventas por producto.
  3. Cálculo de requerimientos de insumos basado en la receta estándar.
  4. Exportación de resultados a CSV.
  5. (Opcional) Interfaz interactiva de revisión y ajuste humano (--review).

Uso:
    python main.py [--sales <ruta_csv>] [--recipe <ruta_csv>] [--weeks <n>] [--output <ruta_csv>]
    python main.py --review [--suggestions <ruta_csv>] [--export-pdf]

Argumentos opcionales:
    --sales       Ruta al CSV del histórico de ventas
                  (default: data/historico_ventas_sample.csv)
    --recipe      Ruta al CSV de la receta estándar
                  (default: data/receta_estandar.csv)
    --weeks       Número de semanas a proyectar (default: 4)
    --output      Ruta donde se guardará el CSV de sugerencias
                  (default: data/sugerencia_insumos.csv)
    --review      Activa la interfaz de revisión humana (HU-02)
    --suggestions Ruta al CSV de sugerencias a revisar; si se omite se ejecuta
                  primero el pipeline de predicción
    --export-pdf  Exporta también la lista validada en formato PDF
"""

import argparse
import os
import sys

import pandas as pd

from src.data_cleaning import clean_historical_data
from src.ingredient_calculator import (
    add_inventory_context,
    calculate_ingredient_requirements,
    load_inventory,
    load_standard_recipe,
)
from src.prediction_engine import generate_predictions

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_SALES_PATH = os.path.join(BASE_DIR, "data", "historico_ventas_sample.csv")
DEFAULT_RECIPE_PATH = os.path.join(BASE_DIR, "data", "receta_estandar.csv")
DEFAULT_INVENTORY_PATH = os.path.join(BASE_DIR, "data", "inventarioActual.csv")
DEFAULT_OUTPUT_PATH = os.path.join(BASE_DIR, "data", "sugerencia_insumos.csv")
DEFAULT_HORIZON_WEEKS = 4


def run_pipeline(
    sales_path: str = DEFAULT_SALES_PATH,
    recipe_path: str = DEFAULT_RECIPE_PATH,
    inventory_path: str = DEFAULT_INVENTORY_PATH,
    output_path: str = DEFAULT_OUTPUT_PATH,
    horizon_weeks: int = DEFAULT_HORIZON_WEEKS,
) -> None:
    """Ejecuta el pipeline completo de predicción e imprime un resumen en consola.

    Args:
        sales_path: Ruta al CSV con el histórico de ventas.
        recipe_path: Ruta al CSV con la receta estándar.
        inventory_path: Ruta al CSV con el inventario físico actual.
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
    if os.path.exists(inventory_path):
        inventory = load_inventory(inventory_path)
        requirements = add_inventory_context(requirements, inventory)
        print(f"      Inventario cargado: {len(inventory)} insumos")
    else:
        print(f"      [AVISO] No se encontró inventario físico en: {inventory_path}")
    print(f"      Insumos identificados: {len(requirements)}")

    # ── Exportar resultados ────────────────────────────────────
    requirements.to_csv(output_path, index=False)
    print(f"\n✔  Sugerencia de insumos exportada a: {output_path}")
    print("\n      Resumen de insumos críticos:")
    print(requirements.to_string(index=False))
    print("\n" + "=" * 60)


def run_review(
    suggestions_path: str = DEFAULT_OUTPUT_PATH,
    export_pdf: bool = False,
) -> None:
    """Interfaz interactiva de revisión y ajuste humano (HU-02).

    Carga las sugerencias generadas por la IA, permite al administrador
    ajustar las cantidades y exporta la lista validada a CSV (y opcionalmente
    a PDF). El sistema no ejecuta compras; sólo genera la lista validada.

    Args:
        suggestions_path: Ruta al CSV de sugerencias generado por el pipeline.
        export_pdf: Si es True, exporta también un archivo PDF.
    """
    from src.review_interface import (
        apply_override,
        export_to_csv,
        export_to_pdf,
        finalize_review,
        prepare_review_table,
        print_review_table,
    )

    print("=" * 60)
    print("  HU-02: Interfaz de Ajuste y Validación Humana")
    print("=" * 60)

    # ── Cargar sugerencias ─────────────────────────────────────
    if not os.path.exists(suggestions_path):
        print(f"\n[ERROR] No se encontró el archivo de sugerencias: {suggestions_path}")
        print("        Ejecute primero el pipeline sin --review para generar las sugerencias.")
        sys.exit(1)

    requirements = pd.read_csv(suggestions_path)
    review_df = prepare_review_table(requirements)

    print_review_table(review_df)

    # ── Bucle interactivo de ajuste ────────────────────────────
    print("\nIntroduzca los ajustes manuales. Escriba 'listo' para finalizar la revisión.")
    print("Formato: <nombre_insumo> <nueva_cantidad>")
    print("Ejemplo: Pan 150")

    while True:
        try:
            raw = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nRevisión cancelada.")
            return

        if raw.lower() in ("listo", "ok", "done", ""):
            break

        parts = raw.rsplit(maxsplit=1)
        if len(parts) != 2:
            print("  Formato incorrecto. Use: <nombre_insumo> <nueva_cantidad>")
            continue

        insumo_input, cantidad_input = parts
        try:
            nueva_cantidad = float(cantidad_input.replace(",", "."))
        except ValueError:
            print(f"  Cantidad inválida: '{cantidad_input}'")
            continue

        try:
            review_df = apply_override(review_df, insumo_input, nueva_cantidad)
            flag = review_df.loc[review_df["insumo"] == insumo_input, "desviacion_significativa"].values[0]
            msg = f"  ✔ {insumo_input}: {nueva_cantidad:,.2f}"
            if flag:
                msg += "  ⚠  Desviación > 20 % respecto a la sugerencia de la IA"
            print(msg)
        except (ValueError, RuntimeError) as exc:
            print(f"  [ERROR] {exc}")

    # ── Tabla final antes de exportar ─────────────────────────
    print("\nResumen final antes de exportar:")
    print_review_table(review_df)

    # ── Finalizar y exportar ───────────────────────────────────
    review_df = finalize_review(review_df)

    base_dir = os.path.dirname(suggestions_path)
    csv_out = os.path.join(base_dir, "lista_validada.csv")
    csv_path = export_to_csv(review_df, csv_out)
    print(f"\n✔  Lista validada exportada a CSV: {csv_path}")

    if export_pdf:
        pdf_out = os.path.join(base_dir, "lista_validada.pdf")
        try:
            pdf_path = export_to_pdf(review_df, pdf_out)
            print(f"✔  Lista validada exportada a PDF: {pdf_path}")
        except ImportError as exc:
            print(f"[AVISO] No se pudo exportar a PDF: {exc}")

    print("\n✔  Revisión finalizada. La lista está lista para enviar al proveedor.")
    print("   (El sistema NO ejecuta compras automáticamente.)")
    print("\n" + "=" * 60)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Pipeline de predicción de insumos — Inversiones Pulso S.A.S."
    )
    parser.add_argument("--sales", default=DEFAULT_SALES_PATH, help="Ruta al CSV del histórico de ventas")
    parser.add_argument("--recipe", default=DEFAULT_RECIPE_PATH, help="Ruta al CSV de la receta estándar")
    parser.add_argument("--inventory", default=DEFAULT_INVENTORY_PATH, help="Ruta al CSV del inventario físico actual")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH, help="Ruta de salida para el CSV de sugerencias")
    parser.add_argument("--weeks", type=int, default=DEFAULT_HORIZON_WEEKS, help="Semanas a proyectar")
    parser.add_argument(
        "--review", action="store_true",
        help="Activa la interfaz interactiva de revisión y ajuste humano (HU-02)",
    )
    parser.add_argument(
        "--suggestions", default=None,
        help="Ruta al CSV de sugerencias para la revisión (requiere --review). "
             "Si se omite, se ejecuta el pipeline de predicción primero.",
    )
    parser.add_argument(
        "--export-pdf", action="store_true",
        help="Exporta la lista validada también en formato PDF (requiere --review)",
    )
    args = parser.parse_args(argv)

    if args.review:
        suggestions_path = args.suggestions or args.output
        if not os.path.exists(suggestions_path):
            # Generar sugerencias automáticamente antes de la revisión
            run_pipeline(
                sales_path=args.sales,
                recipe_path=args.recipe,
                inventory_path=args.inventory,
                output_path=args.output,
                horizon_weeks=args.weeks,
            )
        run_review(suggestions_path=suggestions_path, export_pdf=args.export_pdf)
    else:
        run_pipeline(
            sales_path=args.sales,
            recipe_path=args.recipe,
            inventory_path=args.inventory,
            output_path=args.output,
            horizon_weeks=args.weeks,
        )


if __name__ == "__main__":
    main()
