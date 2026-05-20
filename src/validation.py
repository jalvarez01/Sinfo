"""
Validación de Histórico de Datos
==================================
Funciones para verificar calidad y completitud del histórico antes de predicciones.
"""

import pandas as pd
from datetime import datetime


def validate_historical_data(df: pd.DataFrame) -> dict:
    """Valida que el histórico sea confiable para predicciones.
    
    Args:
        df: DataFrame con columnas: fecha, producto, cantidad, sucursal (opcional)
        
    Returns:
        dict con métricas de validación
    """
    
    report = {
        "fecha_minima": df["fecha"].min(),
        "fecha_maxima": df["fecha"].max(),
        "dias_cobertura": (df["fecha"].max() - df["fecha"].min()).days,
        "productos_unicos": df["producto"].nunique(),
        "registros_totales": len(df),
        "registros_por_dia_promedio": len(df) / max((df["fecha"].max() - df["fecha"].min()).days, 1),
    }
    
    # Detectar huecos en fechas
    date_range = pd.date_range(start=df["fecha"].min(), end=df["fecha"].max(), freq="D")
    fechas_presentes = df["fecha"].dt.date.unique()
    fechas_faltantes = [d for d in date_range.date if d not in fechas_presentes]
    report["huecos_detectados"] = len(fechas_faltantes)
    report["huecos_lista"] = fechas_faltantes[:10]  # Primeros 10
    
    # Productos con muy pocos datos
    productos_count = df.groupby("producto").size()
    productos_insuficientes = productos_count[productos_count < 10]
    report["productos_con_pocos_datos"] = len(productos_insuficientes)
    report["productos_insuficientes_lista"] = productos_insuficientes.index.tolist()[:10]
    
    # Distribución por sucursal si existe
    if "sucursal" in df.columns:
        report["sedes"] = df["sucursal"].unique().tolist()
        report["registros_por_sede"] = df.groupby("sucursal").size().to_dict()
    
    # Detectar outliers en cantidad
    Q1 = df["cantidad"].quantile(0.25)
    Q3 = df["cantidad"].quantile(0.75)
    IQR = Q3 - Q1
    outliers = df[(df["cantidad"] < Q1 - 1.5*IQR) | (df["cantidad"] > Q3 + 1.5*IQR)]
    report["outliers_detectados"] = len(outliers)
    
    return report


def print_validation_report(validation: dict) -> None:
    """Imprime un reporte amigable de validación."""
    
    print("\n[VALIDACIÓN DE HISTÓRICO]")
    print(f"  Rango de datos: {validation['fecha_minima'].date()} a {validation['fecha_maxima'].date()}")
    print(f"  Días de cobertura: {validation['dias_cobertura']}")
    print(f"  Registros totales: {validation['registros_totales']:,}")
    print(f"  Promedio registros/día: {validation['registros_por_dia_promedio']:.1f}")
    print(f"  Productos únicos: {validation['productos_unicos']}")
    
    if validation["huecos_detectados"] > 0:
        print(f"  ⚠️  HUECOS DETECTADOS: {validation['huecos_detectados']} días sin datos")
        if validation["huecos_lista"]:
            print(f"      Primeros: {validation['huecos_lista'][:3]}")
    else:
        print(f"  ✓ Sin huecos en fechas")
    
    if validation["productos_con_pocos_datos"] > 0:
        print(f"  ⚠️  Productos con <10 registros: {validation['productos_con_pocos_datos']}")
        print(f"      Ejemplos: {validation['productos_insuficientes_lista'][:3]}")
    else:
        print(f"  ✓ Suficientes datos por producto")
    
    if validation["outliers_detectados"] > 0:
        print(f"  ⚠️  Outliers detectados: {validation['outliers_detectados']}")
    else:
        print(f"  ✓ Sin outliers significativos")
    
    if "registros_por_sede" in validation:
        print(f"  Sedes: {len(validation['sedes'])}")
        for sede, count in validation["registros_por_sede"].items():
            print(f"      {sede}: {count:,} registros")
