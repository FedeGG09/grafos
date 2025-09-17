# src/graph_builder.py
"""
Construcción de grafo de co-ocurrencias.
Nodo: "col::valor" para evitar colisiones entre columnas.
"""

import networkx as nx
import pandas as pd
from itertools import combinations
from typing import List

def node_id(col: str, val) -> str:
    return f"{col}::" + str(val)

def build_cooccurrence_graph(df: pd.DataFrame, cols: List[str], min_count: int = 1) -> nx.Graph:
    """
    Construye grafo de co-ocurrencias.
    - df: dataframe
    - cols: columnas a considerar (listas)
    - min_count: filtra aristas con peso < min_count (post-build)
    """
    G = nx.Graph()
    # añadir nodos
    for col in cols:
        unique_vals = df[col].dropna().unique()
        for v in unique_vals:
            G.add_node(node_id(col, v), label=str(v), column=col)

    # iterar filas; recomendable filtrar df previamente si es muy grande
    for idx, row in df[cols].dropna(how="all").iterrows():
        items = [(c, row[c]) for c in cols if pd.notna(row[c])]
        for (c1, v1), (c2, v2) in combinations(items, 2):
            u = node_id(c1, v1)
            v = node_id(c2, v2)
            if G.has_edge(u, v):
                G[u][v]["weight"] += 1
            else:
                G.add_edge(u, v, weight=1)

    # opcional: remover aristas de bajo peso
    if min_count > 1:
        to_remove = [(u, v) for u, v, d in G.edges(data=True) if d.get("weight", 1) < min_count]
        G.remove_edges_from(to_remove)
        # eliminar nodos aislados
        isolated = list(nx.isolates(G))
        if isolated:
            G.remove_nodes_from(isolated)

    return G
