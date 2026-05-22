"""
Sales-to-Consumption Converter
================================
Convierte VENTAS DE PLATOS en CONSUMO REAL DE INSUMOS usando recetas.

Ejemplo:
  Ventas: 100 Tacos de Birria
  Receta: Taco de Birria → 0.15 kg ESPALDILLA, 0.05 kg CEBOLLA
  Consumo calculado:
    - ESPALDILLA: 15 kg
    - CEBOLLA: 5 kg
"""

import pandas as pd
from typing import Optional
from difflib import get_close_matches


def normalize_plato_name(name: str) -> str:
    """Normaliza nombre de plato para matching."""
    return str(name).strip().lower()


def fuzzy_match_plato(sales_name: str, recipe_names: list, cutoff: float = 0.7) -> Optional[str]:
    """Busca el nombre de plato más parecido en recetas usando fuzzy matching.
    
    Args:
        sales_name: Nombre como aparece en ventas
        recipe_names: Lista de nombres de platos en recetas
        cutoff: Similitud mínima (0-1)
    
    Returns:
        Nombre del plato en recetas si hay match, None si no
    """
    normalized = normalize_plato_name(sales_name)
    normalized_recipes = [normalize_plato_name(r) for r in recipe_names]
    
    matches = get_close_matches(normalized, normalized_recipes, n=1, cutoff=cutoff)
    
    if matches:
        idx = normalized_recipes.index(matches[0])
        return recipe_names[idx]
    
    return None


def convert_sales_to_consumption(
    sales_df: pd.DataFrame,
    recipes_df: pd.DataFrame,
    fuzzy_matching: bool = True,
) -> pd.DataFrame:
    """Convierte ventas de platos en consumo real de insumos.
    
    Args:
        sales_df: DataFrame con: fecha, producto (plato), cantidad, (sede opcional)
        recipes_df: DataFrame con: Producto, Insumo, Cantidad_Por_Unidad, Unidad_Medida
        fuzzy_matching: Si los nombres no coinciden exacto, usar matching aproximado
    
    Returns:
        DataFrame con consumo desglosado:
          fecha | sede | insumo | cantidad_consumida | unidad_medida
    """
    
    # Normalizar columnas de receta
    recipes_df = recipes_df.copy()
    recipes_df.columns = recipes_df.columns.str.strip()
    
    # Detectar columnas en recetas (también flexible)
    receta_cols = {
        "plato": _find_col(recipes_df, ["producto", "plato", "nombre"]),
        "insumo": _find_col(recipes_df, ["insumo", "ingrediente"]),
        "cantidad": _find_col(recipes_df, ["cantidad_por_unidad", "cantidad", "qty"]),
        "unidad": _find_col(recipes_df, ["unidad_medida", "unidad", "unit"]),
    }
    
    if not all([receta_cols["plato"], receta_cols["insumo"], receta_cols["cantidad"]]):
        raise ValueError(f"Recetas mal estructuradas. Columnas: {list(recipes_df.columns)}")
    
    # Construir mapping de platos
    platos_en_recetas = recipes_df[receta_cols["plato"]].unique().tolist()
    platos_en_ventas = sales_df["producto"].unique().tolist()
    
    # Matching
    plato_mapping = {}
    sin_match = []
    
    for plato_venta in platos_en_ventas:
        # Match exacto
        if plato_venta in platos_en_recetas:
            plato_mapping[plato_venta] = plato_venta
        else:
            # Fuzzy match
            if fuzzy_matching:
                match = fuzzy_match_plato(plato_venta, platos_en_recetas, cutoff=0.7)
                if match:
                    plato_mapping[plato_venta] = match
                else:
                    sin_match.append(plato_venta)
            else:
                sin_match.append(plato_venta)
    
    print(f"\n[CONVERSIÓN VENTAS → INSUMOS]")
    print(f"  Platos en ventas: {len(platos_en_ventas)}")
    print(f"  Platos en recetas: {len(platos_en_recetas)}")
    print(f"  Match exitoso: {len(plato_mapping)}")
    if sin_match:
        print(f"  ⚠️  Sin receta ({len(sin_match)}): {sin_match[:5]}{'...' if len(sin_match) > 5 else ''}")
    
    # Cruce
    consumption_records = []
    
    for _, sale in sales_df.iterrows():
        plato_venta = sale["producto"]
        
        if plato_venta not in plato_mapping:
            continue
        
        plato_receta = plato_mapping[plato_venta]
        receta = recipes_df[recipes_df[receta_cols["plato"]] == plato_receta]
        
        for _, ingrediente in receta.iterrows():
            cantidad_consumida = (
                sale["cantidad"] * ingrediente[receta_cols["cantidad"]]
            )
            
            record = {
                "fecha": sale["fecha"],
                "producto": ingrediente[receta_cols["insumo"]],  # Compat con predictor
                "cantidad": cantidad_consumida,
            }
            
            if "sede" in sales_df.columns:
                record["sucursal"] = sale["sede"]
            
            if receta_cols["unidad"]:
                record["unidad_medida"] = ingrediente[receta_cols["unidad"]]
            
            consumption_records.append(record)
    
    if not consumption_records:
        return pd.DataFrame()
    
    consumption_df = pd.DataFrame(consumption_records)
    print(f"  Registros de consumo generados: {len(consumption_df):,}")
    
    return consumption_df


def _find_col(df: pd.DataFrame, patterns: list) -> Optional[str]:
    """Busca columna por patrones (case-insensitive)."""
    import re
    for col in df.columns:
        col_clean = str(col).lower().strip()
        for pattern in patterns:
            if re.search(pattern, col_clean, re.IGNORECASE):
                return col
    return None
