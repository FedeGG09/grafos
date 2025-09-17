# streamlit_app.py
"""
App Streamlit principal. Interactúa con los módulos en /src para:
- cargar datos
- aplicar filtros
- generar gráficos con Plotly
- construir un grafo (co-ocurrencias)
- calcular métricas optimizadas
- visualizar pyvis embebido y descargar resultados
"""

import os
import io
import base64
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from streamlit.components.v1 import html as st_html

# Añadir src al path para imports locales
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from data_loader import load_csv_smart
from graph_builder import build_cooccurrence_graph
from metrics import compute_graph_metrics
from visualization import pyvis_graph_to_html, dataframe_download_link
from utils import ensure_dir

st.set_page_config(layout="wide", page_title="Explorador de Grafos")

st.title("Exploración y visualización interactiva de grafos")

# Sidebar - carga
st.sidebar.header("Carga de datos")
uploaded = st.sidebar.file_uploader("Subí un CSV (ej: vf.csv)", type=["csv"])
use_example = st.sidebar.checkbox("Usar dataset de ejemplo (si existe vf.csv local)", value=False)

if uploaded is not None:
    try:
        df = load_csv_smart(uploaded)
    except Exception as e:
        st.sidebar.error(f"Error al leer el CSV subido: {e}")
        st.stop()
elif use_example and os.path.exists("vf.csv"):
    df = load_csv_smart("vf.csv")
else:
    st.sidebar.info("Subí un CSV o activa 'Usar dataset de ejemplo' con vf.csv en el repo.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.header("Export/Descarga")
st.sidebar.markdown(dataframe_download_link(df, "original.csv"), unsafe_allow_html=True)

# Main layout: left data + right controls/preview
left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("Vista previa de los datos")
    st.dataframe(df.head(200))
    st.markdown(f"**Filas:** {df.shape[0]} — **Columnas:** {df.shape[1]}")

with right_col:
    st.subheader("Selección rápida de columnas")
    # columnas categóricas candidate
    cat_cols = [c for c in df.columns if df[c].dtype == "object" or df[c].nunique() < 200]
    st.write("Columnas candidatas (categóricas/baja cardinalidad):")
    st.write(cat_cols[:50])

st.markdown("---")
st.header("1) Filtros dinámicos")

# Generar filtros automáticos para columnas que convienen (object o pocos valores)
filter_cols = [c for c in df.columns if (df[c].dtype == "object" and df[c].nunique() <= 200)]
filter_cols += [c for c in df.columns if df[c].dtype != "object" and df[c].nunique() <= 20]
filter_cols = sorted(list(set(filter_cols)))

st.sidebar.header("Filtros dinámicos")
active_filters = {}
for c in filter_cols:
    if df[c].dtype == "object":
        vals = list(df[c].dropna().unique())
        sel = st.sidebar.multiselect(f"{c}", options=sorted(vals), default=vals[:5])
        if sel:
            active_filters[c] = sel
    else:
        # numeric small cardinality -> multiselect
        vals = sorted(df[c].dropna().unique().tolist())
        sel = st.sidebar.multiselect(f"{c}", options=vals, default=vals[:5] if len(vals) > 0 else [])
        if sel:
            active_filters[c] = sel

# Aplicar filtros
df_filtered = df.copy()
for c, vals in active_filters.items():
    df_filtered = df_filtered[df_filtered[c].isin(vals)]

st.markdown(f"Dataset filtrado: {df_filtered.shape[0]} filas")

# Download filtered
st.markdown(dataframe_download_link(df_filtered, "filtered.csv"), unsafe_allow_html=True)

st.markdown("---")
st.header("2) Generador de gráficos interactivos")

chart_type = st.selectbox("Tipo de gráfico", ["scatter", "line", "bar", "histogram", "box"])
cols_all = df_filtered.columns.tolist()
cols_numeric = df_filtered.select_dtypes(include="number").columns.tolist()

col1, col2 = st.columns([1,1])
with col1:
    x_col = st.selectbox("Eje X", options=cols_all, index=0)
with col2:
    y_col = st.selectbox("Eje Y (si aplica)", options=[None] + cols_numeric, index=0 if cols_numeric else None)

color_col = st.selectbox("Color (opcional)", options=[None] + cols_all, index=0)

if st.button("Generar gráfico"):
    try:
        if chart_type == "scatter":
            if y_col is None:
                st.error("Scatter necesita eje y numérico.")
            else:
                fig = px.scatter(df_filtered, x=x_col, y=y_col, color=color_col, hover_data=cols_all)
                st.plotly_chart(fig, use_container_width=True)
        elif chart_type == "line":
            if y_col is None:
                st.error("Line necesita eje y numérico.")
            else:
                fig = px.line(df_filtered, x=x_col, y=y_col, color=color_col)
                st.plotly_chart(fig, use_container_width=True)
        elif chart_type == "bar":
            if y_col is None:
                fig = px.bar(df_filtered, x=x_col, color=color_col)
            else:
                fig = px.bar(df_filtered, x=x_col, y=y_col, color=color_col)
            st.plotly_chart(fig, use_container_width=True)
        elif chart_type == "histogram":
            fig = px.histogram(df_filtered, x=x_col, color=color_col)
            st.plotly_chart(fig, use_container_width=True)
        elif chart_type == "box":
            if y_col is None:
                st.error("Box necesita eje y numérico.")
            else:
                fig = px.box(df_filtered, x=x_col, y=y_col, color=color_col)
                st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error creando gráfico: {e}")

st.markdown("---")
st.header("3) Construir grafo (co-ocurrencias) y analizar")

st.info("Seleccioná columnas categóricas (o de baja cardinalidad) para construir nodos. Nodo = 'col::valor'.")

default_choices = [c for c in df.columns if df[c].dtype == "object"][:3]
selected_cols = st.multiselect("Columnas para nodos", options=list(df.columns), default=default_choices)

col1, col2 = st.columns([1,1])
with col1:
    max_nodes_filter = st.number_input("Max nodos a mostrar en visualización (0 = sin filtro)", min_value=0, value=800, step=100)
with col2:
    use_approx = st.checkbox("Usar aproximación para betweenness si es grande", value=True)

if st.button("Construir y analizar grafo"):
    if not selected_cols:
        st.error("Seleccioná al menos una columna para construir el grafo.")
    else:
        with st.spinner("Construyendo grafo..."):
            G = build_cooccurrence_graph(df_filtered, selected_cols)
        st.success(f"Grafo construido: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")

        # Calcular métricas (óptimas)
        st.info("Calculando métricas (puede tardar según tamaño).")
        nodes_df, edges_df = compute_graph_metrics(
            G,
            approx_betweenness=use_approx,
            bet_k=None,          # None => auto
            max_nodes_for_exact=2000
        )
        st.write("Top nodos (por degree_weighted):")
        st.dataframe(nodes_df.head(20))

        # Guardar archivos en disco para descargar
        out_dir = ensure_dir("outputs")
        nodes_csv = os.path.join(out_dir, "nodes_metrics.csv")
        edges_csv = os.path.join(out_dir, "edges_metrics.csv")
        nodes_df.to_csv(nodes_csv, index=False)
        edges_df.to_csv(edges_csv, index=False)
        st.sidebar.markdown(dataframe_download_link(nodes_df, "nodes_metrics.csv"), unsafe_allow_html=True)
        st.sidebar.markdown(dataframe_download_link(edges_df, "edges_metrics.csv"), unsafe_allow_html=True)

        # Visualizar con pyvis (guardar graph.html)
        st.info("Generando visualización interactiva (pyvis)...")
        html_path = os.path.join(out_dir, "graph.html")
        pyvis_graph_to_html(G, nodes_df, html_path, max_nodes_to_show=max_nodes_filter)
        st.success(f"graph.html creado: {html_path}")

        # Mostrar el graph.html embebido (si < max size)
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                html_text = f.read()
            st_html(html_text, height=700)
        except Exception as e:
            st.error(f"No pude embeber graph.html: {e}. Descargalo desde Outputs.")

st.markdown("---")
st.write("Hecho — podes clonar este repo, ajustar parámetros y desplegar en Streamlit Cloud o localmente.")
