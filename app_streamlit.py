import os
from typing import Dict

import pandas as pd
import streamlit as st


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_PATH = os.path.join(BASE_DIR, "data", "sugerencia_insumos.csv")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: Dict[str, str] = {
        "Insumo": "insumo",
        "Stock_Fisico": "stock_fisico",
        "Cantidad_Sugerida_IA": "cantidad_requerida",
        "Cantidad_Ajustada_Humano": "pedido_ajustado",
        "Estado": "estado",
    }
    existing = {src: dst for src, dst in rename_map.items() if src in df.columns}
    return df.rename(columns=existing)


def classify_category(insumo: str) -> str:
    text = str(insumo).lower()
    if any(k in text for k in ["carne", "birria", "pastor", "pollo", "res", "cerdo"]):
        return "Proteinas"
    if any(k in text for k in ["tortilla", "arepa", "totopo", "consome"]):
        return "Bases"
    if any(k in text for k in ["queso", "guacamole", "cebolla", "cilantro", "piña", "pina"]):
        return "Complementos"
    if any(k in text for k in ["cerveza", "gaseosa", "bebida"]):
        return "Bebidas"
    return "Otros"


def load_projection_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df = normalize_columns(df)

    required = {"insumo", "cantidad_requerida"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Columnas requeridas faltantes: {missing}")

    if "stock_fisico" not in df.columns:
        df["stock_fisico"] = 0.0

    df["insumo"] = df["insumo"].astype(str).str.strip()
    df["cantidad_requerida"] = pd.to_numeric(df["cantidad_requerida"], errors="coerce").fillna(0.0)
    df["stock_fisico"] = pd.to_numeric(df["stock_fisico"], errors="coerce").fillna(0.0)

    if "pedido_ajustado" not in df.columns:
        df["pedido_ajustado"] = df["cantidad_requerida"]
    else:
        df["pedido_ajustado"] = pd.to_numeric(df["pedido_ajustado"], errors="coerce").fillna(df["cantidad_requerida"])

    df["categoria"] = df["insumo"].apply(classify_category)
    return df


def compute_risk(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["pedido_ajustado"] = pd.to_numeric(out["pedido_ajustado"], errors="coerce").fillna(0.0)
    out["stock_fisico"] = pd.to_numeric(out["stock_fisico"], errors="coerce").fillna(0.0)
    out["faltante"] = (out["pedido_ajustado"] - out["stock_fisico"]).round(2)
    out["riesgo_quiebre"] = out["faltante"] > 0
    out["estado_riesgo"] = out["riesgo_quiebre"].map({True: "Riesgo de Quiebre de Stock", False: "Stock Suficiente"})
    return out


def inject_style() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Nunito:wght@400;600;700&display=swap');

        .stApp {
            background:
              radial-gradient(circle at 15% 15%, rgba(255, 115, 0, 0.22), transparent 35%),
              radial-gradient(circle at 85% 10%, rgba(239, 68, 68, 0.18), transparent 30%),
              linear-gradient(180deg, #150b09 0%, #23110d 55%, #110907 100%);
            color: #fff5e6;
            font-family: 'Nunito', sans-serif;
        }

        h1, h2, h3 {
            font-family: 'Bebas Neue', sans-serif;
            letter-spacing: 0.8px;
        }

        .hero-box {
            padding: 1rem 1.2rem;
            border-radius: 18px;
            border: 1px solid rgba(255, 160, 122, 0.28);
            background: linear-gradient(130deg, rgba(28, 13, 9, 0.85), rgba(56, 21, 14, 0.78));
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35);
            animation: fadeUp 700ms ease-out;
        }

        @keyframes fadeUp {
            0% { opacity: 0; transform: translateY(8px); }
            100% { opacity: 1; transform: translateY(0); }
        }

        .pill {
            display: inline-block;
            padding: 0.2rem 0.65rem;
            border-radius: 999px;
            font-weight: 700;
            margin-right: 0.5rem;
            font-size: 0.85rem;
        }

        .pill-risk { background: rgba(220, 38, 38, 0.18); color: #fecaca; border: 1px solid rgba(239, 68, 68, 0.4); }
        .pill-safe { background: rgba(22, 163, 74, 0.2); color: #bbf7d0; border: 1px solid rgba(74, 222, 128, 0.35); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Proyeccion de Pedido Sugerido", page_icon="🍽️", layout="wide")
    inject_style()

    st.markdown("<div class='hero-box'><h1>Proyeccion Interactiva de Pedido Sugerido</h1><p>Visualiza y ajusta el pedido recomendado segun el stock actual.</p></div>", unsafe_allow_html=True)

    with st.sidebar:
        st.header("Configuracion")
        uploaded = st.file_uploader("Cargar CSV de sugerencias", type=["csv"])
        source_path = uploaded if uploaded is not None else DEFAULT_DATA_PATH

        if st.button("Resetear ajustes"):
            if "pedido_df" in st.session_state:
                del st.session_state["pedido_df"]

    try:
        base_df = load_projection_data(source_path)
    except Exception as exc:
        st.error(f"No fue posible cargar los datos: {exc}")
        return

    if "pedido_df" not in st.session_state:
        st.session_state["pedido_df"] = base_df.copy()

    working_df = st.session_state["pedido_df"].copy()

    categories = ["Todas"] + sorted(working_df["categoria"].dropna().unique().tolist())
    selected_category = st.selectbox("Filtrar por categoria", categories, index=0)

    if selected_category != "Todas":
        filtered_df = working_df[working_df["categoria"] == selected_category].copy()
    else:
        filtered_df = working_df.copy()

    st.subheader("Ajuste de Pedido")
    edit_columns = ["insumo", "categoria", "stock_fisico", "cantidad_requerida", "pedido_ajustado"]
    if "unidad_medida" in filtered_df.columns:
        edit_columns.insert(2, "unidad_medida")
    editable = filtered_df[edit_columns].copy()

    edited = st.data_editor(
        editable,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "stock_fisico": st.column_config.NumberColumn("Stock Actual", min_value=0.0, step=1.0),
            "cantidad_requerida": st.column_config.NumberColumn("Pedido Sugerido", disabled=True),
            "pedido_ajustado": st.column_config.NumberColumn("Pedido Ajustado", min_value=0.0, step=1.0),
            "insumo": st.column_config.TextColumn("Insumo", disabled=True),
            "categoria": st.column_config.TextColumn("Categoria", disabled=True),
            "unidad_medida": st.column_config.TextColumn("Unidad", disabled=True),
        },
    )

    updates = edited.set_index("insumo")["pedido_ajustado"].to_dict()
    st.session_state["pedido_df"].loc[
        st.session_state["pedido_df"]["insumo"].isin(updates.keys()), "pedido_ajustado"
    ] = st.session_state["pedido_df"]["insumo"].map(updates).fillna(st.session_state["pedido_df"]["pedido_ajustado"])

    analyzed = compute_risk(st.session_state["pedido_df"])
    if selected_category != "Todas":
        analyzed = analyzed[analyzed["categoria"] == selected_category].copy()

    total_risk = int(analyzed["riesgo_quiebre"].sum())
    total_items = int(len(analyzed))
    total_faltante = float(analyzed.loc[analyzed["riesgo_quiebre"], "faltante"].sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("Insumos en Riesgo", f"{total_risk}", f"de {total_items}")
    c2.metric("Faltante Total", f"{total_faltante:,.0f}")
    c3.metric("Cobertura", f"{(1 - (total_risk / total_items if total_items else 0))*100:,.1f}%")

    st.subheader("Stock Actual vs Pedido Sugerido")
    chart_df = analyzed[["insumo", "stock_fisico", "pedido_ajustado"]].set_index("insumo")
    st.bar_chart(chart_df, use_container_width=True)

    st.subheader("Tabla Dinamica de Riesgo")

    table_columns = ["insumo", "categoria"]
    if "unidad_medida" in analyzed.columns:
        table_columns.append("unidad_medida")
    table_columns.extend(["stock_fisico", "pedido_ajustado", "faltante", "estado_riesgo"])
    risk_table = analyzed[table_columns].copy()

    def highlight_row(row: pd.Series):
        if row["estado_riesgo"] == "Riesgo de Quiebre de Stock":
            return ["background-color: rgba(220, 38, 38, 0.30); color: #fff1f2; font-weight: 700;"] * len(row)
        return [""] * len(row)

    styled = (
        risk_table.style
        .apply(highlight_row, axis=1)
        .format(
            {
                "stock_fisico": "{:,.0f}",
                "pedido_ajustado": "{:,.0f}",
                "faltante": "{:,.0f}",
            }
        )
    )
    st.dataframe(styled, hide_index=True, use_container_width=True)

    tag = "pill pill-risk" if total_risk > 0 else "pill pill-safe"
    msg = "Riesgo de Quiebre de Stock" if total_risk > 0 else "Stock Suficiente"
    st.markdown(f"<span class='{tag}'>{msg}</span>", unsafe_allow_html=True)

    csv_data = analyzed.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Descargar proyeccion ajustada",
        data=csv_data,
        file_name="proyeccion_pedido_ajustada.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
