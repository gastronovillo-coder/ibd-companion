"""
core/mailer.py — IBD Companion
================================
Envío de correos SMTP al paciente y/o al equipo médico.

Plantillas disponibles:
  - conducta_llamada
  - conducta_teleconsulta
  - conducta_estudios
  - conducta_ajuste
  - conducta_presencial
  - conducta_guardia
  - alerta_equipo (notificación interna de ROJO)

Credenciales: leídas desde st.secrets["smtp"].
"""

from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import streamlit as st


# ─── Plantillas ───────────────────────────────────────────────────────────────

_PLANTILLAS: dict[str, dict[str, str]] = {
    "conducta_llamada": {
        "asunto": "IBD Companion — Tu médico intentará contactarte",
        "cuerpo": """\
Hola {nombre},

Tu equipo médico intentará comunicarse con vos por teléfono en las próximas horas.

Si antes de que te llamemos notás un empeoramiento importante de tus síntomas
(más de 6 deposiciones con sangre, fiebre, dolor abdominal intenso), por favor
acudí a guardia o llamá al 107.

Saludos,
{equipo}
""",
    },
    "conducta_teleconsulta": {
        "asunto": "IBD Companion — Teleconsulta programada",
        "cuerpo": """\
Hola {nombre},

Tu médico tratante desea coordinar una teleconsulta con vos.
Por favor respondé este correo o comunicarte al {contacto} para confirmar el horario.

Si antes de la teleconsulta notás un empeoramiento importante de tus síntomas,
por favor acudí a guardia o llamá al 107.

Saludos,
{equipo}
""",
    },
    "conducta_estudios": {
        "asunto": "IBD Companion — Solicitud de estudios",
        "cuerpo": """\
Hola {nombre},

Tu equipo médico consideró necesario solicitar algunos estudios complementarios.
Los detalles son:

{detalle}

Por favor comunicarte al {contacto} para coordinar cómo obtenerlos.

Saludos,
{equipo}
""",
    },
    "conducta_ajuste": {
        "asunto": "IBD Companion — Ajuste de medicación",
        "cuerpo": """\
Hola {nombre},

Tu médico tratante realizó un ajuste en tu medicación. Por favor leé con atención:

{detalle}

Ante cualquier duda o efecto adverso, comunicarte al {contacto}.

Saludos,
{equipo}
""",
    },
    "conducta_presencial": {
        "asunto": "IBD Companion — Consulta presencial requerida",
        "cuerpo": """\
Hola {nombre},

Tu equipo médico necesita verte en consulta presencial.
Por favor comunicarte al {contacto} para coordinar un turno a la brevedad.

Si antes de la consulta notás un empeoramiento importante, acudí a guardia o llamá al 107.

Saludos,
{equipo}
""",
    },
    "conducta_guardia": {
        "asunto": "⚠️ IBD Companion — Acudí a guardia",
        "cuerpo": """\
Hola {nombre},

Basándonos en tu último registro, tu equipo médico recomienda que te dirijas a guardia
con URGENCIA.

Por favor llevá tu historial de medicación y mostrá este correo si es posible.

Número de emergencias: 107

Saludos,
{equipo}
""",
    },
    "alerta_equipo": {
        "asunto": "🔴 IBD Companion — ALERTA: Paciente {id_paciente} requiere atención",
        "cuerpo": """\
ALERTA DE TRIAGE — IBD Companion

Paciente: {nombre} (ID: {id_paciente})
Nivel: 🔴 ROJO
Score: {score_tipo} = {score}

Razones:
{razones}

Por favor ingresar al dashboard para ver el detalle y registrar la conducta.
""",
    },
}


# ─── Envío de correo ──────────────────────────────────────────────────────────

def _get_smtp_config() -> dict:
    """Lee la config SMTP desde st.secrets."""
    try:
        return {
            "host": st.secrets["smtp"]["host"],
            "port": int(st.secrets["smtp"]["port"]),
            "user": st.secrets["smtp"]["user"],
            "password": st.secrets["smtp"]["password"],
            "from_name": st.secrets["smtp"].get("from_name", "IBD Companion"),
        }
    except Exception as e:
        raise RuntimeError(f"Configuración SMTP no encontrada en secrets: {e}") from e


def enviar_correo(
    destinatario: str,
    asunto: str,
    cuerpo: str,
    html: bool = False,
) -> bool:
    """
    Envía un correo vía SMTP TLS.

    Retorna True si el envío fue exitoso, False si falló.
    Los errores se muestran como st.error (no se relanza la excepción
    para no romper el flujo de la app).
    """
    try:
        cfg = _get_smtp_config()
        msg = MIMEMultipart("alternative")
        msg["Subject"] = asunto
        msg["From"] = f'{cfg["from_name"]} <{cfg["user"]}>'
        msg["To"] = destinatario

        part = MIMEText(cuerpo, "html" if html else "plain", "utf-8")
        msg.attach(part)

        context = ssl.create_default_context()
        with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["user"], destinatario, msg.as_string())

        return True

    except Exception as exc:
        st.error(f"Error al enviar correo a {destinatario}: {exc}", icon="📧")
        return False


# ─── Funciones de conducta ────────────────────────────────────────────────────

def _plantilla(
    clave: str,
    nombre: str = "",
    id_paciente: str = "",
    detalle: str = "",
    score_tipo: str = "",
    score: int | float = 0,
    razones: list[str] | None = None,
    contacto: str = "",
    equipo: str = "Tu equipo de salud",
) -> tuple[str, str]:
    """Retorna (asunto, cuerpo) rellenados con los parámetros."""
    p = _PLANTILLAS[clave]
    razones_str = "\n".join(f"  • {r}" for r in (razones or []))
    asunto = p["asunto"].format(
        nombre=nombre, id_paciente=id_paciente,
        score_tipo=score_tipo, score=score,
    )
    cuerpo = p["cuerpo"].format(
        nombre=nombre, id_paciente=id_paciente,
        detalle=detalle, score_tipo=score_tipo,
        score=score, razones=razones_str,
        contacto=contacto, equipo=equipo,
    )
    return asunto, cuerpo


def notificar_conducta(
    tipo_accion: str,
    email_paciente: str,
    nombre_paciente: str,
    detalle: str = "",
    contacto: str = "",
    equipo: str = "Tu equipo de salud",
) -> bool:
    """Envía la notificación de conducta al paciente."""
    clave_map = {
        "Llamada telefónica":   "conducta_llamada",
        "Teleconsulta":         "conducta_teleconsulta",
        "Solicitud de estudios":"conducta_estudios",
        "Ajuste terapéutico":   "conducta_ajuste",
        "Consulta presencial":  "conducta_presencial",
        "Derivación a guardia": "conducta_guardia",
    }
    clave = clave_map.get(tipo_accion, "conducta_llamada")
    asunto, cuerpo = _plantilla(
        clave, nombre=nombre_paciente, detalle=detalle,
        contacto=contacto, equipo=equipo,
    )
    return enviar_correo(email_paciente, asunto, cuerpo)


def alerta_equipo(
    email_equipo: str,
    nombre_paciente: str,
    id_paciente: str,
    score_tipo: str,
    score: int | float,
    razones: list[str],
) -> bool:
    """Envía alerta interna al equipo médico cuando el triage es ROJO."""
    asunto, cuerpo = _plantilla(
        "alerta_equipo",
        nombre=nombre_paciente,
        id_paciente=id_paciente,
        score_tipo=score_tipo,
        score=score,
        razones=razones,
    )
    return enviar_correo(email_equipo, asunto, cuerpo)
