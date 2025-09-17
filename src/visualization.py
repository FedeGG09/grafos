# src/visualization.py
"""
Funciones de visualización:
- pyvis_graph_to_html: crear graph.html desde networkx + metrics
- dataframe_download_link: generar link base64 para descarga de DataFrame
"""

import math
import networkx as nx
from pyvis.network import Network
import pandas as pd
import io
import base64
from typing import Optional

def dataframe_download_link(df: pd.DataFrame, filename: str = "data.csv") -> str:
    """
    Genera un link HTML para descargar un DataFrame como CSV en Streamlit.
    """
    towrite = io.BytesIO()
    df.to_csv(towrite, index=False)
    towrite.seek(0)
    b64 = base64.b64encode(towrite.read()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Descargar {filename}</a>'
    return href

def pyvis_graph_to_html(
    G: nx.Graph,
    nodes_df: pd.DataFrame,
    out_path: str = "graph.html",
    max_nodes_to_show: int = 800
) -> str:
    """
    Crea un archivo HTML interactivo con pyvis y devuelve la ruta.
    - Si max_nodes_to_show > 0 y el grafo es más grande, filtra por top-k degree_weighted.
    """
    G_to_show = G
    if max_nodes_to_show and G.number_of_nodes() > max_nodes_to_show:
        top_nodes = set(nodes_df.head(max_nodes_to_show)["node_id"].tolist())
        G_to_show = G.subgraph([n for n in G.nodes() if n in top_nodes]).copy()

    # palette
    columns = list({(d.get("column") if d.get("column") is not None else "UNKNOWN") for _, d in G_to_show.nodes(data=True)})
    palette = [
        "#e6194b","#3cb44b","#ffe119","#4363d8","#f58231","#911eb4","#46f0f0",
        "#f032e6","#bcf60c","#fabebe","#800000","#808000","#00FFFF","#008080"
    ]
    color_map = {col: palette[i % len(palette)] for i, col in enumerate(columns)}

    net = Network(height="800px", width="100%", notebook=True)
    net.barnes_hut()

    lookup = nodes_df.set_index("node_id").to_dict("index")

    for n, d in G_to_show.nodes(data=True):
        if n in lookup:
            row = lookup[n]
            label = str(row.get("label", n))
            col = row.get("column", "UNKNOWN")
            title = f"<b>{label}</b><br>Col: {col}<br>Degree(w): {row.get('degree_weighted',0)}<br>Community: {row.get('community',-1)}"
            size = 8 + (math.sqrt(max(row.get("degree_weighted", 0), 0)) * 4)
        else:
            label = str(d.get("label", n))
            col = d.get("column", "UNKNOWN")
            title = f"<b>{label}</b><br>Col: {col}"
            size = 8
        net.add_node(n, label=label, title=title, color=color_map.get(col, "#888888"), size=size)

    for u, v, dd in G_to_show.edges(data=True):
        w = dd.get("weight", 1)
        net.add_edge(u, v, value=w, title=f"weight: {w}")

    net.show(out_path)
    return out_path
