"""
core/sheets.py — IBD Companion
================================
Acceso a Google Sheets via gspread + Service Account.

Principios ALCOA+:
  - Sin borrado físico (baja lógica con Activo=False).
  - Cada append es atribuible, contemporáneo e inmutable.
  - Cache de 60 s en lecturas del dashboard para minimizar llamadas a la API.

Uso:
    from core.sheets import get_client, get_registros, append_registro, ...
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

from core.config import (
    COLUMNAS_ACCIONES,
    COLUMNAS_CONSENTIMIENTOS,
    COLUMNAS_DIARIAS,
    COLUMNAS_PACIENTES,
    COLUMNAS_PERIODICAS,
    PESTANAS,
)

# ─── Scopes de Google API ─────────────────────────────────────────────────────
_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


# ─── Inicialización del cliente ───────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def get_client() -> gspread.Client:
    """Devuelve el cliente gspread autenticado (singleton, cacheado por Streamlit)."""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=_SCOPES,
    )
    return gspread.authorize(creds)


def get_spreadsheet() -> gspread.Spreadsheet:
    """Abre el spreadsheet por ID definido en secrets."""
    client = get_client()
    return client.open_by_key(st.secrets["sheets"]["spreadsheet_id"])


def _worksheet(nombre: str) -> gspread.Worksheet:
    """
    Devuelve la hoja por nombre.
    1. Busca coincidencia exacta.
    2. Busca coincidencia case-insensitive (robusto ante mayúsculas del Sheet).
    3. Si no existe, la crea con la cabecera correcta.
    """
    ss = get_spreadsheet()
    # Coincidencia exacta
    try:
        return ss.worksheet(nombre)
    except gspread.WorksheetNotFound:
        pass
    # Coincidencia case-insensitive
    nombre_lower = nombre.lower()
    for ws in ss.worksheets():
        if ws.title.lower() == nombre_lower:
            return ws
    # No existe → crear
    return _crear_hoja(ss, nombre)


def _crear_hoja(ss: gspread.Spreadsheet, nombre: str) -> gspread.Worksheet:
    """Crea una hoja nueva con la cabecera correcta según su nombre."""
    cabeceras: dict[str, list[str]] = {
        PESTANAS["registros"].lower():        COLUMNAS_DIARIAS,
        PESTANAS["pacientes"].lower():        COLUMNAS_PACIENTES,
        PESTANAS["consentimientos"].lower():  COLUMNAS_CONSENTIMIENTOS,
        PESTANAS["acciones"].lower():         COLUMNAS_ACCIONES,
    }
    ws = ss.add_worksheet(title=nombre, rows=1000, cols=30)
    cols = cabeceras.get(nombre.lower(), [])
    if cols:
        ws.append_row(cols, value_input_option="RAW")
    return ws



# ─── Lecturas ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def get_registros(id_paciente: str | None = None) -> pd.DataFrame:
    """
    Carga todos los registros (diarios + periódicos).
    Si id_paciente se pasa, filtra solo ese paciente.
    """
    ws = _worksheet(PESTANAS["registros"])
    data = ws.get_all_records(default_blank="")
    df = pd.DataFrame(data)
    if df.empty:
        return df
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    if id_paciente:
        df = df[df["ID_Paciente"] == id_paciente]
    return df.sort_values("Timestamp", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=60, show_spinner=False)
def get_pacientes(solo_activos: bool = True) -> pd.DataFrame:
    """Carga la lista de pacientes."""
    ws = _worksheet(PESTANAS["pacientes"])
    data = ws.get_all_records(default_blank="")
    df = pd.DataFrame(data)
    if df.empty:
        return df
    if solo_activos and "Activo" in df.columns:
        df = df[df["Activo"].astype(str).str.lower() == "true"]
    return df.reset_index(drop=True)


def get_paciente(id_paciente: str) -> dict | None:
    """Devuelve el dict del paciente o None si no existe."""
    df = get_pacientes(solo_activos=False)
    if df.empty or "ID_Paciente" not in df.columns:
        return None
    fila = df[df["ID_Paciente"] == id_paciente]
    if fila.empty:
        return None
    return fila.iloc[0].to_dict()


@st.cache_data(ttl=60, show_spinner=False)
def get_consentimientos(id_paciente: str | None = None) -> pd.DataFrame:
    """Carga la pestaña de consentimientos."""
    ws = _worksheet(PESTANAS["consentimientos"])
    data = ws.get_all_records(default_blank="")
    df = pd.DataFrame(data)
    if df.empty:
        return df
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    if id_paciente:
        df = df[df["ID_Paciente"] == id_paciente]
    return df.sort_values("Timestamp", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=120, show_spinner=False)
def get_acciones(id_paciente: str | None = None) -> pd.DataFrame:
    """Carga el log de acciones del equipo."""
    ws = _worksheet(PESTANAS["acciones"])
    data = ws.get_all_records(default_blank="")
    df = pd.DataFrame(data)
    if df.empty:
        return df
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    if id_paciente:
        df = df[df["ID_Paciente"] == id_paciente]
    return df.sort_values("Timestamp", ascending=False).reset_index(drop=True)


# ─── Escrituras ───────────────────────────────────────────────────────────────

def append_registro(registro: dict) -> None:
    """
    Agrega un registro (diario o periódico) a la pestaña registros.
    Impone Timestamp ISO si no viene incluido.
    """
    registro.setdefault("Timestamp", datetime.now().isoformat(timespec="seconds"))
    ws = _worksheet(PESTANAS["registros"])
    # Determinar cabecera desde la primera fila
    cabecera = ws.row_values(1)
    if not cabecera:
        tipo = registro.get("Tipo_Registro", "diario")
        cabecera = COLUMNAS_DIARIAS if tipo == "diario" else COLUMNAS_PERIODICAS
        ws.append_row(cabecera, value_input_option="RAW")
    fila = [str(registro.get(col, "")) for col in cabecera]
    ws.append_row(fila, value_input_option="USER_ENTERED")
    # Invalidar cache
    get_registros.clear()


def append_paciente(paciente: dict) -> None:
    """Registra un nuevo paciente en la pestaña pacientes."""
    if "PIN" in paciente:
        paciente["PIN"] = _hash_pin(paciente["PIN"])
    paciente.setdefault("Fecha_Alta", datetime.now().date().isoformat())
    paciente.setdefault("Activo", "True")
    ws = _worksheet(PESTANAS["pacientes"])
    cabecera = ws.row_values(1) or COLUMNAS_PACIENTES
    fila = [str(paciente.get(col, "")) for col in cabecera]
    ws.append_row(fila, value_input_option="USER_ENTERED")
    get_pacientes.clear()


def append_consentimiento(consent: dict) -> None:
    """Registra un evento de consentimiento."""
    consent.setdefault("Timestamp", datetime.now().isoformat(timespec="seconds"))
    ws = _worksheet(PESTANAS["consentimientos"])
    cabecera = ws.row_values(1) or COLUMNAS_CONSENTIMIENTOS
    fila = [str(consent.get(col, "")) for col in cabecera]
    ws.append_row(fila, value_input_option="USER_ENTERED")
    get_consentimientos.clear()


def append_accion(accion: dict) -> None:
    """Registra una acción del equipo médico en la pestaña acciones."""
    accion.setdefault("Timestamp", datetime.now().isoformat(timespec="seconds"))
    ws = _worksheet(PESTANAS["acciones"])
    cabecera = ws.row_values(1) or COLUMNAS_ACCIONES
    fila = [str(accion.get(col, "")) for col in cabecera]
    ws.append_row(fila, value_input_option="USER_ENTERED")
    get_acciones.clear()


def baja_logica_paciente(id_paciente: str) -> None:
    """Marca un paciente como Activo=False (sin borrar el registro)."""
    ws = _worksheet(PESTANAS["pacientes"])
    data = ws.get_all_records(default_blank="")
    cabecera = ws.row_values(1)
    col_id = cabecera.index("ID_Paciente") + 1
    col_activo = cabecera.index("Activo") + 1
    for i, row in enumerate(data, start=2):
        if str(row.get("ID_Paciente")) == str(id_paciente):
            ws.update_cell(i, col_activo, "False")
    get_pacientes.clear()


# ─── Autenticación de paciente ────────────────────────────────────────────────

def verificar_pin(id_paciente: str, pin: str) -> bool:
    """Verifica el PIN hasheado contra el almacenado en el Sheet."""
    paciente = get_paciente(id_paciente)
    if not paciente:
        return False
    stored = str(paciente.get("PIN", ""))
    return stored == _hash_pin(pin)


def _hash_pin(pin: str) -> str:
    """SHA-256 del PIN (simple; usar bcrypt en producción real)."""
    return hashlib.sha256(pin.encode()).hexdigest()
