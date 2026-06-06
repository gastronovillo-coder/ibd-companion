"""
tests/test_triage.py — IBD Companion
Pruebas de triage para los escenarios del Definition of Done.

Cobertura:
  - CU: remisión, actividad leve-moderada, ASUC, no-adherencia
  - EC: remisión, actividad severa
  - pMayo: coherencia score ↔ badge, límites 0-6
  - SIN_DATOS: score_sin_datos()
  - Temperatura: comparación en escala absoluta

Correr con: python tests/test_triage.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.triage import triage
from core.scores import mayo_parcial, hbi, score_sin_datos

# ─── Pacientes de referencia ──────────────────────────────────────────────────

PAC_CU = {"ID_Paciente": "PAC-CU-01", "Enfermedad": "CU", "Basal_Deposiciones": 1}
PAC_EC = {"ID_Paciente": "PAC-EC-01", "Enfermedad": "EC", "Basal_Deposiciones": 2}

# ─── Escenarios CU ────────────────────────────────────────────────────────────

def test_cu_remision():
    """CU en remisión → VERDE, pMayo ≤ 2."""
    reg = {
        "Enfermedad": "CU",
        "Deposiciones_Numero": 1,   # igual al basal → dep_rel=0 → si_frec=0
        "Sangre_Deposiciones": "Ninguna",
        "Urgencia": "No",
        "Deposiciones_Nocturnas": "No",
        "Dolor_Abdominal": "Ninguno",
        "Estado_General": 0,
        "Escala_Fatiga": 2,
        "Frecuencia_Cardiaca": 70,
        "Temperatura": 0,
        "Adherencia_Medicacion": "Sí, tomé todo",
    }
    r = triage(reg, PAC_CU)
    assert r["nivel"] == "VERDE", f"CU remisión esperaba VERDE, got {r['nivel']}: {r['razones']}"
    pm = mayo_parcial(reg, PAC_CU)
    assert pm["score"] <= 2, f"pMayo remisión esperaba ≤2, got {pm['score']}"
    print(f"✅ CU remisión → VERDE  |  pMayo {pm['score']}/6 ({pm['interpretacion']})")


def test_cu_leve_moderado():
    """CU actividad leve-moderada → AMARILLO."""
    reg = {
        "Enfermedad": "CU",
        "Deposiciones_Numero": 4,   # +3 sobre basal=1 → si_frec=3
        "Sangre_Deposiciones": "Estrías",  # si_sangre=1 → pMayo=4 → moderado → badge AMARILLO
        "Urgencia": "Sí",
        "Deposiciones_Nocturnas": "No",
        "Dolor_Abdominal": "Leve",
        "Estado_General": 1,
        "Escala_Fatiga": 5,
        "Frecuencia_Cardiaca": 80,
        "Temperatura": 0,
        "Adherencia_Medicacion": "Sí, tomé todo",
    }
    r = triage(reg, PAC_CU)
    assert r["nivel"] == "AMARILLO", f"CU leve esperaba AMARILLO, got {r['nivel']}: {r['razones']}"
    pm = r["score"]
    assert pm["tipo"] == "pMayo", "Score tipo debe ser pMayo"
    assert pm["score"] <= 6, f"pMayo nunca puede superar 6, got {pm['score']}"
    print(f"✅ CU actividad leve → AMARILLO  |  pMayo {pm['score']}/6 ({pm['interpretacion']})")


def test_cu_asuc():
    """Sospecha ASUC: sangre pura + sistémicos → ROJO inmediato. Usa temperatura absoluta."""
    reg = {
        "Enfermedad": "CU",
        "Deposiciones_Numero": 8,
        "Sangre_Deposiciones": "Sangre pura",
        "Urgencia": "Sí",
        "Deposiciones_Nocturnas": "Sí",
        "Dolor_Abdominal": "Severo",
        "Estado_General": 3,
        "Escala_Fatiga": 9,
        "Frecuencia_Cardiaca": 105,
        "Temperatura": 38.2,           # absoluto: 38.2°C ≥ T_rojo(37.8)
        "Hemoglobina": 9.5,
        "PCR_Sangre": 55,
        "Adherencia_Medicacion": "Sí, tomé todo",
    }
    r = triage(reg, PAC_CU)
    assert r["nivel"] == "ROJO", f"ASUC esperaba ROJO, got {r['nivel']}"
    asuc_mencionado = any("ASUC" in ra or "Sangre pura" in ra for ra in r["razones"])
    assert asuc_mencionado, f"No menciona ASUC/Sangre pura: {r['razones']}"
    pm = r["score"]
    assert pm["score"] == 6, f"ASUC: pMayo máximo=6, got {pm['score']}"  # 3+3
    assert pm["score"] <= 6, "pMayo nunca puede superar 6"
    print(f"✅ CU ASUC → ROJO  | pMayo {pm['score']}/6 | Razones: {r['razones_rojo']}")


def test_cu_pmayo_max_6():
    """pMayo nunca puede superar 6 (frecuencia 0-3 + sangrado 0-3)."""
    reg = {
        "Enfermedad": "CU",
        "Deposiciones_Numero": 20,       # ≥3 sobre basal → si_frec=3
        "Sangre_Deposiciones": "Sangre pura",  # si_sangre=3
        "Estado_General": 4,             # NO entra en pMayo parcial
        "Urgencia": "Sí",               # NO entra en pMayo parcial
        "Deposiciones_Nocturnas": "Sí", # NO entra en pMayo parcial
    }
    pm = mayo_parcial(reg, PAC_CU)
    assert pm["score"] == 6, f"pMayo máximo debe ser 6, got {pm['score']}"
    assert "Estado general" not in pm["componentes"], \
        "Estado_General NO debe estar en pMayo parcial"
    print(f"✅ pMayo máximo = 6  ({pm['componentes']})")


def test_cu_pmayo_badge_coherencia():
    """Badge AMARILLO cuando pMayo indica actividad moderada (4-5)."""
    reg = {
        "Enfermedad": "CU",
        "Deposiciones_Numero": 4,   # +3 sobre basal=1 → si_frec=3
        "Sangre_Deposiciones": "Evidente",  # si_sangre=2 → pMayo=5 → moderado
        "Temperatura": 0,
        "Adherencia_Medicacion": "Sí, tomé todo",
        "Escala_Fatiga": 4,
    }
    pm = mayo_parcial(reg, PAC_CU)
    assert pm["score"] == 5, f"pMayo esperado 5, got {pm['score']}"
    assert pm["interpretacion"] == "Actividad moderada", pm["interpretacion"]

    r = triage(reg, PAC_CU)
    # pMayo=5 (moderado) → badge debe ser al menos AMARILLO, no VERDE
    assert r["nivel"] in ("AMARILLO", "ROJO"), \
        f"pMayo=5/moderado no puede ser VERDE, got {r['nivel']}"
    print(f"✅ pMayo 5/6 (Moderado) → badge {r['nivel']} (coherente)")


def test_cu_no_adherencia_no_verde():
    """No adherencia nunca puede ser VERDE."""
    reg = {
        "Enfermedad": "CU",
        "Deposiciones_Numero": 1,
        "Sangre_Deposiciones": "Ninguna",
        "Urgencia": "No",
        "Deposiciones_Nocturnas": "No",
        "Dolor_Abdominal": "Ninguno",
        "Estado_General": 0,
        "Escala_Fatiga": 2,
        "Frecuencia_Cardiaca": 70,
        "Temperatura": 0,
        "Adherencia_Medicacion": "No tomé la medicación",
    }
    r = triage(reg, PAC_CU)
    assert r["nivel"] != "VERDE", f"No adherencia no puede ser VERDE, got {r['nivel']}"
    print(f"✅ CU no adherencia → {r['nivel']} (nunca VERDE)")


# ─── Escenarios EC ────────────────────────────────────────────────────────────

def test_ec_remision():
    reg = {
        "Enfermedad": "EC",
        "Deposiciones_Numero": 2,
        "Sangre_Deposiciones": "Ninguna",
        "Dolor_Abdominal": "Ninguno",
        "Estado_General": 0,
        "Escala_Fatiga": 2,
        "Manif_Extraintestinales": "",
        "Adherencia_Medicacion": "Sí, tomé todo",
        "Temperatura": 0,
    }
    r = triage(reg, PAC_EC)
    assert r["nivel"] == "VERDE", f"EC remisión esperaba VERDE, got {r['nivel']}: {r['razones']}"
    print("✅ EC remisión → VERDE")


def test_ec_severo():
    """EC severo: HBI alto + fiebre absoluta + dolor severo. Temperatura en °C absolutos."""
    reg = {
        "Enfermedad": "EC",
        "Deposiciones_Numero": 10,
        "Sangre_Deposiciones": "Evidente",
        "Dolor_Abdominal": "Severo",
        "Estado_General": 3,
        "Escala_Fatiga": 9,
        "Manif_Extraintestinales": "artritis, fístula perianal",
        "Adherencia_Medicacion": "Sí, tomé todo",
        "Temperatura": 38.3,           # absoluto: 38.3°C ≥ T_rojo(37.8)
        "PCR_Sangre": 45,
    }
    r = triage(reg, PAC_EC)
    assert r["nivel"] == "ROJO", f"EC severo esperaba ROJO, got {r['nivel']}: {r['razones']}"
    print(f"✅ EC severo → ROJO  | Razones: {r['razones_rojo']}")


# ─── Tests de scores ──────────────────────────────────────────────────────────

def test_mayo_parcial_remision():
    """pMayo remisión: 1 dep (igual al basal) + sin sangre = 0."""
    reg = {
        "Enfermedad": "CU",
        "Deposiciones_Numero": 1,
        "Sangre_Deposiciones": "Ninguna",
    }
    r = mayo_parcial(reg, PAC_CU)
    assert r["score"] == 0, f"pMayo remisión esperaba 0, got {r['score']}"
    assert r["interpretacion"] == "Remisión", r["interpretacion"]
    assert "Estado general" not in r["componentes"], "Estado_General no debe estar en pMayo"
    print(f"✅ pMayo remisión → {r['score']} ({r['interpretacion']})")


def test_hbi_remision():
    reg = {
        "Enfermedad": "EC",
        "Deposiciones_Numero": 2,
        "Dolor_Abdominal": "Ninguno",
        "Estado_General": 0,
        "Manif_Extraintestinales": "",
    }
    r = hbi(reg, PAC_EC)
    assert r["score"] <= 4, f"HBI remisión esperaba ≤4, got {r['score']}"
    print(f"✅ HBI remisión → {r['score']} ({r['interpretacion']})")


def test_score_sin_datos():
    """score_sin_datos() devuelve tipo SIN_DATOS y score None."""
    s = score_sin_datos()
    assert s["tipo"] == "SIN_DATOS", s
    assert s["score"] is None, s
    print(f"✅ score_sin_datos() → tipo={s['tipo']}, score={s['score']}")


# ─── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n─── IBD Companion — Tests de Triage y Scores ───\n")
    tests = [
        test_cu_remision,
        test_cu_leve_moderado,
        test_cu_asuc,
        test_cu_pmayo_max_6,
        test_cu_pmayo_badge_coherencia,
        test_cu_no_adherencia_no_verde,
        test_ec_remision,
        test_ec_severo,
        test_mayo_parcial_remision,
        test_hbi_remision,
        test_score_sin_datos,
    ]
    errores = []
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"❌ {t.__name__}: {e}")
            errores.append(t.__name__)
        except Exception as e:
            print(f"💥 {t.__name__}: {type(e).__name__}: {e}")
            errores.append(t.__name__)

    print(f"\n─── Resultado: {len(tests) - len(errores)}/{len(tests)} tests pasaron ───")
    if errores:
        print(f"FALLARON: {errores}")
        sys.exit(1)
    else:
        print("✅ Todos los tests pasaron.\n")
