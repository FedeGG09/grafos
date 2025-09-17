# src/data_loader.py
"""
Funciones para cargar CSVs robustamente:
- load_csv_smart: intenta detectar separador, distintos encodings y usa fallback.
"""

import pandas as pd
import io
import chardet

def detect_encoding(path_or_bytes, nbytes=4096):
    """
    Detecta encoding usando chardet sobre los primeros nbytes.
    path_or_bytes: ruta (str) o bytes-like (uploaded file)
    """
    data = None
    if isinstance(path_or_bytes, (bytes, bytearray)):
        data = path_or_bytes[:nbytes]
    elif hasattr(path_or_bytes, "read"):
        pos = path_or_bytes.tell()
        data = path_or_bytes.read(nbytes)
        path_or_bytes.seek(pos)
    else:
        # assume path
        with open(path_or_bytes, "rb") as f:
            data = f.read(nbytes)
    res = chardet.detect(data)
    return res.get("encoding", "utf-8")

def load_csv_smart(path_or_buffer):
    """
    Carga CSV desde:
    - uploaded file-like (streamlit's UploadedFile)
    - path string
    Intenta distintos separadores y encodings.
    """
    # Si es file-like (UploadedFile), obtener bytes
    if hasattr(path_or_buffer, "getvalue"):
        raw = path_or_buffer.getvalue()
        enc = detect_encoding(raw)
        # intentar sniffer simple
        for sep in [",", ";", "\t", "|"]:
            try:
                df = pd.read_csv(io.BytesIO(raw), sep=sep, encoding=enc, low_memory=False)
                return df
            except Exception:
                continue
        # fallback: pandas autodetect
        return pd.read_csv(io.BytesIO(raw), low_memory=False)
    else:
        # path
        enc = detect_encoding(path_or_buffer)
        for sep in [",", ";", "\t", "|"]:
            try:
                df = pd.read_csv(path_or_buffer, sep=sep, encoding=enc, low_memory=False)
                return df
            except Exception:
                continue
        return pd.read_csv(path_or_buffer, low_memory=False)
