# src/utils.py
"""
Funciones utilitarias pequeñas.
"""

import os

def ensure_dir(path: str):
    """Asegura que exista el directorio `path` y lo devuelve."""
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path
