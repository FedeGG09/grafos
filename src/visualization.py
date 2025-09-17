# src/visualization.py
"""
Visualización y utilidades para grafos con pyvis (actualizado para mostrar etiquetas visibles
y permitir configurar color de fondo).

Funciones principales:
- dataframe_download_link(df, filename) -> str
- pyvis_graph_to_html(G, nodes_df, out_path=..., max_nodes_to_show=..., show_labels=..., label_field=..., label_max_len=..., font_size=..., font_color=..., bgcolor=...)

Notas:
- Para que las etiquetas se vean, pyvis pasa la propiedad `label` al cliente (vis.js).
  Aquí truncamos etiquetas largas y además creamos un `title` HTML rico (tooltip) con las métricas.
- Si el grafo es muy grande se filtra por top-K nodos (por degree_weighted) antes de generar el HTML.
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
    Genera un link HTML para descargar un DataFrame como CSV (base64), útil en Streamlit.
    """
    towrite = io.BytesIO()
    df.to_csv(towrite, index=False)
    towrite.seek(0)
    b64 = base64.b64encode(towrite.read()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Descargar {filename}</a>'
    return href


def _truncate_label(text: str, max_len: int = 40) -> str:
    """
    Trunca una etiqueta manteniendo el prefijo y agregando '...' si es necesario.
    """
    if text is None:
        return ""
    s = str(text)
    if len(s) <= max_len:
        return s
    # mantener inicio y cortar si es muy largo
    head = s[: max_len - 3]
    return head + "..."


def pyvis_graph_to_html(
    G: nx.Graph,
    nodes_df: Optional[pd.DataFrame],
    out_path: str = "graph.html",
    max_nodes_to_show: Optional[int] = 800,
    show_labels: bool = True,
    label_field: str = "label",
    label_max_len: int = 40,
    font_size: int = 14,
    font_color: str = "#000000",
    physics: bool = True,
    bgcolor: str = "#ffffff"
) -> str:
    """
    Crea un archivo HTML interactivo con pyvis y devuelve la ruta.

    Parámetros destacados:
      - G: grafo networkx
      - nodes_df: DataFrame con métricas; debe contener 'node_id' y (opcional) las métricas que quieras mostrar en tooltip.
      - out_path: ruta de salida del HTML
      - max_nodes_to_show: si no None y G tiene más nodos, filtra a top-K por degree_weighted
      - show_labels: si True, fuerza a que cada nodo tenga una etiqueta visible (label)
      - label_field: campo en nodes_df (o en node attribute) que se usa para la etiqueta visible
      - label_max_len: máximo número de caracteres mostrados en la etiqueta (se trunca si es mayor)
      - font_size, font_color: estilo de la etiqueta (se pasa a vis.js vía pyvis)
      - physics: habilita/deshabilita simulación física
      - bgcolor: color de fondo para el HTML generado (ej. "#ffffff")
    """
    # Preparar lookup desde nodes_df (si viene)
    if nodes_df is None:
        nodes_lookup = {}
    else:
        df = nodes_df.copy()
        if 'node_id' not in df.columns:
            # intentar inferir índice o lanzar warning silencioso
            df = df.reset_index().rename(columns={df.index.name or 0: 'node_id'})
        df['node_id'] = df['node_id'].astype(str)
        nodes_lookup = df.set_index('node_id').to_dict('index')

    # Filtrado top-K si corresponde (por degree_weighted)
    G_to_show = G
    if max_nodes_to_show and G.number_of_nodes() > max_nodes_to_show:
        if nodes_df is not None and 'degree_weighted' in nodes_df.columns:
            top_nodes = nodes_df.sort_values('degree_weighted', ascending=False).head(max_nodes_to_show)['node_id'].astype(str).tolist()
        else:
            degs = dict(G.degree(weight='weight'))
            top_nodes = sorted(degs, key=lambda x: degs.get(x, 0), reverse=True)[:max_nodes_to_show]
        top_set = set(str(n) for n in top_nodes)
        G_to_show = G.subgraph([n for n in G.nodes() if str(n) in top_set]).copy()

    # Crear paleta simple por columnas si existen
    column_list = list({(d.get('column') if d.get('column') is not None else 'UNKNOWN') for _, d in G_to_show.nodes(data=True)})
    default_colors = [
        '#e6194b','#3cb44b','#ffe119','#4363d8','#f58231','#911eb4','#46f0f0','#f032e6',
        '#bcf60c','#fabebe','#800000','#808000','#00FFFF','#008080','#000080','#800080'
    ]
    color_map = {col: default_colors[i % len(default_colors)] for i, col in enumerate(column_list)}

    # Crear la red pyvis indicando bgcolor (fondo)
    net = Network(height="800px", width="100%", notebook=True, bgcolor=bgcolor)
    net.barnes_hut()
    net.toggle_physics(physics)

    # Añadir nodos con label (visible) y title (tooltip html)
    for n, d in G_to_show.nodes(data=True):
        node_id = str(n)
        row = nodes_lookup.get(node_id, {})
        # obtener etiqueta base: preferir label_field, sino atributo 'label', sino node_id
        raw_label = row.get(label_field) or d.get('label') or node_id
        label = _truncate_label(raw_label, max_len=label_max_len) if show_labels else None

        # preparar title HTML con más información (tooltip)
        title_lines = []
        title_lines.append(f"<b>{raw_label}</b>")
        col_val = row.get('column') or d.get('column')
        if col_val:
            title_lines.append(f"Columna: {col_val}")
        for metric in ('degree_weighted', 'degree', 'degree_centrality', 'betweenness', 'eigenvector', 'community'):
            if metric in row:
                val = row.get(metric)
                if isinstance(val, float):
                    val = f"{val:.4f}"
                title_lines.append(f"{metric}: {val}")
        title_lines.append(f"node_id: {node_id}")
        title_html = "<br>".join(title_lines)

        # color por columna
        col = row.get('column') or d.get('column') or 'UNKNOWN'
        color = color_map.get(col, "#888888")

        # font config: vis.js font dict
        font = {"size": font_size, "color": font_color, "face": "Arial"}

        # tamaño de nodo proporcional al degree_weighted si está disponible
        size = 10
        try:
            size = 8 + math.sqrt(float(row.get('degree_weighted', d.get('weight', 0) or 0))) * 3
            size = max(6, min(size, 36))
        except Exception:
            size = 10

        net.add_node(
            node_id,
            label=label,
            title=title_html,
            color=color,
            size=size,
            font=font
        )

    # Añadir aristas con peso y títulos
    for u, v, ed in G_to_show.edges(data=True):
        w = ed.get('weight', 1)
        net.add_edge(str(u), str(v), value=w, title=f"weight: {w}")

    # Opciones visuales globales para vis.js
    options = f"""
    var options = {{
      "nodes": {{
        "borderWidth": 1,
        "shadow": true
      }},
      "interaction": {{
        "hover": true,
        "tooltipDelay": 100
      }},
      "physics": {{
        "barnesHut": {{
          "gravitationalConstant": -8000,
          "centralGravity": 0.3,
          "springLength": 95,
          "springConstant": 0.04,
          "damping": 0.09
        }},
        "minVelocity": 0.75
      }}
    }}
    """
    net.set_options(options)

    # Guardar archivo HTML
    net.show(out_path)
    return out_path
