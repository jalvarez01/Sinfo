"""
Review Interface — HU-02: Interfaz de Ajuste y Validación Humana
================================================================
Permite al Administrador Operativo revisar las cantidades sugeridas por la IA,
aplicar ajustes manuales (override), detectar desviaciones significativas y
exportar la lista validada a CSV o PDF.

El sistema NO ejecuta compras automáticas; su función termina al generar la
lista validada para que el usuario proceda con el proveedor externamente.

Flujo típico:
  1. prepare_review_table(requirements_df)   → tabla con sugerencia IA + columna editable
  2. apply_override(review_df, insumo, qty)  → sobrescritura manual de una cantidad
  3. flag_significant_deviations(review_df)  → resalta filas con desviación > 20 %
  4. finalize_review(review_df)              → congela la lista (marca como finalizada)
  5. export_to_csv / export_to_pdf           → exporta para envío al proveedor
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

_DEVIATION_THRESHOLD = 0.20  # 20 %


# ---------------------------------------------------------------------------
# 1. Preparación de la tabla de revisión
# ---------------------------------------------------------------------------


def prepare_review_table(requirements_df: pd.DataFrame) -> pd.DataFrame:
    """Construye la tabla comparativa para revisión humana.

    Toma el DataFrame de requerimientos generado por el motor de IA y añade
    las columnas necesarias para el proceso de validación manual.

    Args:
        requirements_df: DataFrame con columnas ['insumo', 'unidad_medida',
                         'cantidad_requerida'] generado por
                         ``calculate_ingredient_requirements``.

    Returns:
        DataFrame con columnas:
            - insumo
            - unidad_medida
            - cantidad_sugerida_ia   (copia inmutable de la sugerencia del modelo)
            - cantidad_final         (editable; inicialmente igual a la sugerencia)
            - desviacion_significativa (bool, False por defecto)
            - finalizada             (bool, False por defecto)

    Raises:
        ValueError: Si faltan columnas requeridas en *requirements_df*.
    """
    required_cols = {"insumo", "unidad_medida", "cantidad_requerida"}
    missing = required_cols - set(requirements_df.columns)
    if missing:
        raise ValueError(f"Columnas faltantes en requirements_df: {missing}")

    review = requirements_df[["insumo", "unidad_medida", "cantidad_requerida"]].copy()
    review = review.rename(columns={"cantidad_requerida": "cantidad_sugerida_ia"})
    review["cantidad_final"] = review["cantidad_sugerida_ia"].copy()
    review["desviacion_significativa"] = False
    review["finalizada"] = False
    return review.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2. Sobrescritura manual (override)
# ---------------------------------------------------------------------------


def apply_override(
    review_df: pd.DataFrame,
    insumo: str,
    nueva_cantidad: float,
) -> pd.DataFrame:
    """Aplica una cantidad final personalizada para un insumo concreto.

    Args:
        review_df: DataFrame de revisión (salida de ``prepare_review_table``).
        insumo: Nombre del insumo a modificar.
        nueva_cantidad: Nueva cantidad final (debe ser ≥ 0).

    Returns:
        DataFrame actualizado con la nueva cantidad para el insumo indicado.

    Raises:
        ValueError: Si *nueva_cantidad* es negativa o si el insumo no existe.
        RuntimeError: Si la lista ya fue finalizada.
    """
    if nueva_cantidad < 0:
        raise ValueError(f"La cantidad no puede ser negativa: {nueva_cantidad}")

    if review_df["finalizada"].any():
        raise RuntimeError(
            "La lista ya fue finalizada y no admite modificaciones."
        )

    mask = review_df["insumo"] == insumo
    if not mask.any():
        raise ValueError(f"Insumo no encontrado en la tabla de revisión: '{insumo}'")

    review_df = review_df.copy()
    review_df.loc[mask, "cantidad_final"] = nueva_cantidad
    return flag_significant_deviations(review_df)


# ---------------------------------------------------------------------------
# 3. Detección de desviaciones significativas (> 20 %)
# ---------------------------------------------------------------------------


def flag_significant_deviations(
    review_df: pd.DataFrame,
    threshold: float = _DEVIATION_THRESHOLD,
) -> pd.DataFrame:
    """Actualiza la columna ``desviacion_significativa`` para cada insumo.

    Marca como ``True`` las filas donde la cantidad final difiere más de
    *threshold* (por defecto 20 %) respecto a la sugerencia de la IA.

    Args:
        review_df: DataFrame de revisión.
        threshold: Fracción de desviación (0.20 = 20 %).

    Returns:
        DataFrame con la columna ``desviacion_significativa`` actualizada.
    """
    review_df = review_df.copy()

    sugerida = review_df["cantidad_sugerida_ia"]
    final = review_df["cantidad_final"]

    # Cuando la sugerencia es 0 se compara la cantidad final directamente.
    with_zero = sugerida == 0
    desv = pd.Series(False, index=review_df.index)
    desv[~with_zero] = (
        (final[~with_zero] - sugerida[~with_zero]).abs()
        / sugerida[~with_zero].abs()
        > threshold
    )
    desv[with_zero] = final[with_zero] != 0

    review_df["desviacion_significativa"] = desv
    return review_df


# ---------------------------------------------------------------------------
# 4. Finalización de la lista
# ---------------------------------------------------------------------------


def finalize_review(review_df: pd.DataFrame) -> pd.DataFrame:
    """Congela la lista de insumos marcándola como finalizada.

    Una vez finalizada, la lista no debe recibir más modificaciones.
    Los intentos de ``apply_override`` sobre una lista finalizada lanzarán
    un ``RuntimeError``.

    Args:
        review_df: DataFrame de revisión.

    Returns:
        DataFrame con la columna ``finalizada`` establecida a ``True`` en
        todas las filas.
    """
    review_df = review_df.copy()
    review_df["finalizada"] = True
    return review_df


# ---------------------------------------------------------------------------
# 5. Exportación
# ---------------------------------------------------------------------------


def export_to_csv(review_df: pd.DataFrame, output_path: str) -> str:
    """Exporta la lista validada a un archivo CSV.

    El archivo resultante incluye únicamente las columnas relevantes para el
    proveedor: insumo, unidad_medida, cantidad_sugerida_ia, cantidad_final y
    desviacion_significativa.

    Args:
        review_df: DataFrame de revisión (debe estar finalizado).
        output_path: Ruta de destino para el CSV.

    Returns:
        Ruta absoluta del archivo generado.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    export_cols = [
        "insumo",
        "unidad_medida",
        "cantidad_sugerida_ia",
        "cantidad_final",
        "desviacion_significativa",
    ]
    review_df[export_cols].to_csv(out, index=False)
    return str(out.resolve())


def export_to_pdf(
    review_df: pd.DataFrame,
    output_path: str,
    title: Optional[str] = None,
) -> str:
    """Exporta la lista validada a un archivo PDF.

    Genera un documento PDF con la tabla comparativa (cantidad sugerida por IA
    vs. cantidad final), destacando visualmente las filas con desviación
    significativa.

    Args:
        review_df: DataFrame de revisión.
        output_path: Ruta de destino para el PDF.
        title: Título opcional del documento.

    Returns:
        Ruta absoluta del archivo generado.

    Raises:
        ImportError: Si la biblioteca ``fpdf2`` no está instalada.
    """
    try:
        from fpdf import FPDF  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "La exportación a PDF requiere la biblioteca 'fpdf2'. "
            "Instálala con: pip install fpdf2"
        ) from exc

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)

    doc_title = title or "Lista de Insumos Validada - Inversiones Pulso S.A.S."
    pdf.cell(0, 10, doc_title, ln=True, align="C")
    pdf.set_font("Helvetica", size=9)
    pdf.cell(
        0, 6,
        f"Generado: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        ln=True, align="C",
    )
    pdf.ln(4)

    # ── Encabezado de tabla ────────────────────────────────────────────────
    col_widths = [60, 25, 40, 35, 25]
    headers = ["Insumo", "Unidad", "Cant. Sugerida IA", "Cant. Final", "Desv. >20%"]

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(220, 220, 220)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 8, h, border=1, fill=True)
    pdf.ln()

    # ── Filas de datos ────────────────────────────────────────────────────
    pdf.set_font("Helvetica", size=9)
    for _, row in review_df.iterrows():
        desv = bool(row["desviacion_significativa"])
        if desv:
            pdf.set_fill_color(255, 230, 153)  # amarillo para alertas
        else:
            pdf.set_fill_color(255, 255, 255)

        values = [
            str(row["insumo"]),
            str(row["unidad_medida"]),
            f"{row['cantidad_sugerida_ia']:,.2f}",
            f"{row['cantidad_final']:,.2f}",
            "! Si" if desv else "No",
        ]
        for w, v in zip(col_widths, values):
            pdf.cell(w, 7, v, border=1, fill=True)
        pdf.ln()

    pdf.output(str(out))
    return str(out.resolve())


# ---------------------------------------------------------------------------
# 6. Utilidad: resumen en consola
# ---------------------------------------------------------------------------


def print_review_table(review_df: pd.DataFrame) -> None:
    """Imprime la tabla de revisión en la consola con marcas de alerta.

    Args:
        review_df: DataFrame de revisión.
    """
    print("\n" + "=" * 75)
    print("  TABLA COMPARATIVA DE INSUMOS — REVISIÓN HUMANA")
    print("=" * 75)
    header = f"{'Insumo':<30} {'Unidad':<10} {'Cant. IA':>12} {'Cant. Final':>12} {'Alerta':>7}"
    print(header)
    print("-" * 75)
    for _, row in review_df.iterrows():
        alerta = "⚠ >20%" if row["desviacion_significativa"] else ""
        print(
            f"{str(row['insumo']):<30} "
            f"{str(row['unidad_medida']):<10} "
            f"{row['cantidad_sugerida_ia']:>12,.2f} "
            f"{row['cantidad_final']:>12,.2f} "
            f"{alerta:>7}"
        )
    print("=" * 75)
