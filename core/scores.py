"""
core/scores.py — IBD Companion
================================
Cálculo de scores clínicos validados para EII.

CU  → Mayo Parcial (pMayo, 0-9)
      SCCAI (Simple Clinical Colitis Activity Index, 0-19)
EC  → HBI (Harvey-Bradshaw Index, 0-∞)

Todos los scores:
  - Reciben un dict `registro` con los campos del CRF.
  - Reciben opcionalmente un dict `paciente` para interpretar frecuencia relativa al basal.
  - Devuelven {"score": int, "interpretacion": str, "componentes": dict}.

Referencias:
  Mayo P et al. Gastroenterology 1987; Walmsley RS et al. Gut 1998;
  Harvey RF & Bradshaw JM. Lancet 1980.
"""

from __future__ import annotations

from core.config import UMBRALES

# ─── Helpers internos ─────────────────────────────────────────────────────────

def _sangre_a_puntos(sangre: str) -> int:
    """Convierte la opción de Sangre_Deposiciones al sub-índice del Mayo."""
    mapping = {
        "ninguna": 0,
        "estrías": 1,
        "estrías": 1,     # con tilde
        "evidente": 2,
        "sangre pura": 3,
    }
    return mapping.get(str(sangre).lower(), 0)


def _dolor_a_puntos_hbi(dolor: str) -> int:
    """HBI: dolor abdominal (0-3)."""
    mapping = {"ninguno": 0, "leve": 1, "moderado": 2, "severo": 3}
    return mapping.get(str(dolor).lower(), 0)


def _deposiciones_relativas(deposiciones: float, paciente: dict | None) -> float:
    """
    Devuelve las deposiciones ajustadas al basal del paciente si existe.
    Si el paciente tiene Basal_Deposiciones registrado, se resta para
    obtener el exceso sobre su normalidad personal.
    """
    if paciente:
        try:
            basal = float(paciente.get("Basal_Deposiciones", 0) or 0)
            return max(deposiciones - basal, 0)
        except (ValueError, TypeError):
            pass
    return deposiciones


def _estado_general_a_puntos(estado: int | str) -> int:
    """Estado general 0-4 → puntos HBI 0-4."""
    try:
        v = int(estado)
        return max(0, min(v, 4))
    except (ValueError, TypeError):
        return 0


def _interpretar_mayo(score: int) -> str:
    """pMayo parcial (0-6): frecuencia + sangrado."""
    if score <= UMBRALES["mayo_remision"]:
        return "Remisión"
    elif score <= 3:
        return "Actividad leve"
    elif score <= 5:
        return "Actividad moderada"
    else:
        return "Actividad severa"  # score 6 = máximo


def _interpretar_sccai(score: int) -> str:
    if score <= UMBRALES["SCCAI_remision"]:
        return "Remisión"
    elif score <= UMBRALES["SCCAI_leve"]:
        return "Actividad leve"
    elif score <= UMBRALES["SCCAI_moderado"]:
        return "Actividad moderada"
    else:
        return "Actividad severa"


def _interpretar_hbi(score: int) -> str:
    if score <= UMBRALES["HBI_remision"]:
        return "Remisión"
    elif score <= UMBRALES["HBI_leve"]:
        return "Actividad leve"
    elif score <= UMBRALES["HBI_moderado"]:
        return "Actividad moderada"
    else:
        return "Actividad severa"


# ─── Mayo Parcial (pMayo) — CU ────────────────────────────────────────────────

def mayo_parcial(registro: dict, paciente: dict | None = None) -> dict:
    """
    Mayo Parcial (pMayo): 0-6 puntos.

    Sub-índices (según la definición original):
      - Frecuencia de deposiciones (0-3): relativa al basal del paciente.
      - Sangrado rectal (0-3): Ninguna / Estrías / Evidente / Sangre pura.

    NOTA: La valoración global del médico (PGA, 0-3) es el tercer sub-índice
    del Mayo completo, pero NO se incluye en el pMayo parcial auto-reportado.
    Urgencia y deposiciones nocturnas pertenecen al SCCAI, no al pMayo.
    """
    try:
        dep = float(registro.get("Deposiciones_Numero", 0) or 0)
    except (ValueError, TypeError):
        dep = 0.0

    dep_rel = _deposiciones_relativas(dep, paciente)

    # Sub-índice frecuencia (0-3): deposiciones por encima del basal
    if dep_rel <= 0:
        si_frec = 0
    elif dep_rel <= 1:
        si_frec = 1
    elif dep_rel <= 2:
        si_frec = 2
    else:
        si_frec = 3

    # Sub-índice sangrado rectal (0-3)
    si_sangre = _sangre_a_puntos(registro.get("Sangre_Deposiciones", "Ninguna"))

    score = si_frec + si_sangre  # máximo 6

    return {
        "score": score,
        "interpretacion": _interpretar_mayo(score),
        "componentes": {
            "Frecuencia deposiciones": si_frec,
            "Sangrado rectal": si_sangre,
        },
    }


# ─── SCCAI — CU ──────────────────────────────────────────────────────────────

def sccai(registro: dict, paciente: dict | None = None) -> dict:
    """
    Simple Clinical Colitis Activity Index (SCCAI): 0-19 puntos.

    Componentes:
      1. Deposiciones diurnas (0-3)
      2. Deposiciones nocturnas (0-2)
      3. Urgencia (0-3)
      4. Sangre en heces (0-3)
      5. Estado general (0-4)
      6. Manifestaciones extraintestinales (0-3)
    """
    try:
        dep = float(registro.get("Deposiciones_Numero", 0) or 0)
    except (ValueError, TypeError):
        dep = 0.0

    # 1. Deposiciones diurnas (0-3)
    dep_rel = _deposiciones_relativas(dep, paciente)
    if dep_rel <= 1:
        s_dep_diurnas = 0
    elif dep_rel <= 3:
        s_dep_diurnas = 1
    elif dep_rel <= 5:
        s_dep_diurnas = 2
    else:
        s_dep_diurnas = 3

    # 2. Deposiciones nocturnas (0-2)
    noc = str(registro.get("Deposiciones_Nocturnas", "No")).lower()
    s_noc = 2 if noc == "sí" else (1 if noc == "si" else 0)

    # 3. Urgencia (0-3): no/leve/moderada/urgencia imperios
    urgencia = str(registro.get("Urgencia", "No")).lower()
    s_urgencia = 2 if urgencia in ("sí", "si") else 0

    # 4. Sangre (0-3)
    s_sangre = _sangre_a_puntos(registro.get("Sangre_Deposiciones", "Ninguna"))

    # 5. Estado general (0-4)
    s_estado = _estado_general_a_puntos(registro.get("Estado_General", 0))

    # 6. Manifestaciones extraintestinales (0-3): presencia de texto = 1
    manif = str(registro.get("Manif_Extraintestinales", "") or "").strip()
    s_manif = 1 if manif and manif.lower() not in ("no", "ninguna", "") else 0

    score = s_dep_diurnas + s_noc + s_urgencia + s_sangre + s_estado + s_manif

    return {
        "score": score,
        "interpretacion": _interpretar_sccai(score),
        "componentes": {
            "Deposiciones diurnas": s_dep_diurnas,
            "Deposiciones nocturnas": s_noc,
            "Urgencia": s_urgencia,
            "Sangre en heces": s_sangre,
            "Estado general": s_estado,
            "Manif. extraintestinales": s_manif,
        },
    }


# ─── HBI — EC ────────────────────────────────────────────────────────────────

def hbi(registro: dict, paciente: dict | None = None) -> dict:
    """
    Harvey-Bradshaw Index (HBI): 0-∞ (raramente >20).

    Componentes:
      1. Estado general (0-4)
      2. Dolor abdominal (0-3)
      3. Número de deposiciones líquidas/día (1 punto por cada una)
      4. Masa abdominal (0/2/5): aquí codificado desde Manif_Extraintestinales
      5. Complicaciones (1 punto por cada una): artritis, uveítis, eritema nodoso,
         aftas, pioderma, fístulas, absceso nuevo
    """
    # 1. Estado general
    s_estado = _estado_general_a_puntos(registro.get("Estado_General", 0))

    # 2. Dolor abdominal
    s_dolor = _dolor_a_puntos_hbi(registro.get("Dolor_Abdominal", "Ninguno"))

    # 3. Deposiciones líquidas
    try:
        dep = float(registro.get("Deposiciones_Numero", 0) or 0)
    except (ValueError, TypeError):
        dep = 0.0
    s_dep = int(dep)  # 1 punto por cada deposición líquida

    # 4. Masa abdominal (0 si no hay referencia explícita)
    s_masa = 0  # campo no explícito en el CRF diario; se puede agregar en periódico

    # 5. Complicaciones: keywords en Manif_Extraintestinales o Evento_Adverso
    complicaciones_keywords = [
        "artritis", "uveítis", "eritema", "aftas", "pioderma",
        "fístula", "absceso",
    ]
    manif = str(registro.get("Manif_Extraintestinales", "") or "").lower()
    evento = str(registro.get("Evento_Adverso", "") or "").lower()
    texto_comp = manif + " " + evento
    s_comp = sum(1 for kw in complicaciones_keywords if kw in texto_comp)

    score = s_estado + s_dolor + s_dep + s_masa + s_comp

    return {
        "score": score,
        "interpretacion": _interpretar_hbi(score),
        "componentes": {
            "Estado general": s_estado,
            "Dolor abdominal": s_dolor,
            "Deposiciones": s_dep,
            "Masa abdominal": s_masa,
            "Complicaciones": s_comp,
        },
    }


# ─── Selector por enfermedad ──────────────────────────────────────────────────

def calcular_score(registro: dict, paciente: dict | None = None) -> dict:
    """
    Calcula el score más apropiado según la enfermedad del paciente.
    Si el registro está vacío o no hay enfermedad, devuelve SIN_DATOS.
    Devuelve {"score": int, "tipo": str, "interpretacion": str, "componentes": dict}.
    """
    enfermedad = str(registro.get("Enfermedad", "") or "").upper()
    if enfermedad == "CU":
        resultado = mayo_parcial(registro, paciente)
        resultado["tipo"] = "pMayo"
    elif enfermedad == "EC":
        resultado = hbi(registro, paciente)
        resultado["tipo"] = "HBI"
    else:
        resultado = {
            "score": 0,
            "interpretacion": "Enfermedad no especificada",
            "componentes": {},
            "tipo": "N/A",
        }
    return resultado


def score_sin_datos() -> dict:
    """Marcador especial cuando un paciente no tiene ningún registro."""
    return {
        "score": None,
        "tipo": "SIN_DATOS",
        "interpretacion": "Sin registros aún",
        "componentes": {},
    }
