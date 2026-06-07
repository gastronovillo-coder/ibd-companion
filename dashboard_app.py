"""
dashboard_app.py — IBD Companion
================================
Visor del Equipo Médico.

Flujo:
  1. Login del equipo (PIN compartido o ID médico)
  2. Vista poblacional: tabla de pacientes ordenada por riesgo (ROJO arriba)
  3. Zoom de paciente: historia, tendencias, notas personales
  4. Panel de conducta: escalera proporcional al riesgo → registrar → notificar
  5. Auditoría: log de acciones del equipo

Correr con:
    streamlit run dashboard_app.py
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date

# ─── Config de página ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IBD Companion — Equipo Médico",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
header[data-testid="stHeader"] { display: none; }

/* Header principal */
.dash-header {
    background: linear-gradient(135deg, #1A237E 0%, #0D47A1 50%, #0288D1 100%);
    border-radius: 12px;
    padding: 1.2rem 2rem;
    color: white;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
}
.dash-header h1 { font-size: 1.6rem; margin: 0; font-weight: 700; }
.dash-header p  { margin: 0.2rem 0 0; opacity: 0.8; font-size: 0.9rem; }

/* Cards de KPI */
.kpi-card {
    background: white;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    border-top: 4px solid #1565C0;
}
.kpi-rojo   { border-top-color: #D32F2F; }
.kpi-amarillo{ border-top-color: #F57F17; }
.kpi-verde  { border-top-color: #2E7D32; }
.kpi-card .kpi-num { font-size: 2rem; font-weight: 700; margin: 0; }
.kpi-card .kpi-lbl { font-size: 0.82rem; color: #666; margin: 0; }

/* Fila de paciente en tabla */
.pac-rojo    { background-color: #FFEBEE !important; }
.pac-amarillo{ background-color: #FFF8E1 !important; }
.pac-verde   { background-color: #E8F5E9 !important; }

/* Badge de triage */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.82rem;
    color: white;
}
.badge-r { background: #D32F2F; }
.badge-a { background: #F57F17; }
.badge-v { background: #2E7D32; }
.badge-g { background: #757575; }

/* Panel lateral */
section[data-testid="stSidebar"] { background: #F8F9FA; }
</style>
""", unsafe_allow_html=True)


# ─── Imports core ─────────────────────────────────────────────────────────────
from core.triage import triage, nivel_ui
from core.scores import calcular_score
from core.audit import mostrar_panel_conducta, mostrar_log_acciones
from core.config import UMBRALES


# ─── Login equipo ─────────────────────────────────────────────────────────────

def pantalla_login_equipo():
    st.markdown("""
    <div class="dash-header">
        <div>
            <h1>🏥 IBD Companion</h1>
            <p>Panel del Equipo Médico</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_c, col_f = st.columns([1, 1])
    with col_c:
        st.markdown("### Acceso del equipo")
        id_medico = st.text_input("ID del médico / operador", placeholder="Ej: DR-GARCIA")
        pin = st.text_input("PIN de equipo", type="password")
        login_btn = st.button("Ingresar", type="primary", use_container_width=True)

        if login_btn:
            try:
                pin_correcto = st.secrets["app"]["team_pin"]
            except Exception:
                pin_correcto = "1234"

            if pin == pin_correcto and id_medico.strip():
                st.session_state["medico_auth"] = True
                st.session_state["id_medico"] = id_medico.strip().upper()
                st.rerun()
            else:
                st.error("PIN incorrecto o ID vacío.", icon="❌")

    with col_f:
        st.markdown("### Recordatorio")
        st.info(
            "Este panel está destinado **exclusivamente** al equipo de salud. "
            "Toda acción queda auditada.\n\n"
            "**IBD Companion** es apoyo a la decisión, no reemplaza el criterio clínico.",
            icon="ℹ️",
        )


# ─── Helpers de estado ────────────────────────────────────────────────────────

def _cargar_estado_poblacional() -> pd.DataFrame:
    """
    Construye la tabla de estado de todos los pacientes activos.
    Para cada paciente: último registro diario → triage + score.
    """
    from core.sheets import get_pacientes, get_registros
    from core.scores import score_sin_datos

    pacientes = get_pacientes(solo_activos=True)
    if pacientes.empty:
        return pd.DataFrame()

    filas = []
    for _, pac in pacientes.iterrows():
        id_pac = pac.get("ID_Paciente", "")
        registros = get_registros(id_paciente=id_pac)

        # Último registro diario
        reg_diario = registros[
            registros.get("Tipo_Registro", pd.Series(dtype=str)) == "diario"
        ] if "Tipo_Registro" in registros.columns else registros

        dias_sin_registro = None

        if not reg_diario.empty:
            # Hay registros → triage real
            ultimo = reg_diario.iloc[0].to_dict()
            ts = reg_diario.iloc[0].get("Timestamp")
            if pd.notna(ts):
                dias_sin_registro = (datetime.now() - pd.to_datetime(ts)).days

            resultado_triage = triage(ultimo, pac.to_dict())

            # Alerta de abandono solo cuando YA tuvo registros y dejó de reportar
            if dias_sin_registro is not None:
                if dias_sin_registro >= UMBRALES["dias_sin_registro_rojo"]:
                    resultado_triage["nivel"] = "ROJO"
                    resultado_triage["razones"] = resultado_triage.get("razones", []) + [
                        f"Sin registro hace {dias_sin_registro} días"
                    ]
                elif dias_sin_registro >= UMBRALES["dias_sin_registro_amarillo"]:
                    if resultado_triage["nivel"] == "VERDE":
                        resultado_triage["nivel"] = "AMARILLO"
                    resultado_triage["razones"] = resultado_triage.get("razones", []) + [
                        f"Sin registro hace {dias_sin_registro} días"
                    ]
        else:
            # Sin ningún registro → SIN_DATOS (gris), no ROJO
            dias_sin_registro = None  # no aplica el contador de días
            resultado_triage = {
                "nivel": "SIN_DATOS",
                "razones": ["Paciente sin registros aún"],
                "razones_rojo": [],
                "razones_amarillo": [],
                "score": score_sin_datos(),
            }

        score = resultado_triage.get("score", {})
        filas.append({
            "ID_Paciente": id_pac,
            "Nombre": pac.get("Nombre", "—"),
            "Enfermedad": pac.get("Enfermedad", "—"),
            "Triage": resultado_triage["nivel"],
            "Score_Tipo": score.get("tipo", "N/A"),
            "Score": score.get("score"),  # puede ser None para SIN_DATOS
            "Interpretacion": score.get("interpretacion", "—"),
            "Dias_Sin_Registro": dias_sin_registro,
            "Razones": " | ".join(resultado_triage.get("razones", [])),
            "_triage_obj": resultado_triage,
            "_pac_dict": pac.to_dict(),
        })

    df = pd.DataFrame(filas)
    if df.empty:
        return df

    # Ordenar: ROJO → AMARILLO → VERDE → SIN_DATOS
    orden = {"ROJO": 0, "AMARILLO": 1, "VERDE": 2, "SIN_DATOS": 3}
    df["_orden"] = df["Triage"].map(orden).fillna(3)
    df = df.sort_values(["_orden", "Score"], ascending=[True, False]).reset_index(drop=True)
    return df


def _badge(nivel: str) -> str:
    cls = {"ROJO": "badge-r", "AMARILLO": "badge-a", "VERDE": "badge-v", "SIN_DATOS": "badge-g"}.get(nivel, "badge-g")
    emoji = {"ROJO": "🔴", "AMARILLO": "🟡", "VERDE": "🟢", "SIN_DATOS": "⚪"}.get(nivel, "⚪")
    label = {"ROJO": "ROJO", "AMARILLO": "AMARILLO", "VERDE": "VERDE", "SIN_DATOS": "SIN DATOS"}.get(nivel, nivel)
    return f'<span class="badge {cls}">{emoji} {label}</span>'


# ─── Vista poblacional ────────────────────────────────────────────────────────

def vista_poblacional(id_medico: str):
    st.markdown("## 👥 Monitoreo Poblacional")

    with st.spinner("Cargando estado de pacientes…"):
        df = _cargar_estado_poblacional()

    if df.empty:
        st.info("No hay pacientes activos registrados.", icon="ℹ️")
        return

    # KPIs
    n_rojo     = len(df[df["Triage"] == "ROJO"])
    n_amarillo = len(df[df["Triage"] == "AMARILLO"])
    n_verde    = len(df[df["Triage"] == "VERDE"])
    n_sin      = len(df[df["Triage"] == "SIN_DATOS"])
    total      = len(df)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f"""
        <div class="kpi-card">
            <p class="kpi-num">{total}</p>
            <p class="kpi-lbl">Pacientes activos</p>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="kpi-card kpi-rojo">
            <p class="kpi-num" style="color:#D32F2F">{n_rojo}</p>
            <p class="kpi-lbl">🔴 Rojo</p>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="kpi-card kpi-amarillo">
            <p class="kpi-num" style="color:#F57F17">{n_amarillo}</p>
            <p class="kpi-lbl">🟡 Amarillo</p>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="kpi-card kpi-verde">
            <p class="kpi-num" style="color:#2E7D32">{n_verde}</p>
            <p class="kpi-lbl">🟢 Verde</p>
        </div>""", unsafe_allow_html=True)
    with c5:
        st.markdown(f"""
        <div class="kpi-card" style="border-top-color:#757575">
            <p class="kpi-num" style="color:#757575">{n_sin}</p>
            <p class="kpi-lbl">⚪ Sin datos</p>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Filtros
    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        filtro_nivel = st.multiselect(
            "Filtrar por nivel",
            options=["ROJO", "AMARILLO", "VERDE", "SIN_DATOS"],
            default=["ROJO", "AMARILLO", "VERDE", "SIN_DATOS"],
            format_func=lambda x: {"SIN_DATOS": "⚪ Sin datos"}.get(x, x),
        )
    with col_f2:
        buscar = st.text_input("Buscar paciente", placeholder="Nombre o ID…")

    df_filtrado = df[df["Triage"].isin(filtro_nivel)]
    if buscar:
        mask = (
            df_filtrado["Nombre"].str.lower().str.contains(buscar.lower(), na=False) |
            df_filtrado["ID_Paciente"].str.lower().str.contains(buscar.lower(), na=False)
        )
        df_filtrado = df_filtrado[mask]

    # Tabla de pacientes
    st.markdown(f"**{len(df_filtrado)} pacientes** (ordenados por riesgo)")

    for _, row in df_filtrado.iterrows():
        color_bg = {
            "ROJO": "#fff5f5", "AMARILLO": "#fffbf0", "VERDE": "#f0fff4"
        }.get(row["Triage"], "white")

        dias = row["Dias_Sin_Registro"]
        if row["Triage"] == "SIN_DATOS":
            dias_str = "Sin registros aún"
        elif dias is None:
            dias_str = "Hoy"
        elif dias == 0:
            dias_str = "Hoy"
        else:
            dias_str = f"{dias}d sin registro"

        with st.container():
            cols = st.columns([3, 1.5, 1.5, 1.5, 2])
            with cols[0]:
                st.markdown(
                    f"**{row['Nombre']}** `{row['ID_Paciente']}`  \n"
                    f"<small>{row['Enfermedad']} · {dias_str}</small>",
                    unsafe_allow_html=True,
                )
            with cols[1]:
                st.markdown(_badge(row["Triage"]), unsafe_allow_html=True)
        with cols[2]:
            if row["Triage"] == "SIN_DATOS" or row["Score"] is None:
                st.markdown("⚪ *Sin datos*")
                st.caption("Paciente no registra aún")
            else:
                st.markdown(f"**{row['Score_Tipo']}** {row['Score']}")
                st.caption(row["Interpretacion"])
            with cols[3]:
                primera_razon = row["Razones"].split(" | ")[0] if row["Razones"] else "—"
                st.caption(primera_razon[:60] + ("…" if len(primera_razon) > 60 else ""))
            with cols[4]:
                if st.button("Ver paciente", key=f"ver_{row['ID_Paciente']}", use_container_width=True):
                    st.session_state["zoom_paciente"] = row["ID_Paciente"]
                    st.session_state["vista"] = "zoom"
                    st.rerun()

            st.markdown("<hr style='margin:0.4rem 0; opacity:0.2'>", unsafe_allow_html=True)


# ─── Zoom de paciente ─────────────────────────────────────────────────────────

def vista_zoom_paciente(id_paciente: str, id_medico: str):
    import plotly.graph_objects as go
    from core.sheets import get_registros, get_paciente, get_acciones

    paciente = get_paciente(id_paciente)
    if not paciente:
        st.error(f"Paciente `{id_paciente}` no encontrado.", icon="❌")
        return

    nombre = paciente.get("Nombre", id_paciente)
    enf    = paciente.get("Enfermedad", "—")

    # Back
    if st.button("← Volver a la lista"):
        st.session_state["vista"] = "poblacional"
        st.session_state.pop("zoom_paciente", None)
        st.rerun()

    # Header del paciente
    registros = get_registros(id_paciente=id_paciente)
    reg_diario = registros[
        registros.get("Tipo_Registro", pd.Series(dtype=str)) == "diario"
    ] if "Tipo_Registro" in registros.columns else registros

    resultado_triage = {"nivel": "VERDE", "razones": ["Sin registros"], "score": {"score": 0, "tipo": "N/A", "interpretacion": "Sin datos"}}
    if not reg_diario.empty:
        ultimo = reg_diario.iloc[0].to_dict()
        resultado_triage = triage(ultimo, paciente)

    ui = nivel_ui(resultado_triage["nivel"])
    score = resultado_triage.get("score", {})

    st.markdown(f"""
    <div style="background:{ui['bg']}; border-left:5px solid {ui['color']};
                border-radius:8px; padding:1rem 1.5rem; margin-bottom:1rem;">
        <h2 style="margin:0; color:{ui['color']}">
            {ui['emoji']} {nombre} — <small>{enf}</small>
        </h2>
        <p style="margin:0.3rem 0 0; color:#555;">
            <strong>ID:</strong> {id_paciente} &nbsp;|&nbsp;
            <strong>{score.get('tipo','N/A')}:</strong> {score.get('score',0)} ({score.get('interpretacion','—')}) &nbsp;|&nbsp;
            <strong>Triage:</strong> {ui['label']}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Razones del triage
    if resultado_triage["razones"]:
        with st.expander("📋 Razones del triage", expanded=True):
            for r in resultado_triage.get("razones_rojo", []):
                st.error(f"🔴 {r}")
            for r in resultado_triage.get("razones_amarillo", []):
                st.warning(f"🟡 {r}")
            if resultado_triage["nivel"] == "VERDE":
                st.success(f"🟢 {resultado_triage['razones'][0]}")

    tabs = st.tabs(["📊 Tendencias", "📋 Historia", "📔 Notas", "🎯 Conducta", "📁 Auditoría"])

    # ── Tab: Tendencias ────────────────────────────────────────────────────
    with tabs[0]:
        if reg_diario.empty:
            st.info("Sin registros diarios aún.", icon="ℹ️")
        else:
            df_plot = reg_diario.sort_values("Timestamp")

            # Score histórico
            scores_hist = []
            for _, row in df_plot.iterrows():
                s = calcular_score(row.to_dict(), paciente)
                scores_hist.append({"Fecha": row["Timestamp"], "Score": s.get("score", 0)})
            scores_df = pd.DataFrame(scores_hist)

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=scores_df["Fecha"], y=scores_df["Score"],
                mode="lines+markers", name=score.get("tipo","Score"),
                line=dict(color=ui["color"], width=2.5),
            ))
            # Línea de umbral remisión
            umbral_rem = UMBRALES.get("mayo_remision" if enf == "CU" else "HBI_remision", 2)
            fig.add_hline(y=umbral_rem, line_dash="dot", line_color="green",
                          annotation_text=f"Umbral remisión ({umbral_rem})")
            fig.update_layout(title="Score clínico en el tiempo", height=280,
                              plot_bgcolor="white", paper_bgcolor="white",
                              margin=dict(l=0,r=0,t=40,b=0))
            st.plotly_chart(fig, use_container_width=True)

            # Deposiciones y fatiga
            fig2 = go.Figure()
            if "Deposiciones_Numero" in df_plot.columns:
                fig2.add_trace(go.Bar(
                    x=df_plot["Timestamp"],
                    y=pd.to_numeric(df_plot["Deposiciones_Numero"], errors="coerce"),
                    name="Deposiciones", marker_color="#90CAF9",
                ))
            if "Escala_Fatiga" in df_plot.columns:
                fig2.add_trace(go.Scatter(
                    x=df_plot["Timestamp"],
                    y=pd.to_numeric(df_plot["Escala_Fatiga"], errors="coerce"),
                    mode="lines+markers", name="Fatiga",
                    line=dict(color="#E91E63"), yaxis="y2",
                ))
            fig2.update_layout(
                title="Deposiciones / Fatiga", height=260,
                yaxis=dict(title="Deposiciones"),
                yaxis2=dict(title="Fatiga (1-10)", overlaying="y", side="right", range=[0,10]),
                plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(l=0,r=0,t=40,b=0), legend=dict(orientation="h"),
            )
            st.plotly_chart(fig2, use_container_width=True)

    # ── Tab: Historia ──────────────────────────────────────────────────────
    with tabs[1]:
        st.markdown("### Datos basales")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.markdown(f"**Diagnóstico:** {enf}")
            st.markdown(f"**Medicación:** {paciente.get('Medicacion_Actual','—')}")
            st.markdown(f"**Basal deposiciones:** {paciente.get('Basal_Deposiciones','—')} / día")
        with col_b2:
            st.markdown(f"**Email:** {paciente.get('Email','—')}")
            st.markdown(f"**Alta:** {paciente.get('Fecha_Alta','—')}")

        st.markdown("---")
        st.markdown("### Registros recientes")
        if not registros.empty:
            cols_mostrar = [c for c in [
                "Timestamp", "Tipo_Registro", "Deposiciones_Numero", "Sangre_Deposiciones",
                "Dolor_Abdominal", "Escala_Fatiga", "Adherencia_Medicacion",
                "Calprotectina_Fecal", "PCR_Sangre", "Hemoglobina",
            ] if c in registros.columns]
            st.dataframe(registros[cols_mostrar].head(30), use_container_width=True, hide_index=True)

    # ── Tab: Notas ─────────────────────────────────────────────────────────
    with tabs[2]:
        st.markdown("### Notas del paciente")
        notas_df = registros[
            registros["Notas_Paciente"].str.strip().str.len() > 0
        ] if "Notas_Paciente" in registros.columns else pd.DataFrame()

        if notas_df.empty:
            st.info("El paciente no ha dejado notas aún.", icon="ℹ️")
        else:
            for _, row in notas_df.head(20).iterrows():
                ts = row.get("Timestamp", "")
                if hasattr(ts, "strftime"):
                    ts = ts.strftime("%d/%m/%Y %H:%M")
                st.markdown(f"**{ts}** — {row.get('Notas_Paciente','')}")
                st.markdown("<hr style='opacity:0.2'>", unsafe_allow_html=True)

    # ── Tab: Conducta ──────────────────────────────────────────────────────
    with tabs[3]:
        mostrar_panel_conducta(id_medico, id_paciente, resultado_triage)

        # Opción de notificar por email
        if paciente.get("Email"):
            st.markdown("---")
            st.markdown("### Notificar al paciente por correo")
            from core.config import OPCIONES_CONDUCTA
            from core.mailer import notificar_conducta

            col_m1, col_m2 = st.columns([2, 1])
            with col_m1:
                tipo_mail = st.selectbox("Tipo de notificación", OPCIONES_CONDUCTA, key="mail_tipo")
                detalle_mail = st.text_input("Detalle adicional para el correo", key="mail_detalle")
            with col_m2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("📧 Enviar correo", use_container_width=True, key="enviar_mail"):
                    ok = notificar_conducta(
                        tipo_accion=tipo_mail,
                        email_paciente=paciente.get("Email",""),
                        nombre_paciente=nombre,
                        detalle=detalle_mail,
                    )
                    if ok:
                        st.success(f"Correo enviado a {paciente['Email']}", icon="📧")

    # ── Tab: Auditoría ─────────────────────────────────────────────────────
    with tabs[4]:
        st.markdown("### Acciones registradas para este paciente")
        mostrar_log_acciones(id_paciente=id_paciente)


# ─── Vista Auditoría global ───────────────────────────────────────────────────

def vista_auditoria():
    st.markdown("## 📁 Auditoría — Todas las acciones del equipo")
    mostrar_log_acciones()


# ─── Vista Alta de paciente ───────────────────────────────────────────────────

def vista_alta_paciente(id_medico: str):
    """Formulario para registrar un paciente nuevo. El PIN se guarda encriptado."""
    import re
    from core.sheets import append_paciente, get_paciente, get_pacientes
    from core.audit import registrar_accion

    st.markdown("## ➕ Alta de paciente")
    st.caption(
        "Registrá un paciente nuevo. El PIN se guarda **encriptado** automáticamente; "
        "nunca queda visible en la base de datos."
    )

    # ── Sugerencia automática del próximo ID (sin abrir el Sheet) ──
    df_pac = get_pacientes(solo_activos=False)
    ids_existentes = (
        [str(x) for x in df_pac["ID_Paciente"].tolist()]
        if (not df_pac.empty and "ID_Paciente" in df_pac.columns)
        else []
    )

    def _siguiente_id(ids: list[str]) -> str:
        maxn = 0
        for i in ids:
            nums = re.findall(r"\d+", i)
            if nums:
                maxn = max(maxn, int(nums[-1]))
        return f"PAC-{maxn + 1:03d}"

    sugerido = _siguiente_id(ids_existentes)
    st.markdown(
        f"**ID sugerido: `{sugerido}`** · Pacientes registrados: "
        f"{len(ids_existentes)} — no hace falta abrir el Sheet."
    )
    if ids_existentes:
        with st.expander(f"Ver IDs ya usados ({len(ids_existentes)})"):
            st.write(", ".join(sorted(ids_existentes)))

    with st.form("form_alta_paciente", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            id_pac = st.text_input(
                "ID del paciente *",
                value=sugerido,
                key=f"alta_id_{len(ids_existentes)}",
            )
            nombre = st.text_input("Nombre y apellido *", placeholder="Ej: Juan Pérez")
            email = st.text_input("Email", placeholder="opcional")
            fecha_nac = st.date_input(
                "Fecha de nacimiento",
                value=None,
                min_value=date(1900, 1, 1),
                max_value=date.today(),
                format="DD/MM/YYYY",
            )
        with c2:
            enfermedad = st.selectbox(
                "Enfermedad *",
                options=["CU — Colitis Ulcerosa", "EC — Enfermedad de Crohn"],
            )
            basal = st.number_input(
                "Deposiciones basales (en remisión)",
                min_value=0, max_value=20, value=1, step=1,
            )
            medicacion = st.text_input("Medicación actual", placeholder="opcional")
            pin = st.text_input(
                "PIN de acceso (4 dígitos) *", type="password", placeholder="Ej: 1234"
            )

        enviado = st.form_submit_button(
            "Registrar paciente", use_container_width=True, type="primary"
        )

    if not enviado:
        return

    # ── Normalización + validaciones ──
    id_pac = (id_pac or "").strip().upper()
    nombre = (nombre or "").strip()
    email = (email or "").strip()
    medicacion = (medicacion or "").strip()
    pin = (pin or "").strip()

    errores = []
    if not id_pac:
        errores.append("Falta el ID del paciente.")
    if not nombre:
        errores.append("Falta el nombre del paciente.")
    if not (pin.isdigit() and len(pin) == 4):
        errores.append("El PIN debe ser de 4 dígitos numéricos (ej: 1234).")
    if id_pac and get_paciente(id_pac):
        errores.append(f"Ya existe un paciente con ID {id_pac}. Elegí otro.")

    if errores:
        for e in errores:
            st.error(e, icon="❌")
        return

    enfermedad_cod = "CU" if enfermedad.startswith("CU") else "EC"

    nuevo = {
        "ID_Paciente": id_pac,
        "Nombre": nombre,
        "Email": email,
        "Fecha_Nacimiento": fecha_nac.isoformat() if fecha_nac else "",
        "Enfermedad": enfermedad_cod,
        "Basal_Deposiciones": str(int(basal)),
        "Medicacion_Actual": medicacion,
        "PIN": pin,  # append_paciente() lo encripta (hash SHA-256)
    }

    try:
        append_paciente(nuevo)
        registrar_accion(
            id_medico=id_medico,
            id_paciente=id_pac,
            tipo_accion="Alta de paciente",
            detalle=f"Alta de {nombre} ({enfermedad_cod})",
            resultado="Paciente registrado y activo",
        )
        st.success(f"Paciente {id_pac} registrado correctamente.", icon="✅")
        st.info(
            f"Pasale al paciente el **link de la app**, su **ID: {id_pac}** y su "
            f"**PIN: {pin}**.\n\n"
            "En su primer ingreso, la app le va a pedir aceptar el **consentimiento "
            "informado** antes de poder cargar datos.",
            icon="📋",
        )
    except Exception as e:
        st.error(f"No se pudo registrar el paciente: {e}", icon="❌")


# ─── Sidebar ──────────────────────────────────────────────────────────────────

def sidebar(id_medico: str):
    with st.sidebar:
        st.markdown(f"### 🏥 IBD Companion")
        st.markdown(f"**Usuario:** `{id_medico}`")
        st.markdown("---")

        vista = st.radio(
            "Navegación",
            options=["👥 Pacientes", "➕ Alta de paciente", "📁 Auditoría"],
            index=0,
        )

        st.markdown("---")
        st.markdown("""
        <div style="font-size:0.8rem; color:#999; margin-top:1rem;">
            <strong>IBD Companion</strong><br>
            Apoyo a la decisión clínica.<br>
            No reemplaza el juicio médico.<br><br>
            🚨 Emergencia: <strong>107</strong>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Cerrar sesión", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    return vista


# ─── App principal ────────────────────────────────────────────────────────────

def main():
    if "medico_auth" not in st.session_state:
        st.session_state["medico_auth"] = False

    if not st.session_state["medico_auth"]:
        pantalla_login_equipo()
        return

    id_medico = st.session_state["id_medico"]

    # Header
    ahora = datetime.now().strftime("%A %d/%m/%Y, %H:%M")
    st.markdown(f"""
    <div class="dash-header">
        <div style="font-size:2rem">🏥</div>
        <div>
            <h1>IBD Companion — Panel Médico</h1>
            <p>{ahora} · Operador: {id_medico}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar y navegación
    vista_sel = sidebar(id_medico)

    # Zoom de paciente: solo dentro de la sección Pacientes
    if (
        "Pacientes" in vista_sel
        and st.session_state.get("vista") == "zoom"
        and st.session_state.get("zoom_paciente")
    ):
        vista_zoom_paciente(st.session_state["zoom_paciente"], id_medico)
        return

    if "Pacientes" in vista_sel:
        st.session_state["vista"] = "poblacional"
        vista_poblacional(id_medico)
    elif "Alta" in vista_sel:
        st.session_state.pop("zoom_paciente", None)
        vista_alta_paciente(id_medico)
    elif "Auditoría" in vista_sel:
        st.session_state.pop("zoom_paciente", None)
        vista_auditoria()


if __name__ == "__main__":
    main()
