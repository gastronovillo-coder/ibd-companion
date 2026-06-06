"""
core/triage.py — IBD Companion
================================
Clasificación de riesgo (semáforo) por enfermedad.

Principios de seguridad clínica:
  - Cualquier bandera ROJA → nivel ROJO (no importa el resto).
  - No adherencia → nunca VERDE.
  - Ante la duda → escalar (preferir falso positivo).
  - Devuelve siempre razones legibles, no sólo color.

Uso:
    from core.triage import triage
    resultado = triage(registro, paciente)
    # {"nivel": "ROJO", "razones": ["Sangre pura en deposiciones", ...], "score": {...}}
"""

from __future__ import annotations

from core.config import UMBRALES
from core.scores import calcular_score


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _safe_float(valor, default: float = 0.0) -> float:
    try:
        v = float(str(valor).replace(",", "."))
        return v if v == v else default   # NaN check
    except (ValueError, TypeError):
        return default


def _sangre_es_pura(sangre: str) -> bool:
    return str(sangre).lower().strip() in ("sangre pura",)


def _sangre_presente(sangre: str) -> bool:
    return str(sangre).lower().strip() not in ("ninguna", "", "none")


def _adherencia_incompleta(adherencia: str) -> bool:
    return str(adherencia).lower().strip() not in (
        "sí, tomé todo", "si, tome todo", "sí", "si", "true", "1"
    )


# ─── Triage CU ───────────────────────────────────────────────────────────────

def _triage_cu(registro: dict, paciente: dict | None = None) -> dict:
    """Clasificación de riesgo específica para Colitis Ulcerosa."""
    razones_rojo: list[str] = []
    razones_amarillo: list[str] = []

    sangre = registro.get("Sangre_Deposiciones", "Ninguna")
    dep = _safe_float(registro.get("Deposiciones_Numero", 0))
    fc = _safe_float(registro.get("Frecuencia_Cardiaca", 0))
    fiebre = _safe_float(registro.get("Temperatura") or registro.get("Fiebre", 0))
    # Si es delta (campo viejo < 10), convertir a absoluto para comparar
    if 0 < fiebre < 10:
        fiebre = 37.0 + fiebre
    hb = _safe_float(registro.get("Hemoglobina", 0))
    pcr = _safe_float(registro.get("PCR_Sangre", 0))
    calpro = _safe_float(registro.get("Calprotectina_Fecal", 0))
    fatiga = _safe_float(registro.get("Escala_Fatiga", 0))
    adherencia = registro.get("Adherencia_Medicacion", "Sí, tomé todo")

    # ── ROJO ────────────────────────────────────────────────────────────────
    if _sangre_es_pura(sangre):
        razones_rojo.append("Sangre pura en deposiciones (criterio de ASUC)")

    # ≥6 deposiciones CON sangre + ≥1 signo sistémico → sospecha ASUC
    signos_sistemicos: list[str] = []
    if fc > UMBRALES["FC_rojo"]:
        signos_sistemicos.append(f"FC {fc:.0f} lpm (> {UMBRALES['FC_rojo']})")
    if fiebre > 35 and fiebre >= UMBRALES["T_rojo"]:
        signos_sistemicos.append(f"Temperatura {fiebre:.1f}°C (≥ {UMBRALES['T_rojo']}°C)")
    if hb > 0 and hb < UMBRALES["Hb_rojo"]:
        signos_sistemicos.append(f"Hemoglobina {hb:.1f} g/dL (< {UMBRALES['Hb_rojo']})")
    if pcr > 0 and pcr >= UMBRALES["PCR_rojo"]:
        signos_sistemicos.append(f"PCR {pcr:.0f} mg/L (≥ {UMBRALES['PCR_rojo']})")

    if dep >= UMBRALES["deposiciones_rojo"] and _sangre_presente(sangre) and signos_sistemicos:
        razones_rojo.append(
            f"≥{UMBRALES['deposiciones_rojo']} deposiciones con sangre + signo(s) sistémico(s): "
            + "; ".join(signos_sistemicos)
            + " — Sospecha ASUC"
        )
    elif signos_sistemicos and _sangre_presente(sangre):
        # Signos sistémicos con sangre aunque < 6 → ROJO por seguridad
        razones_rojo.append(
            "Sangre en deposiciones + signo(s) sistémico(s): " + "; ".join(signos_sistemicos)
        )
    elif signos_sistemicos:
        for s in signos_sistemicos:
            razones_amarillo.append(f"Signo sistémico: {s}")

    # ── AMARILLO ────────────────────────────────────────────────────────────
    if calpro > 0:
        if calpro >= UMBRALES["calpro_rojo"]:
            razones_rojo.append(f"Calprotectina {calpro:.0f} µg/g (≥ {UMBRALES['calpro_rojo']})")
        elif calpro >= UMBRALES["calpro_amarillo"]:
            razones_amarillo.append(f"Calprotectina {calpro:.0f} µg/g (250-499 µg/g)")

    if pcr > 0 and UMBRALES["PCR_amarillo"] <= pcr < UMBRALES["PCR_rojo"]:
        razones_amarillo.append(f"PCR {pcr:.0f} mg/L (5-29 mg/L)")

    if UMBRALES["deposiciones_amarillo"] <= dep < UMBRALES["deposiciones_rojo"]:
        razones_amarillo.append(f"{dep:.0f} deposiciones/día (actividad leve-moderada)")

    if fatiga >= UMBRALES["fatiga_amarillo"]:
        razones_amarillo.append(f"Fatiga {fatiga:.0f}/10 (≥ {UMBRALES['fatiga_amarillo']})")

    if _adherencia_incompleta(adherencia):
        razones_amarillo.append(
            f"No adherencia a medicación: '{adherencia}' — siempre al menos AMARILLO"
        )

    # ── Clasificar ──────────────────────────────────────────────────────────
    resultado = _clasificar(razones_rojo, razones_amarillo)

    # ── Coherencia pMayo ↔ badge: score severo no puede quedar en VERDE ──────
    from core.scores import mayo_parcial
    pmayo = mayo_parcial(registro, paciente)
    ps = pmayo["score"]
    pi = pmayo["interpretacion"]

    if ps == 6 and resultado["nivel"] != "ROJO":
        resultado["nivel"] = "ROJO"
        msg = f"pMayo {ps}/6 — {pi}"
        resultado["razones"] = [msg] + resultado["razones"]
        resultado["razones_rojo"] = [msg] + resultado.get("razones_rojo", [])
    elif ps >= 4 and resultado["nivel"] == "VERDE":
        resultado["nivel"] = "AMARILLO"
        msg = f"pMayo {ps}/6 — {pi}"
        resultado["razones"] = [msg] + resultado["razones"]
        resultado["razones_amarillo"] = [msg] + resultado.get("razones_amarillo", [])

    return resultado


# ─── Triage EC ───────────────────────────────────────────────────────────────

def _triage_ec(registro: dict, paciente: dict | None = None) -> dict:
    """Clasificación de riesgo específica para Enfermedad de Crohn."""
    razones_rojo: list[str] = []
    razones_amarillo: list[str] = []

    dolor = str(registro.get("Dolor_Abdominal", "Ninguno")).lower()
    fiebre = _safe_float(registro.get("Temperatura") or registro.get("Fiebre", 0))
    # Si es delta (campo viejo < 10), convertir a absoluto para comparar
    if 0 < fiebre < 10:
        fiebre = 37.0 + fiebre
    calpro = _safe_float(registro.get("Calprotectina_Fecal", 0))
    pcr = _safe_float(registro.get("PCR_Sangre", 0))
    fatiga = _safe_float(registro.get("Escala_Fatiga", 0))
    adherencia = registro.get("Adherencia_Medicacion", "Sí, tomé todo")
    manif = str(registro.get("Manif_Extraintestinales", "") or "").lower()
    evento = str(registro.get("Evento_Adverso", "") or "").lower()
    actividades = str(registro.get("Actividades_Diarias", "") or "").lower()

    # Score HBI
    from core.scores import hbi as calc_hbi
    score_hbi = calc_hbi(registro, paciente)["score"]

    # ── ROJO ────────────────────────────────────────────────────────────────
    if score_hbi > UMBRALES["HBI_moderado"]:
        razones_rojo.append(f"HBI {score_hbi} (> {UMBRALES['HBI_moderado']} = severo)")

    if dolor == "severo" and fiebre > 35 and fiebre >= UMBRALES["T_rojo"]:
        razones_rojo.append(
            f"Dolor severo + fiebre {fiebre:.1f}°C — descartar complicación/absceso"
        )

    # Keywords de obstrucción
    palabras_obstruccion = ["obstrucción", "obstruccion", "vómito", "vomito", "distensión", "detención"]
    for kw in palabras_obstruccion:
        if kw in (manif + " " + evento):
            razones_rojo.append(f"Posible signo de obstrucción intestinal: '{kw}'")
            break

    # Keywords de complicación penetrante
    palabras_penetrante = ["fístula", "fistula", "absceso", "perforación", "perforacion"]
    for kw in palabras_penetrante:
        if kw in (manif + " " + evento):
            razones_rojo.append(f"Posible complicación penetrante: '{kw}'")
            break

    # ── AMARILLO ────────────────────────────────────────────────────────────
    if UMBRALES["HBI_remision"] < score_hbi <= UMBRALES["HBI_moderado"]:
        razones_amarillo.append(f"HBI {score_hbi} (actividad leve-moderada)")

    if calpro > 0:
        if calpro >= UMBRALES["calpro_rojo"]:
            razones_rojo.append(f"Calprotectina {calpro:.0f} µg/g (≥ {UMBRALES['calpro_rojo']})")
        elif calpro >= UMBRALES["calpro_amarillo"]:
            razones_amarillo.append(f"Calprotectina {calpro:.0f} µg/g (250-499 µg/g)")

    if pcr > 0 and UMBRALES["PCR_amarillo"] <= pcr < UMBRALES["PCR_rojo"]:
        razones_amarillo.append(f"PCR {pcr:.0f} mg/L (5-29 mg/L)")

    if pcr > 0 and pcr >= UMBRALES["PCR_rojo"]:
        razones_rojo.append(f"PCR {pcr:.0f} mg/L (≥ {UMBRALES['PCR_rojo']})")

    if fatiga >= UMBRALES["fatiga_amarillo"]:
        razones_amarillo.append(f"Fatiga {fatiga:.0f}/10 (≥ {UMBRALES['fatiga_amarillo']})")

    if _adherencia_incompleta(adherencia):
        razones_amarillo.append(
            f"No adherencia a medicación: '{adherencia}' — siempre al menos AMARILLO"
        )

    if "severa" in actividades:
        razones_amarillo.append("Limitación severa de actividades diarias")

    return _clasificar(razones_rojo, razones_amarillo)


# ─── Clasificador final ───────────────────────────────────────────────────────

def _clasificar(razones_rojo: list[str], razones_amarillo: list[str]) -> dict:
    """
    Aplica las reglas de seguridad:
      - Cualquier razón ROJA → nivel ROJO.
      - No adherencia está en AMARILLO → nunca VERDE si hay razones amarillas.
      - Sin razones → VERDE.
    """
    if razones_rojo:
        return {
            "nivel": "ROJO",
            "razones": razones_rojo + razones_amarillo,
            "razones_rojo": razones_rojo,
            "razones_amarillo": razones_amarillo,
        }
    elif razones_amarillo:
        return {
            "nivel": "AMARILLO",
            "razones": razones_amarillo,
            "razones_rojo": [],
            "razones_amarillo": razones_amarillo,
        }
    else:
        return {
            "nivel": "VERDE",
            "razones": ["En objetivo (remisión clínica)"],
            "razones_rojo": [],
            "razones_amarillo": [],
        }


# ─── Función pública principal ────────────────────────────────────────────────

def triage(registro: dict, paciente: dict | None = None) -> dict:
    """
    Clasifica el riesgo del paciente según su último registro.
    Si el registro está vacío devuelve nivel SIN_DATOS.
    """
    enfermedad = str(registro.get("Enfermedad", "") or "").upper()

    # Calcular score
    score_resultado = calcular_score(registro, paciente)

    # Triage por enfermedad
    if enfermedad == "CU":
        resultado = _triage_cu(registro, paciente)
    elif enfermedad == "EC":
        resultado = _triage_ec(registro, paciente)
    else:
        # Ante la duda, escalar
        resultado = {
            "nivel": "AMARILLO",
            "razones": ["Enfermedad no especificada — escalando por precaución"],
            "razones_rojo": [],
            "razones_amarillo": ["Enfermedad no especificada — escalando por precaución"],
        }

    resultado["score"] = score_resultado
    return resultado


# ─── Emoji / color helper para UI ────────────────────────────────────────────

NIVEL_UI = {
    "ROJO":     {"emoji": "🔴", "color": "#D32F2F", "bg": "#FFEBEE", "label": "Riesgo alto"},
    "AMARILLO": {"emoji": "🟡", "color": "#F57F17", "bg": "#FFF8E1", "label": "Riesgo moderado"},
    "VERDE":    {"emoji": "🟢", "color": "#2E7D32", "bg": "#E8F5E9", "label": "En remisión"},
    "SIN_DATOS":{"emoji": "⚪",    "color": "#757575", "bg": "#F5F5F5", "label": "Sin registros"},
}


def nivel_ui(nivel: str) -> dict:
    """Devuelve los atributos visuales del nivel de triage."""
    return NIVEL_UI.get(nivel.upper(), NIVEL_UI["AMARILLO"])
