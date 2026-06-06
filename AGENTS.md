# IBD Companion — Contexto del proyecto (para el agente)

> Dejá este archivo en la **raíz del repositorio**. Antigravity lo lee como contexto.
> La especificación clínica/regulatoria completa está en `IBD_Companion_Especificacion.docx`.
> **Aclaración:** Antigravity es el IDE; la app se construye con **Streamlit + Google Sheets**
> (base de código `ibd_telemonitor`).

## Qué es
Sistema de **telemonitoreo en Enfermedad Inflamatoria Intestinal (EII)** — colitis ulcerosa (CU)
y enfermedad de Crohn (EC). Modelo: **treat-to-target continuo (STRIDE-II)**. De la consulta
reactiva al monitoreo continuo: el paciente reporta datos breves, una capa de IA detecta señales
tempranas y el equipo interviene **antes** de la recaída.

**Es apoyo a la decisión, NO diagnóstico.** No reemplaza el juicio clínico ni la urgencia.

## Arquitectura
Dos apps Streamlit independientes que comparten un Google Sheet (vía Service Account / gspread):
- **Visor del Paciente** (`patient_app.py`) — escribe registros.
- **Visor del Equipo Médico** (`dashboard_app.py`) — lee, analiza, triage, contacta.

## Estructura objetivo
```
core/config.py     # columnas del Sheet + umbrales clínicos (NUNCA quemar umbrales en la lógica)
core/sheets.py     # acceso a Sheet: pestañas registros, pacientes, consentimientos, acciones
core/scores.py     # (NUEVO) pMayo, SCCAI (CU), HBI (EC) desde los campos del CRF
core/triage.py     # alertas Rojo/Amarillo/Verde POR ENFERMEDAD, con razones explícitas
core/consent.py    # (NUEVO) consentimiento y re-consentimiento
core/mailer.py     # correo SMTP + plantillas de conducta
core/audit.py      # (NUEVO) registro de acciones del equipo
patient_app.py     # onboarding+consentimiento, registro diario/periódico, notas personales
dashboard_app.py   # monitoreo poblacional, zoom, escalera de conducta, auditoría
```

## Modelo de datos (CRF — pestaña `registros`)
Campos diarios: `ID_Paciente, Timestamp, Enfermedad(CU/EC), Deposiciones_Numero, Sangre_Deposiciones
(Ninguna/Estrías/Evidente/Sangre pura), Urgencia, Deposiciones_Nocturnas, Dolor_Abdominal
(Ninguno/Leve/Moderado/Severo), Estado_General(0-4), Escala_Fatiga(1-10), Frecuencia_Cardiaca,
Fiebre(+°C), Actividades_Diarias, Manif_Extraintestinales, Adherencia_Medicacion, Notas_Paciente`.
Campos periódicos/evento: `Calprotectina_Fecal(µg/g), PCR_Sangre(mg/L), Hemoglobina, Albumina, Peso,
Endoscopia_Resultado, Imagen_Resultado, Cambio_Medicacion, SIBDQ(10-70), Evento_Adverso`.
Otras pestañas: `pacientes` (basal + email), `consentimientos` (versión/fecha/estado), `acciones` (auditoría).
Integridad estilo CRF/ALCOA+: atribuible, contemporáneo, sin borrado físico (baja lógica), versionado.

## Scores (core/scores.py)
- **CU:** Mayo parcial (frecuencia 0-3 + sangrado 0-3 + global), SCCAI (agrega urgencia, nocturnas, bienestar).
- **EC:** HBI (estado general 0-4, dolor 0-3, deposiciones líquidas/día, masa, complicaciones).
- Interpretar frecuencia **relativa al basal** del paciente cuando exista (`Basal_Deposiciones`).

## Triage (core/triage.py) — devuelve nivel + razones
**CU — ROJO:** sangre pura; o ≥6 deposiciones con sangre + signo sistémico (FC>90, T≥37.8, Hb<10.5,
PCR≥30) → sospecha ASUC. **EC — ROJO:** HBI severo; dolor severo + fiebre; signos de obstrucción;
sospecha de complicación penetrante. **AMARILLO (ambas):** actividad leve-moderada, calprotectina
250-499, PCR 5-29, fatiga ≥7, **no adherencia**, tendencia en ascenso. **VERDE:** en objetivo.
Reglas: cualquier bandera roja del paciente fuerza ROJO; la no adherencia nunca es VERDE;
**ante la duda, escalar** (preferir falso positivo).

## Umbrales (core/config.py)
`calpro: amarillo 250 / rojo 500 (µg/g)` · `PCR: amarillo 5 / rojo 30 (mg/L)` ·
`deposiciones: amarillo 4 / rojo 6` · `fatiga_amarillo 7` · `Hb_rojo 10.5` · `FC_rojo 90` · `T_rojo 37.8`.

## Capa de personalización (clave para adherencia)
Notas libres ("lo que el paciente quiera"), diario de síntomas, objetivos personales, recordatorios,
gatillos personales. El equipo las ve en el zoom del paciente.

## Conducta (dashboard, escalera proporcional al riesgo, todo auditado)
Llamada → Teleconsulta → Solicitud de estudios → Ajuste terapéutico → Consulta presencial/guardia.

## Cumplimiento (Argentina) — el sistema lo SOPORTA; validación legal/ética local requerida
Ley 27.553 (teleasistencia/receta electrónica) + ReNaPDiS · Ley 25.326 (datos sensibles) ·
Ley 26.529 (derechos del paciente, HC, consentimiento) · Ley 25.506 (firma digital).
Consentimiento e-consent obligatorio antes de cargar datos; bloquea la carga si no está vigente.

## Convenciones
- Interfaz en español rioplatense, clara y respetuosa; mobile-first en el visor del paciente.
- Credenciales sólo en `secrets`, jamás en el repo.
- Toda alerta devuelve **razones legibles**, no sólo color.

## Definition of Done
1. Un paciente CU y uno EC completan registro diario y periódico de punta a punta.
2. El triage clasifica bien remisión / actividad leve-moderada / brote grave (incl. ASUC) en ambas.
3. El dashboard prioriza por riesgo, muestra razones y registra una conducta.
4. El consentimiento bloquea la carga si no está vigente.
5. Las acciones del equipo quedan auditadas.
