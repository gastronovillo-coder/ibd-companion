"""
patient_app.py — IBD Companion
================================
Visor del Paciente — mobile-first.

Flujo:
  1. Login (ID Paciente + PIN)
  2. Check consentimiento → si no vigente, mostrar formulario y bloquear
  3. Menú: Registro Diario | Registro Periódico | Mis Notas | Mi Progreso
  4. Registro diario: formulario mobile-first con validaciones
  5. Registro periódico: laboratorio, endoscopía, SIBDQ
  6. Notas personales: diario libre
  7. Mi Progreso: gráficos de tendencia personales

Correr con:
    streamlit run patient_app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import datetime, date

# ─── Config de página (debe ir primero) ───────────────────────────────────────
st.set_page_config(
    page_title="IBD Companion — Mi Salud",
    page_icon="💙",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─── CSS Mobile-first ─────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Ocultar header de Streamlit */
header[data-testid="stHeader"] { display: none; }
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 680px; }

/* Card base */
.ibd-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    border: 1px solid #f0f0f0;
}

/* Header de la app */
.ibd-header {
    background: linear-gradient(135deg, #1565C0 0%, #0288D1 100%);
    border-radius: 16px;
    padding: 1.5rem;
    color: white;
    text-align: center;
    margin-bottom: 1.5rem;
}
.ibd-header h1 { font-size: 1.6rem; margin: 0; font-weight: 700; }
.ibd-header p  { margin: 0.3rem 0 0; opacity: 0.85; font-size: 0.95rem; }

/* Badge triage */
.badge-rojo    { background:#D32F2F; color:white; padding:4px 12px; border-radius:20px; font-weight:600; font-size:0.9rem; }
.badge-amarillo{ background:#F57F17; color:white; padding:4px 12px; border-radius:20px; font-weight:600; font-size:0.9rem; }
.badge-verde   { background:#2E7D32; color:white; padding:4px 12px; border-radius:20px; font-weight:600; font-size:0.9rem; }

/* Botones grandes (mobile) */
.stButton button { border-radius: 12px; padding: 0.6rem 1.2rem; font-weight: 600; }

/* Footer */
.ibd-footer { text-align:center; color:#999; font-size:0.78rem; margin-top:2rem; }

/* Tarjeta de alerta de emergencia */
.emergencia-card {
    background: #FFF3E0;
    border-left: 4px solid #E65100;
    border-radius: 8px;
    padding: 0.8rem 1rem;
    margin-bottom: 1rem;
    font-size: 0.88rem;
    color: #BF360C;
}
</style>
""", unsafe_allow_html=True)


# ─── Importaciones core ───────────────────────────────────────────────────────
from core.config import (
    OPCIONES_SANGRE, OPCIONES_DOLOR, OPCIONES_ESTADO_GENERAL,
    OPCIONES_ACTIVIDADES, OPCIONES_ADHERENCIA,
)
from core.consent import bloquear_sin_consentimiento
from core.triage import triage, nivel_ui

# ─── Utilidades ───────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _header(nombre: str = ""):
    st.markdown(f"""
    <div class="ibd-header">
        <h1>💙 IBD Companion</h1>
        <p>{"Hola, " + nombre + " 👋" if nombre else "Tu compañero de salud"}</p>
    </div>
    """, unsafe_allow_html=True)


def _footer():
    st.markdown("""
    <div class="ibd-footer">
        IBD Companion — Apoyo a la decisión clínica, NO diagnóstico.<br>
        Ante una emergencia llamá al <strong>107</strong> o acudí a guardia.
    </div>
    """, unsafe_allow_html=True)


def _emergencia_banner():
    st.markdown("""
    <div class="emergencia-card">
        ⚠️ <strong>¿Tenés una emergencia?</strong>
        Si tenés más de 6 deposiciones con sangre, fiebre alta o dolor intenso:
        llamá al <strong>107</strong> o acudí a guardia inmediatamente.
        Esta app NO reemplaza la atención de urgencia.
    </div>
    """, unsafe_allow_html=True)


# ─── Login ────────────────────────────────────────────────────────────────────

def pantalla_login():
    _header()
    st.markdown("### Ingresá a tu cuenta")

    with st.form("login_form"):
        id_pac = st.text_input("ID de paciente", placeholder="Ej: PAC-001")
        pin    = st.text_input("PIN", type="password", placeholder="4 dígitos")
        submit = st.form_submit_button("Ingresar", type="primary", use_container_width=True)

    if submit:
        if not id_pac or not pin:
            st.error("Completá tu ID y PIN.", icon="❌")
            return

        from core.sheets import verificar_pin, get_paciente
        if verificar_pin(id_pac.strip().upper(), pin.strip()):
            paciente = get_paciente(id_pac.strip().upper())
            st.session_state["autenticado"] = True
            st.session_state["id_paciente"] = id_pac.strip().upper()
            st.session_state["paciente"] = paciente or {}
            st.rerun()
        else:
            st.error("ID o PIN incorrecto. Verificá tus datos.", icon="❌")

    st.markdown("---")
    st.caption("¿Primera vez? Pedile a tu médico que te active en el sistema.")
    _footer()


# ─── Registro Diario ──────────────────────────────────────────────────────────

def pantalla_registro_diario(id_paciente: str, paciente: dict):
    enfermedad = paciente.get("Enfermedad", "CU")
    st.markdown("## 📝 Registro de hoy")
    _emergencia_banner()

    with st.form("registro_diario"):
        st.markdown("### ¿Cómo estuvo tu día?")

        dep = st.number_input(
            "¿Cuántas veces fuiste al baño hoy? (deposiciones totales)",
            min_value=0, max_value=30, value=0, step=1,
        )
        sangre = st.selectbox(
            "¿Hubo sangre en las deposiciones?",
            options=OPCIONES_SANGRE,
        )
        # Campo condicional: cuántas deposiciones con sangre
        dep_con_sangre = 0
        if sangre != "Ninguna":
            dep_max = max(int(dep), 1)
            dep_con_sangre = st.number_input(
                f"¿En cuántas de las {dep_max} deposiciones viste sangre?",
                min_value=0, max_value=dep_max, value=min(1, dep_max), step=1,
                help="Esto ayuda al equipo médico a evaluar la frecuencia del sangrado.",
            )
        urgencia = st.radio(
            "¿Tuviste urgencia para ir al baño (no podías esperar)?",
            options=["No", "Sí"], horizontal=True,
        )
        dep_noc = st.radio(
            "¿Te levantaste de noche para ir al baño?",
            options=["No", "Sí"], horizontal=True,
        )

        st.markdown("---")
        dolor = st.selectbox("¿Tuviste dolor abdominal?", options=OPCIONES_DOLOR)

        estado_opciones = list(OPCIONES_ESTADO_GENERAL.values())
        estado = st.select_slider(
            "¿Cómo te sentiste hoy en general?",
            options=estado_opciones,
        )
        estado_num = estado_opciones.index(estado)

        fatiga = st.slider(
            "Escala de fatiga (1 = sin fatiga, 10 = agotado/a)",
            min_value=1, max_value=10, value=3,
        )

        st.markdown("---")
        st.markdown("### Datos adicionales *(opcionales)*")
        fc = st.number_input("Frecuencia cardíaca (lpm, si la mediste)", min_value=0, max_value=200, value=0)
        temperatura = st.number_input(
            "Temperatura corporal (°C, si la mediste)",
            min_value=0.0, max_value=42.0, value=0.0, step=0.1,
            help="Ej: 38.5°C. Dejá en 0 si no te tomás la temperatura.",
        )
        actividades = st.selectbox("¿Cómo estuvieron tus actividades diarias?", options=OPCIONES_ACTIVIDADES)
        manif = st.text_input("¿Tuviste molestias en articulaciones, ojos o piel?", placeholder="Ej: dolor de rodilla, ojo rojo…")

        st.markdown("---")
        adherencia = st.selectbox("¿Tomaste tu medicación hoy?", options=OPCIONES_ADHERENCIA)
        notas = st.text_area(
            "Notas personales (lo que quieras registrar)",
            placeholder="¿Comiste algo diferente? ¿Tuviste estrés? ¿Algo que quieras contarle a tu médico?",
            height=100,
        )

        enviar = st.form_submit_button("✅ Guardar registro", type="primary", use_container_width=True)

    if enviar:
        registro = {
            "ID_Paciente": id_paciente,
            "Timestamp": _ts(),
            "Enfermedad": enfermedad,
            "Deposiciones_Numero": dep,
            "Sangre_Deposiciones": sangre,
            "Deposiciones_con_Sangre": dep_con_sangre if sangre != "Ninguna" else 0,
            "Urgencia": urgencia,
            "Deposiciones_Nocturnas": dep_noc,
            "Dolor_Abdominal": dolor,
            "Estado_General": estado_num,
            "Escala_Fatiga": fatiga,
            "Frecuencia_Cardiaca": fc if fc > 0 else "",
            "Temperatura": temperatura if temperatura >= 35 else "",
            "Actividades_Diarias": actividades,
            "Manif_Extraintestinales": manif,
            "Adherencia_Medicacion": adherencia,
            "Notas_Paciente": notas,
            "Tipo_Registro": "diario",
        }
        try:
            from core.sheets import append_registro
            append_registro(registro)

            # Calcular triage en tiempo real y mostrar al paciente
            resultado = triage(registro, paciente)
            nivel = resultado["nivel"]
            ui = nivel_ui(nivel)

            st.success("✅ Registro guardado correctamente.", icon="✅")

            if nivel == "ROJO":
                st.error(
                    "🔴 **Tu registro de hoy genera una alerta.**\n\n"
                    "Tu equipo médico será notificado. Si te sentís muy mal, "
                    "no esperes: acudí a guardia o llamá al **107**.",
                    icon="🚨",
                )
            elif nivel == "AMARILLO":
                st.warning(
                    "🟡 Tu equipo médico puede comunicarse con vos en las próximas horas.",
                    icon="⚠️",
                )
            else:
                st.success("🟢 ¡Todo bien! Seguí así.", icon="🟢")

        except Exception as e:
            st.error(f"Error al guardar: {e}", icon="❌")


# ─── Registro Periódico ───────────────────────────────────────────────────────

def pantalla_registro_periodico(id_paciente: str, paciente: dict):
    enfermedad = paciente.get("Enfermedad", "CU")
    st.markdown("## 🧪 Estudios y datos periódicos")
    st.info(
        "Completá este formulario cuando tengas resultados nuevos de laboratorio, "
        "endoscopía o imágenes. No es diario.",
        icon="ℹ️",
    )

    with st.form("registro_periodico"):
        st.markdown("### Laboratorio")
        calpro = st.number_input("Calprotectina fecal (µg/g)", min_value=0.0, value=0.0, step=1.0,
                                 help="Dejá en 0 si no tenés el resultado")
        pcr    = st.number_input("PCR en sangre (mg/L)", min_value=0.0, value=0.0, step=0.1)
        hb     = st.number_input("Hemoglobina (g/dL)", min_value=0.0, value=0.0, step=0.1)
        alb    = st.number_input("Albúmina (g/dL)", min_value=0.0, value=0.0, step=0.1)
        peso   = st.number_input("Peso actual (kg)", min_value=0.0, value=0.0, step=0.5)

        st.markdown("### Estudios")
        endoscopia = st.text_area("Resultado de endoscopía / colonoscopía", height=80,
                                  placeholder="Ej: mucosa granular leve en colon izquierdo…")
        imagen     = st.text_area("Resultado de imágenes (Rx, eco, RMN, TC)", height=80)

        st.markdown("### Medicación y bienestar")
        cambio_med = st.text_area("¿Hubo algún cambio en tu medicación?", height=60)
        sibdq      = st.slider("SIBDQ — Calidad de vida (10=muy malo, 70=excelente)",
                               min_value=10, max_value=70, value=40,
                               help="Short Inflammatory Bowel Disease Questionnaire")
        evento_adv = st.text_area("Eventos adversos / efectos secundarios", height=60)
        notas      = st.text_area("Notas adicionales", height=80)

        enviar = st.form_submit_button("✅ Guardar estudios", type="primary", use_container_width=True)

    if enviar:
        registro = {
            "ID_Paciente": id_paciente,
            "Timestamp": _ts(),
            "Enfermedad": enfermedad,
            "Calprotectina_Fecal": calpro if calpro > 0 else "",
            "PCR_Sangre": pcr if pcr > 0 else "",
            "Hemoglobina": hb if hb > 0 else "",
            "Albumina": alb if alb > 0 else "",
            "Peso": peso if peso > 0 else "",
            "Endoscopia_Resultado": endoscopia,
            "Imagen_Resultado": imagen,
            "Cambio_Medicacion": cambio_med,
            "SIBDQ": sibdq,
            "Evento_Adverso": evento_adv,
            "Notas_Paciente": notas,
            "Tipo_Registro": "periodico",
        }
        try:
            from core.sheets import append_registro
            append_registro(registro)
            st.success("✅ Estudios guardados correctamente.", icon="✅")
        except Exception as e:
            st.error(f"Error al guardar: {e}", icon="❌")


# ─── Notas personales ─────────────────────────────────────────────────────────

def pantalla_notas(id_paciente: str, paciente: dict):
    st.markdown("## 📔 Mis notas personales")
    st.info(
        "Escribí cualquier cosa que quieras registrar: gatillos, emociones, "
        "alimentos, objetivos personales. Tu equipo puede verlo en el seguimiento.",
        icon="💡",
    )

    with st.form("registro_nota"):
        notas = st.text_area(
            "¿Qué querés escribir hoy?",
            placeholder="Hoy comí picante y… / Me siento ansioso por… / Mi objetivo esta semana es…",
            height=200,
        )
        enviar = st.form_submit_button("💾 Guardar nota", type="primary", use_container_width=True)

    if enviar and notas.strip():
        registro = {
            "ID_Paciente": id_paciente,
            "Timestamp": _ts(),
            "Enfermedad": paciente.get("Enfermedad", ""),
            "Notas_Paciente": notas,
            "Tipo_Registro": "nota",
        }
        try:
            from core.sheets import append_registro
            append_registro(registro)
            st.success("✅ Nota guardada.", icon="✅")
        except Exception as e:
            st.error(f"Error al guardar: {e}", icon="❌")

    # Mostrar notas anteriores
    st.markdown("---")
    st.markdown("### Mis notas anteriores")
    try:
        from core.sheets import get_registros
        df = get_registros(id_paciente=id_paciente)
        if df.empty:
            st.caption("Todavía no hay notas registradas.")
        else:
            # Filtrar solo registros de tipo nota con texto
            if "Tipo_Registro" in df.columns:
                mask = (df["Tipo_Registro"] == "nota")
            else:
                mask = pd.Series([True] * len(df), index=df.index)
            if "Notas_Paciente" in df.columns:
                mask = mask & (df["Notas_Paciente"].fillna("").str.strip() != "")
            notas_filtradas = df[mask]
            if notas_filtradas.empty:
                st.caption("Todavía no hay notas registradas.")
            else:
                for _, row in notas_filtradas.head(10).iterrows():
                    fecha = row.get("Timestamp", "")
                    if hasattr(fecha, "strftime"):
                        fecha = fecha.strftime("%d/%m/%Y %H:%M")
                    st.markdown(f"**{fecha}** — {row.get('Notas_Paciente', '')}")
                    st.markdown("---")
    except Exception:
        st.caption("No se pudieron cargar las notas anteriores.")


# ─── Mi Progreso ─────────────────────────────────────────────────────────────

def pantalla_progreso(id_paciente: str, paciente: dict):
    import plotly.graph_objects as go

    st.markdown("## 📈 Mi Progreso")

    try:
        from core.sheets import get_registros
        from core.scores import calcular_score

        df = get_registros(id_paciente=id_paciente)
        df_diario = df[df.get("Tipo_Registro", pd.Series(dtype=str)) == "diario"] if "Tipo_Registro" in df.columns else df
        df_diario = df_diario.dropna(subset=["Timestamp"]).sort_values("Timestamp")

        if df_diario.empty:
            st.info("Aún no hay registros diarios. ¡Empezá hoy!", icon="ℹ️")
            return

        # Calcular scores históricos
        scores = []
        for _, row in df_diario.iterrows():
            s = calcular_score(row.to_dict(), paciente)
            scores.append({
                "Fecha": row["Timestamp"],
                "Score": s.get("score", 0),
                "Tipo": s.get("tipo", "N/A"),
                "Deposiciones": row.get("Deposiciones_Numero", 0),
                "Fatiga": row.get("Escala_Fatiga", 0),
            })

        scores_df = pd.DataFrame(scores)

        tipo_score = scores_df["Tipo"].iloc[-1] if not scores_df.empty else "Score"

        # Gráfico de score
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=scores_df["Fecha"], y=scores_df["Score"],
            mode="lines+markers", name=tipo_score,
            line=dict(color="#1565C0", width=2),
            marker=dict(size=6),
        ))
        fig.update_layout(
            title=f"Evolución {tipo_score}",
            xaxis_title="Fecha", yaxis_title="Score",
            height=300, margin=dict(l=0,r=0,t=40,b=0),
            plot_bgcolor="white", paper_bgcolor="white",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Gráfico de deposiciones y fatiga
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=scores_df["Fecha"], y=scores_df["Deposiciones"],
            name="Deposiciones", marker_color="#90CAF9", opacity=0.8,
        ))
        fig2.add_trace(go.Scatter(
            x=scores_df["Fecha"], y=scores_df["Fatiga"],
            mode="lines+markers", name="Fatiga",
            line=dict(color="#E91E63", width=2), yaxis="y2",
        ))
        fig2.update_layout(
            title="Deposiciones y Fatiga",
            yaxis=dict(title="Deposiciones"),
            yaxis2=dict(title="Fatiga (1-10)", overlaying="y", side="right", range=[0, 10]),
            height=300, margin=dict(l=0,r=0,t=40,b=0),
            plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(orientation="h"),
        )
        st.plotly_chart(fig2, use_container_width=True)

        # Último triage
        ultimo = df_diario.iloc[-1].to_dict()
        from core.triage import triage, nivel_ui
        resultado = triage(ultimo, paciente)
        ui = nivel_ui(resultado["nivel"])
        st.markdown(f"**Estado actual:** {ui['emoji']} {ui['label']}")

    except Exception as e:
        st.error(f"Error cargando progreso: {e}", icon="❌")


# ─── App principal ────────────────────────────────────────────────────────────

def main():
    # Estado de sesión
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    # Login
    if not st.session_state["autenticado"]:
        pantalla_login()
        return

    id_paciente = st.session_state["id_paciente"]
    paciente    = st.session_state.get("paciente", {})
    nombre      = paciente.get("Nombre", id_paciente)

    # Verificar consentimiento (bloquea si no está vigente)
    if not bloquear_sin_consentimiento(id_paciente):
        _header(nombre)
        _footer()
        return

    # Header
    _header(nombre)

    # Navegación
    tabs = st.tabs(["📝 Hoy", "🧪 Estudios", "📔 Notas", "📈 Progreso", "⚙️ Mi cuenta"])

    with tabs[0]:
        pantalla_registro_diario(id_paciente, paciente)

    with tabs[1]:
        pantalla_registro_periodico(id_paciente, paciente)

    with tabs[2]:
        pantalla_notas(id_paciente, paciente)

    with tabs[3]:
        pantalla_progreso(id_paciente, paciente)

    with tabs[4]:
        st.markdown("## ⚙️ Mi cuenta")
        enf = paciente.get("Enfermedad", "—")
        med = paciente.get("Medicacion_Actual", "—")
        st.markdown(f"**Paciente:** {nombre}  |  **ID:** `{id_paciente}`")
        st.markdown(f"**Diagnóstico:** {enf}  |  **Medicación:** {med}")
        st.markdown("---")

        # Revocar consentimiento
        with st.expander("⚠️ Revocar consentimiento informado"):
            st.warning(
                "Si revocás el consentimiento, no podrás cargar nuevos datos hasta "
                "que lo vuelvas a aceptar. Los datos ya cargados se conservan.",
            )
            confirmar_revoc = st.checkbox("Entendí las consecuencias, quiero revocar")
            if st.button("Revocar consentimiento", disabled=not confirmar_revoc):
                from core.consent import revocar_consentimiento
                revocar_consentimiento(id_paciente)
                st.success("Consentimiento revocado. Para cargar datos nuevamente, deberás aceptarlo otra vez.")
                st.rerun()

        if st.button("Cerrar sesión", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    _footer()


if __name__ == "__main__":
    main()
