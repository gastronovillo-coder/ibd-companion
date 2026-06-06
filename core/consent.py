"""
core/consent.py — IBD Companion
================================
Gestión del consentimiento informado electrónico (e-consent).

Reglas:
  - El e-consent es obligatorio antes de cargar cualquier dato clínico.
  - Si no hay consentimiento vigente, la carga queda bloqueada.
  - El re-consentimiento se dispara automáticamente si la versión del formulario cambió.
  - Los eventos de consentimiento / revocación se registran en la pestaña `consentimientos`.
  - Sin borrado: si el paciente revoca, se agrega una fila con Estado=Revocado.

Texto del consentimiento:
  Se carga desde TEXTO_CONSENTIMIENTO (abajo). En producción, incluir el texto
  completo aprobado por el CEI (Comité de Ética en Investigación) correspondiente.
"""

from __future__ import annotations

import streamlit as st

from core.config import CONSENT_FECHA_FALLBACK, CONSENT_VERSION_FALLBACK

# ─── Texto del consentimiento ─────────────────────────────────────────────────
# Reemplazar por el texto aprobado por el CEI antes de uso clínico real.

TEXTO_CONSENTIMIENTO = """
## Consentimiento Informado — IBD Companion

**Sistema de Telemonitoreo en Enfermedad Inflamatoria Intestinal (EII)**

Este sistema tiene como finalidad **apoyar el seguimiento de su enfermedad** entre las visitas
presenciales. No reemplaza la atención médica ni el criterio de su médico tratante.

**¿Qué datos se recopilan?**
Síntomas diarios (deposiciones, dolor, fatiga), datos de laboratorio y estudios cuando estén
disponibles, y notas personales que usted decida registrar.

**¿Cómo se usan?**
Su equipo médico accede a estos datos para detectar señales de actividad de la enfermedad y
contactarlo antes de una recaída. Los datos son confidenciales y no se comparten con terceros
sin su autorización expresa.

**Marco legal (Argentina):**
- Ley 25.326 — Protección de Datos Personales (datos sensibles de salud)
- Ley 26.529 — Derechos del Paciente y Consentimiento Informado
- Ley 27.553 — Teleasistencia en Salud

**Sus derechos:**
Puede revocar este consentimiento en cualquier momento desde la sección "Mi Perfil" de la app.
La revocación impide nuevas cargas pero no borra los datos ya registrados, que se conservan
con fines de continuidad asistencial.

**Este sistema es apoyo a la decisión, NO diagnóstico.**
Ante cualquier emergencia, concurra a guardia o llame al 107.
""".strip()


# ─── Helpers internos ─────────────────────────────────────────────────────────

def _version_vigente() -> str:
    """Lee la versión de consentimiento vigente desde st.secrets, con fallback."""
    try:
        return st.secrets["app"]["consent_version"]
    except Exception:
        return CONSENT_VERSION_FALLBACK


def _fecha_vigente() -> str:
    try:
        return st.secrets["app"]["consent_fecha"]
    except Exception:
        return CONSENT_FECHA_FALLBACK


# ─── Verificación de consentimiento ──────────────────────────────────────────

def tiene_consentimiento_vigente(id_paciente: str) -> bool:
    """
    Retorna True si el paciente tiene un consentimiento activo para la versión actual.
    Importa sheets en runtime para evitar import circular durante tests.
    """
    from core.sheets import get_consentimientos

    df = get_consentimientos(id_paciente=id_paciente)
    if df.empty:
        return False

    version_actual = _version_vigente()
    vigentes = df[
        (df["Estado"].str.lower() == "vigente") &
        (df["Version"] == version_actual)
    ]
    return not vigentes.empty


def necesita_reconsentimiento(id_paciente: str) -> bool:
    """
    Retorna True si el paciente tiene consentimiento pero de una versión anterior.
    """
    from core.sheets import get_consentimientos

    df = get_consentimientos(id_paciente=id_paciente)
    if df.empty:
        return False

    version_actual = _version_vigente()
    # Tiene algún vigente pero no de la versión actual
    tiene_vigente = not df[df["Estado"].str.lower() == "vigente"].empty
    tiene_version_actual = not df[
        (df["Estado"].str.lower() == "vigente") &
        (df["Version"] == version_actual)
    ].empty

    return tiene_vigente and not tiene_version_actual


# ─── Registro de consentimiento ──────────────────────────────────────────────

def registrar_consentimiento(id_paciente: str, ip: str = "") -> None:
    """Registra un nuevo consentimiento vigente en el Sheet."""
    from core.sheets import append_consentimiento

    append_consentimiento({
        "ID_Paciente": id_paciente,
        "Version": _version_vigente(),
        "Estado": "Vigente",
        "Medio": "App",
        "IP": ip,
    })


def revocar_consentimiento(id_paciente: str, ip: str = "") -> None:
    """Registra la revocación del consentimiento (baja lógica)."""
    from core.sheets import append_consentimiento

    append_consentimiento({
        "ID_Paciente": id_paciente,
        "Version": _version_vigente(),
        "Estado": "Revocado",
        "Medio": "App",
        "IP": ip,
    })


# ─── Componente UI de consentimiento ─────────────────────────────────────────

def mostrar_formulario_consentimiento(id_paciente: str, es_reconsentimiento: bool = False) -> bool:
    """
    Muestra el formulario de consentimiento en Streamlit.
    Retorna True si el paciente dio el consentimiento en esta sesión.
    """
    if es_reconsentimiento:
        st.warning(
            "⚠️ **El formulario de consentimiento fue actualizado.** "
            "Para continuar usando la app, necesitás revisar y aceptar la nueva versión.",
            icon="⚠️",
        )
    else:
        st.info(
            "Antes de comenzar, necesitás leer y aceptar el consentimiento informado.",
            icon="ℹ️",
        )

    version = _version_vigente()
    fecha = _fecha_vigente()

    with st.expander(f"📄 Leer consentimiento informado ({version} — {fecha})", expanded=True):
        st.markdown(TEXTO_CONSENTIMIENTO)

    st.markdown("---")

    col1, col2 = st.columns([3, 1])
    with col1:
        acepta = st.checkbox(
            "✅ Leí y acepto el consentimiento informado. "
            "Entiendo que puedo revocar mi consentimiento en cualquier momento.",
            key="checkbox_consentimiento",
        )
    with col2:
        confirmar = st.button("Confirmar", type="primary", use_container_width=True)

    if confirmar and acepta:
        registrar_consentimiento(id_paciente)
        st.success(
            "✅ Consentimiento registrado correctamente. "
            "Ya podés comenzar a usar la app.",
            icon="✅",
        )
        st.balloons()
        return True
    elif confirmar and not acepta:
        st.error("Necesitás marcar la casilla para continuar.", icon="❌")

    return False


def bloquear_sin_consentimiento(id_paciente: str) -> bool:
    """
    Verifica el consentimiento y muestra el formulario si no está vigente.
    Retorna True si el paciente puede continuar (tiene consentimiento vigente).
    Debe llamarse al inicio del flujo de carga de datos.
    """
    if tiene_consentimiento_vigente(id_paciente):
        return True

    es_reconsentimiento = necesita_reconsentimiento(id_paciente)
    consentido = mostrar_formulario_consentimiento(id_paciente, es_reconsentimiento)

    if consentido:
        st.rerun()

    return False
