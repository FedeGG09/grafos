# grafos

# Explorador interactivo de grafos (Colab + Streamlit)

Repositorio con una app Streamlit modular para:
- cargar datasets CSV,
- filtrar datos,
- generar gráficos interactivos (Plotly),
- construir grafos de co-ocurrencias,
- calcular métricas optimizadas y comunidades,
- visualizar el grafo interactivamente con Pyvis.

## Estructura
- `streamlit_app.py` - App principal (deploy).
- `src/` - módulos: data_loader, graph_builder, metrics, visualization, utils.
- `requirements.txt` - dependencias.

## Instalación local
```bash
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
streamlit run streamlit_app.py
