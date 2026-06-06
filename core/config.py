"""
core/config.py — IBD Companion
================================
Centraliza TODOS los umbrales clínicos y las definiciones de columnas del CRF.
NUNCA quemar umbrales en la lógica de triage o scores; siempre referenciar desde aquí.

Convención de nomenclatura:
  UMBRALES   → dict con valores numéricos clínicos
  COLUMNAS_* → listas ordenadas de nombres de columnas (coinciden con el Sheet)
  PESTANAS   → dict de nombres de pestañas del Google Sheet
  OPCIONES_* → listas de opciones para selectbox/radio en formularios
"""

# ─── Umbrales clínicos (STRIDE-II / guías ECCO) ──────────────────────────────
UMBRALES: dict = {
    # Calprotectina fecal (µg/g)
    "calpro_amarillo": 250,
    "calpro_rojo": 500,
    # PCR en sangre (mg/L)
    "PCR_amarillo": 5,
    "PCR_rojo": 30,
    # Número de deposiciones / día
    "deposiciones_amarillo": 4,
    "deposiciones_rojo": 6,
    # Escala de fatiga (1-10)
    "fatiga_amarillo": 7,
    # Hemoglobina (g/dL)
    "Hb_rojo": 10.5,
    # Frecuencia cardíaca (lpm)
    "FC_rojo": 90,
    # Temperatura (°C)
    "T_rojo": 37.8,
    # Peso mínimo de alerta (% pérdida en 3 meses)
    "peso_perdida_pct_amarillo": 5,
    # Albúmina (g/dL)
    "albumina_rojo": 3.0,
    # SIBDQ
    "SIBDQ_remision": 50,          # ≥50 = remisión funcional
    # Mayo parcial
    "mayo_remision": 2,            # ≤2 = remisión (sin subíndice sangre > 0)
    "mayo_leve": 4,                # ≤4 = leve
    "mayo_moderado": 6,            # ≤6 = moderado, >6 = severo
    # SCCAI
    "SCCAI_remision": 2,
    "SCCAI_leve": 5,
    "SCCAI_moderado": 11,
    # HBI (Harvey-Bradshaw)
    "HBI_remision": 4,
    "HBI_leve": 7,
    "HBI_moderado": 12,
    # Días sin registro antes de alerta de abandono
    "dias_sin_registro_amarillo": 5,
    "dias_sin_registro_rojo": 10,
}

# ─── Pestañas del Google Sheet ────────────────────────────────────────────────
PESTANAS: dict = {
    "registros": "Registros",
    "pacientes": "Pacientes",
    "consentimientos": "Consentimientos",
    "acciones": "Acciones",
}

# ─── Columnas CRF — Registro diario ──────────────────────────────────────────
COLUMNAS_DIARIAS: list[str] = [
    "ID_Paciente",
    "Timestamp",
    "Enfermedad",               # CU | EC
    "Deposiciones_Numero",
    "Sangre_Deposiciones",      # Ninguna | Estrías | Evidente | Sangre pura
    "Deposiciones_con_Sangre",  # Número de deposiciones con sangre (0 si Ninguna)
    "Urgencia",                 # Sí | No
    "Deposiciones_Nocturnas",   # Sí | No
    "Dolor_Abdominal",          # Ninguno | Leve | Moderado | Severo
    "Estado_General",           # 0-4
    "Escala_Fatiga",            # 1-10
    "Frecuencia_Cardiaca",      # lpm (opcional)
    "Temperatura",              # °C absolutos (0 = no medida)
    "Actividades_Diarias",      # Sin limitación | Leve | Moderada | Severa
    "Manif_Extraintestinales",  # texto libre (articulaciones, ojos, piel…)
    "Adherencia_Medicacion",    # Sí | No | Parcial
    "Notas_Paciente",           # texto libre
    "Tipo_Registro",            # "diario"
]

# ─── Columnas CRF — Registro periódico / evento ───────────────────────────────
COLUMNAS_PERIODICAS: list[str] = [
    "ID_Paciente",
    "Timestamp",
    "Enfermedad",
    "Calprotectina_Fecal",      # µg/g
    "PCR_Sangre",               # mg/L
    "Hemoglobina",              # g/dL
    "Albumina",                 # g/dL
    "Peso",                     # kg
    "Endoscopia_Resultado",     # texto libre / Normal / Leve / Moderada / Severa
    "Imagen_Resultado",         # texto libre
    "Cambio_Medicacion",        # texto libre
    "SIBDQ",                    # 10-70
    "Evento_Adverso",           # texto libre
    "Notas_Paciente",
    "Tipo_Registro",            # "periodico"
]

# ─── Columnas — Pestaña pacientes (datos basales) ─────────────────────────────
COLUMNAS_PACIENTES: list[str] = [
    "ID_Paciente",
    "Nombre",
    "Email",
    "Fecha_Nacimiento",
    "Enfermedad",               # CU | EC
    "Basal_Deposiciones",       # deposiciones/día en remisión (referencia personal)
    "Medicacion_Actual",
    "Fecha_Alta",               # fecha de ingreso al sistema
    "Activo",                   # True | False (baja lógica)
    "PIN",                      # hash del PIN de acceso
]

# ─── Columnas — Pestaña consentimientos ───────────────────────────────────────
COLUMNAS_CONSENTIMIENTOS: list[str] = [
    "ID_Paciente",
    "Timestamp",
    "Version",
    "Estado",                   # Vigente | Revocado | Vencido
    "Medio",                    # App | Presencial
    "IP",                       # dirección IP al momento del consent
]

# ─── Columnas — Pestaña acciones (auditoría) ─────────────────────────────────
COLUMNAS_ACCIONES: list[str] = [
    "Timestamp",
    "ID_Medico",
    "ID_Paciente",
    "Tipo_Accion",              # Llamada | Teleconsulta | Estudios | Ajuste_Terapeutico | Presencial | Guardia
    "Detalle",
    "Score_Momento",            # valor numérico del score en ese momento
    "Score_Tipo",               # pMayo | SCCAI | HBI
    "Triage_Momento",           # ROJO | AMARILLO | VERDE
    "Resultado",                # texto libre (qué respondió/qué pasó)
]

# ─── Opciones para formularios ────────────────────────────────────────────────
OPCIONES_SANGRE = ["Ninguna", "Estrías", "Evidente", "Sangre pura"]
OPCIONES_DOLOR = ["Ninguno", "Leve", "Moderado", "Severo"]
OPCIONES_ESTADO_GENERAL = {
    0: "0 — Muy bien",
    1: "1 — Levemente por debajo de lo normal",
    2: "2 — Mal, pero sigo mis actividades habituales",
    3: "3 — Mal, limita mis actividades cotidianas",
    4: "4 — Muy mal, incapacitado",
}
OPCIONES_ACTIVIDADES = ["Sin limitación", "Limitación leve", "Limitación moderada", "Limitación severa"]
OPCIONES_ADHERENCIA = ["Sí, tomé todo", "Parcial (olvidé alguna dosis)", "No tomé la medicación"]
OPCIONES_CONDUCTA = [
    "Llamada telefónica",
    "Teleconsulta",
    "Solicitud de estudios",
    "Ajuste terapéutico",
    "Consulta presencial",
    "Derivación a guardia",
]

# ─── Versión del consentimiento vigente ───────────────────────────────────────
# Se lee de st.secrets["app"]["consent_version"] en runtime;
# este valor es el fallback para tests sin Streamlit.
CONSENT_VERSION_FALLBACK = "v1.0"
CONSENT_FECHA_FALLBACK = "2026-06-01"
