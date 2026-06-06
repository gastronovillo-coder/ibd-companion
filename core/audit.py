"""
core/audit.py — IBD Companion
================================
Registro de acciones del equipo médico (auditoría ALCOA+).

Cada acción queda registrada con:
  - Timestamp ISO (inmutable, generado en el momento)
  - ID del médico / operador
  - ID del paciente
  - Tipo de acción (escalera de conducta)
  - Detalle libre
  - Score y nivel de triage en ese momento

No hay borrado de registros de auditoría (ALCOA+: contemporáneo, atribuible, inmutable).
"""

from __future__ import annotations

import streamlit as st

from core.config import OPCIONES_CONDUCTA


def registrar_accion(
    id_medico: str,
    id_paciente: str,
    tipo_accion: str,
    detalle: str,
    score: int | float = 0,
    score_tipo: str = "",
    triage_nivel: str = "",
    resultado: str = "",
) -> None:
    """
    Registra una acción del equipo en la pestaña 'acciones'.

    Parámetros:
        id_medico      : identificador del médico / operador que ejecuta la acción.
        id_paciente    : ID del paciente involucrado.
        tipo_accion    : uno de OPCIONES_CONDUCTA (llamada, teleconsulta, etc.).
        detalle        : descripción libre de la acción tomada.
        score          : valor numérico del score en el momento de la acción.
        score_tipo     : tipo de score (pMayo, SCCAI, HBI).
        triage_nivel   : ROJO | AMARILLO | VERDE en el momento.
        resultado      : texto libre con el resultado o respuesta obtenida.
    """
    from core.sheets import append_accion

    append_accion({
        "ID_Medico": id_medico,
        "ID_Paciente": id_paciente,
        "Tipo_Accion": tipo_accion,
        "Detalle": detalle,
        "Score_Momento": str(score),
        "Score_Tipo": score_tipo,
        "Triage_Momento": triage_nivel,
        "Resultado": resultado,
    })


# ─── Componente UI de escalera de conducta ────────────────────────────────────

def mostrar_panel_conducta(
    id_medico: str,
    id_paciente: str,
    triage_resultado: dict,
) -> None:
    """
    Renderiza la escalera de conducta proporcional al riesgo en Streamlit.
    Permite al médico registrar la acción tomada con un detalle y resultado.
    """
    from core.triage import nivel_ui

    nivel = triage_resultado.get("nivel", "AMARILLO")
    ui = nivel_ui(nivel)
    score = triage_resultado.get("score", {})

    st.markdown(f"### {ui['emoji']} Conducta — Paciente `{id_paciente}`")
    st.markdown(
        f"**Nivel de riesgo actual:** :{ui['label']}:  |  "
        f"**Score:** {score.get('tipo','N/A')} = {score.get('score','-')} "
        f"({score.get('interpretacion','')})"
    )

    # Escalera proporcional al riesgo
    if nivel == "ROJO":
        opciones_sugeridas = OPCIONES_CONDUCTA[3:]   # Ajuste terapéutico → Guardia
        st.error(
            "🔴 **Nivel ROJO — Acción inmediata requerida.**\n\n"
            "Opciones sugeridas: Consulta presencial o Derivación a guardia.",
            icon="🚨",
        )
    elif nivel == "AMARILLO":
        opciones_sugeridas = OPCIONES_CONDUCTA[:4]   # Llamada → Solicitud estudios
        st.warning(
            "🟡 **Nivel AMARILLO — Evaluación y contacto en las próximas 24-48 h.**",
            icon="⚠️",
        )
    else:
        opciones_sugeridas = OPCIONES_CONDUCTA[:2]   # Llamada de seguimiento
        st.success(
            "🟢 **Nivel VERDE — Seguimiento de rutina.**",
            icon="✅",
        )

    st.markdown("---")

    with st.form(key=f"conducta_{id_paciente}_{nivel}"):
        tipo_accion = st.selectbox(
            "Tipo de acción",
            options=OPCIONES_CONDUCTA,
            index=OPCIONES_CONDUCTA.index(opciones_sugeridas[0])
            if opciones_sugeridas else 0,
        )
        detalle = st.text_area(
            "Detalle de la acción",
            placeholder="Describí qué acciones tomás / qué le indicás al paciente…",
            height=100,
        )
        resultado = st.text_area(
            "Resultado / respuesta (completar luego si aplica)",
            placeholder="¿Cómo respondió el paciente? ¿Qué pasó?",
            height=80,
        )
        enviar = st.form_submit_button("✅ Registrar conducta", type="primary")

    if enviar:
        if not detalle.strip():
            st.error("El campo 'Detalle' es obligatorio.", icon="❌")
            return

        registrar_accion(
            id_medico=id_medico,
            id_paciente=id_paciente,
            tipo_accion=tipo_accion,
            detalle=detalle,
            score=score.get("score", 0),
            score_tipo=score.get("tipo", ""),
            triage_nivel=nivel,
            resultado=resultado,
        )
        st.success(
            f"✅ Conducta registrada: **{tipo_accion}** para el paciente `{id_paciente}`.",
            icon="✅",
        )


# ─── Vista de auditoría ───────────────────────────────────────────────────────

def mostrar_log_acciones(id_paciente: str | None = None) -> None:
    """Muestra el log de acciones auditado en el dashboard."""
    import pandas as pd
    from core.sheets import get_acciones

    df = get_acciones(id_paciente=id_paciente)

    if df.empty:
        st.info("No hay acciones registradas aún.", icon="ℹ️")
        return

    st.markdown(f"**{len(df)} acciones registradas**")
    st.dataframe(
        df[[c for c in [
            "Timestamp", "ID_Medico", "Tipo_Accion", "Triage_Momento",
            "Score_Tipo", "Score_Momento", "Detalle", "Resultado"
        ] if c in df.columns]],
        use_container_width=True,
        hide_index=True,
    )
