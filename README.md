# README.md

# App: https://grafos.streamlit.app/:

**Explorador interactivo de grafos**

---

## Propósito 
Este repositorio muestra cómo transformar una tabla (CSV) en un **grafo** y cómo analizarlo y visualizarlo de forma interactiva.  
La idea clave: cada **valor** de una columna se convierte en un **nodo**  y dos nodos se conectan si **co-ocurren en la misma fila**.  


## Estructura del repo (qué archivos y carpetas hay)
```
repo-root/
├─ streamlit_app.py        # App principal (interfaz Streamlit)
├─ requirements.txt        # Dependencias para instalar
├─ README_teaching.md      # Este archivo (versión docente simplificada)
└─ src/
   ├─ __init__.py
   ├─ data_loader.py      # Leer CSVs robustamente
   ├─ graph_builder.py    # Construir grafo de co-ocurrencias
   ├─ metrics.py          # Calcular métricas del grafo
   ├─ visualization.py    # Crear graph.html con pyvis y links de descarga
   └─ utils.py            # Utilidades pequeñas (crear carpetas)



## Explicación módulo a módulo 


### `src/data_loader.py`  
**Qué hace** lee un archivo CSV aunque tenga problemas (diferente separador `;`, `\t`, o encoding `latin1`, etc.).  
**Por qué lo usamos:** muchos CSV vienen de distintas fuentes y fallan al leerlos; este módulo intenta leerlos de forma inteligente.

**Funciones principales:**

- `detect_encoding(path_or_bytes, nbytes=4096)`  
  - **Qué recibe:** una ruta de archivo o bytes (primeros bytes del archivo).  
  - **Qué devuelve:** el nombre del encoding detectado (por ejemplo `"utf-8"` o `"latin1"`).  
  - **Por qué sirve:** así intentamos leer el CSV con el encoding correcto y evitamos errores raros.

- `load_csv_smart(path_or_buffer)`  
  - **Qué recibe:** un path (ruta) o un objeto subido por el usuario (por ejemplo en Streamlit).  
  - **Qué hace (pasos):**
    1. Si es un objeto file-like (subida), toma sus bytes.
    2. Detecta encoding con `detect_encoding`.
    3. Intenta leer con distintos separadores: `,`, `;`, `\t`, `|`.
    4. Si ninguno funciona, cae a una lectura estándar de pandas.
  - **Qué devuelve:** un `pandas.DataFrame` listo para usar.  
  - **Ejemplo de uso:**  
    ```python
    df = load_csv_smart(uploaded_file)  # en Streamlit
    ```

---

### `src/graph_builder.py`  
**Qué hace:** construye el grafo a partir del DataFrame. Cada valor se convierte en nodo y se crean aristas cuando valores aparecen juntos en la misma fila.

**Funciones principales:**

- `node_id(col: str, val) -> str`  
  - **Qué recibe:** nombre de columna y un valor.  
  - **Qué devuelve:** una cadena única para el nodo.  
  - **Por qué:** evita confundir valores iguales que vienen de columnas distintas.

- `build_cooccurrence_graph(df: pd.DataFrame, cols: List[str], min_count: int = 1) -> nx.Graph`  
  - **Qué recibe:**
    - `df`: el DataFrame con tus datos.
    - `cols`: lista de columnas que quieres usar como entidades/nodos.
    - `min_count`: si >1, elimina aristas con peso menor (filtra ruido).
  - **Qué hace (pasos):**
    1. Crea un grafo vacío `G`.
    2. Para cada columna y cada valor único añade un nodo `node_id(col,val)` con atributos `label` y `column`.
    3. Recorre cada fila y toma los pares de valores presentes; por cada par suma `1` al `weight` de la arista entre ambos nodos (o la crea si no existía).
    4. Si `min_count > 1`, elimina aristas de peso bajo y nodos aislados.
  - **Qué devuelve:** un `networkx.Graph` con nodos y aristas con `weight`.  

  - **Consejo práctico:** construir el grafo puede ser costoso si tienes muchas filas o muchas columnas; filtra antes o elige pocas columnas.



### `src/metrics.py`  
**Qué hace** calcula métricas que nos ayudan a entender el grafo: quiénes son los más conectados, quiénes son los puentes entre grupos, cuáles son las comunidades, etc.  
**Importante:** algunas métricas son pesadas en tiempo; el módulo tiene estrategias para acelerar.

**Funciones principales:**

- `compute_graph_metrics(G, approx_betweenness=True, bet_k=None, max_nodes_for_exact=2000)`  
  - **Qué recibe:** el grafo `G` y algunas opciones para controlar precisión/velocidad.  
  - **Qué hace (pasos):**
    1. Calcula **degree** (número de vecinos) y **degree_weighted** (suma de pesos) — esto es rápido.
    2. Calcula **degree_centrality** (degree normalizado por tamaño del grafo).
    3. Calcula **betweenness**:
       - Si el grafo es pequeño (menos de `max_nodes_for_exact` nodos) y no pedimos aproximación, calcula **exacto**.
       - Si es grande, y `approx_betweenness=True`, calcula una **aproximación** muestreando `k` nodos fuente (esto ahorra mucho tiempo).
    4. Calcula **eigenvector centrality**:
       - Intenta usar métodos para matrices dispersas (`scipy.sparse.linalg.eigs`) — esto es rápido cuando la matriz es dispersa.
       - Si falla, usa el método clásico de NetworkX (más lento).
    5. Detecta **comunidades**:
       - Primero intenta con `igraph` (rápido).
       - Si no está, usa `python-louvain` (librería `community`) o, como último recurso, el método `greedy_modularity_communities` de NetworkX.
    6. Arma y devuelve dos tablas (`pandas.DataFrame`):
       - `nodes_df`: `node_id`, `label`, `column`, `degree`, `degree_weighted`, `degree_centrality`, `betweenness`, `eigenvector`, `community`.
       - `edges_df`: `u`, `v`, `weight`.
  - **Por qué es útil:** te devuelve los rankings y permite exportar para informes o para visualización con colores por comunidad.
  - **Ejemplo de uso:**
    ```python
    nodes_df, edges_df = compute_graph_metrics(G, approx_betweenness=True)

### `src/visualization.py`  
**Qué hace:** crea la visualización interactiva en HTML con pyvis y genera enlaces para descargar tablas como CSV desde Streamlit.

**Funciones principales:**

- `dataframe_download_link(df: pd.DataFrame, filename: str = "data.csv") -> str`  
  - **Qué devuelve:** un string HTML con un enlace que, al hacer click, descarga el DataFrame como CSV (se usa en la sidebar de Streamlit).

- `pyvis_graph_to_html(G: nx.Graph, nodes_df: pd.DataFrame, out_path: str = "graph.html", max_nodes_to_show: int = 800) -> str`  
  - **Qué hace:**
    1. Si el grafo es muy grande y `max_nodes_to_show` está fijado, filtra a los top-K nodos por `degree_weighted`.
    2. Crea un objeto `pyvis.Network`, añade nodos con `title` (tooltip) que muestra métricas y añade aristas con `value=peso`.
    3. Guarda un HTML (`graph.html`) que se puede abrir en cualquier navegador y donde se pueden mover nodos y hacer zoom.
  - **Ejemplo:**  
    ```python
    pyvis_graph_to_html(G, nodes_df, "outputs/graph.html", max_nodes_to_show=500)
    ```
  - **Consejo:** para clase, usar `max_nodes_to_show` pequeño (500) para que el navegador no se cuelgue.

---

### `src/utils.py`  
**Qué hace:** funciones pequeñas de ayuda (por ejemplo, crear carpetas si no existen).

**Función principal:**

- `ensure_dir(path: str)`  
  - **Qué hace:** crea una carpeta si no existe y devuelve la ruta.
  - **Uso típico:** guardar `outputs/graph.html` o `outputs/nodes_metrics.csv`.

# `streamlit_app.py` — qué hace en simples pasos

- Permite al usuario subir un CSV o usar `vf.csv` si existe.
- Muestra una vista previa del DataFrame.
- Genera filtros automáticos en la barra lateral (por columnas con baja cardinalidad).
- Permite descargar el dataset original y el filtrado.
- Tiene un generador de gráficos (Plotly) para crear scatter, line, bar, histogram, box con las columnas que el usuario elija.
- Permite construir el grafo seleccionando columnas; luego calcula métricas y muestra top-nodos.
- Genera el `graph.html` con pyvis y lo embebe en la app (si no es demasiado grande).


