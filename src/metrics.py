# src/metrics.py
"""
Cálculo de métricas de grafo optimizadas:
- degree, degree_weighted, degree_centrality
- betweenness (aprox por muestreo si el grafo es grande)
- eigenvector (usar sparse ARPACK cuando posible)
- detección de comunidades (igraph -> python-louvain -> networkx greedy)
"""

import time
import math
from typing import Tuple
import networkx as nx
import pandas as pd
import numpy as np

def compute_graph_metrics(
    G: nx.Graph,
    approx_betweenness: bool = True,
    bet_k: int = None,
    max_nodes_for_exact: int = 2000
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Retorna nodes_df y edges_df con métricas.
    - approx_betweenness: si True calcula aproximación cuando G es grande
    - bet_k: número de fuentes para aproximación (None -> auto)
    """
    tstart = time.time()
    n_nodes = G.number_of_nodes()
    # degree y degree_weighted
    degree = dict(G.degree())
    degree_w = dict(G.degree(weight="weight"))
    if n_nodes > 1:
        degree_centrality = {n: d / (n_nodes - 1) for n, d in degree.items()}
    else:
        degree_centrality = {n: 0.0 for n in G.nodes()}

    # betweenness (exacta o aproximada)
    if bet_k is None:
        if approx_betweenness and n_nodes > max_nodes_for_exact:
            k = int(min(500, max(50, math.sqrt(n_nodes) * 10)))
        else:
            k = None
    else:
        k = bet_k

    if k is None:
        # exact (puede tardar en grafos grandes)
        bet = nx.betweenness_centrality(G, weight="weight")
    else:
        # aproximada
        try:
            bet = nx.betweenness_centrality(G, k=k, weight="weight", seed=42)
        except TypeError:
            # versión antigua de networkx: fallback a exact (advertir)
            bet = nx.betweenness_centrality(G, weight="weight")

    # eigenvector con sparse si es posible
    eig = {}
    try:
        import scipy.sparse as sp
        from scipy.sparse.linalg import eigs, ArpackNoConvergence
        nodes = list(G.nodes())
        A = nx.to_scipy_sparse_matrix(G, nodelist=nodes, weight="weight", format="csr", dtype=float)
        if A.shape[0] == 0:
            eig = {n: 0.0 for n in nodes}
        elif A.shape[0] == 1:
            eig = {nodes[0]: 1.0}
        else:
            vals, vecs = eigs(A, k=1, which="LM", maxiter=200)
            vec = np.real(vecs[:, 0])
            vec = np.abs(vec)
            if vec.sum() != 0:
                vec = vec / vec.sum()
            eig = {nodes[i]: float(vec[i]) for i in range(len(nodes))}
    except Exception:
        # fallback a networkx power method
        try:
            eig = nx.eigenvector_centrality(G, max_iter=200)
        except Exception:
            eig = {n: 0.0 for n in G.nodes()}

    # comunidades: preferir igraph -> python-louvain -> greedy
    node_community = {}
    try:
        import igraph as ig
        nodes = list(G.nodes())
        idx = {n: i for i, n in enumerate(nodes)}
        edges = [(idx[u], idx[v]) for u, v in G.edges()]
        weights = [d.get("weight", 1) for _, _, d in G.edges(data=True)]
        g_ig = ig.Graph(edges=edges, directed=False)
        if any(weights):
            g_ig.es["weight"] = weights
        cl = g_ig.community_multilevel(weights=g_ig.es["weight"] if "weight" in g_ig.es.attributes() else None)
        for cid, comm in enumerate(cl):
            for vid in comm:
                node_community[nodes[vid]] = int(cid)
    except Exception:
        try:
            import community as community_louvain
            part = community_louvain.best_partition(G, weight="weight")
            node_community = {n: int(c) for n, c in part.items()}
        except Exception:
            try:
                from networkx.algorithms import community as nx_comm
                comms = list(nx_comm.greedy_modularity_communities(G, weight="weight"))
                for i, comm in enumerate(comms):
                    for n in comm:
                        node_community[n] = int(i)
            except Exception:
                node_community = {n: -1 for n in G.nodes()}

    # armar DataFrames
    nodes_data = []
    for n, d in G.nodes(data=True):
        nodes_data.append({
            "node_id": n,
            "label": d.get("label"),
            "column": d.get("column"),
            "degree": int(degree.get(n, 0)),
            "degree_weighted": float(degree_w.get(n, 0)),
            "degree_centrality": float(degree_centrality.get(n, 0)),
            "betweenness": float(bet.get(n, 0)),
            "eigenvector": float(eig.get(n, 0)),
            "community": int(node_community.get(n, -1))
        })
    nodes_df = pd.DataFrame(nodes_data).sort_values("degree_weighted", ascending=False)

    edges_data = [{"u": u, "v": v, "weight": d.get("weight", 1)} for u, v, d in G.edges(data=True)]
    edges_df = pd.DataFrame(edges_data).sort_values("weight", ascending=False)

    return nodes_df, edges_df
