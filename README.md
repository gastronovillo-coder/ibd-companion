# IBD Companion — README

## ¿Qué es?

Sistema de telemonitoreo continuo para **Enfermedad Inflamatoria Intestinal (EII)** —
Colitis Ulcerosa (CU) y Enfermedad de Crohn (EC). Modelo treat-to-target STRIDE-II.

**Es apoyo a la decisión clínica. NO diagnóstico. No reemplaza el juicio médico.**

---

## Estructura

```
core/
  config.py      # Umbrales clínicos + columnas CRF (fuente única de verdad)
  sheets.py      # Acceso a Google Sheets (gspread)
  scores.py      # pMayo, SCCAI (CU) | HBI (EC)
  triage.py      # Semáforo ROJO/AMARILLO/VERDE + razones legibles
  consent.py     # E-consent y re-consentimiento
  audit.py       # Registro de acciones del equipo
  mailer.py      # SMTP + plantillas de conducta
patient_app.py   # Visor del Paciente (mobile-first)
dashboard_app.py # Visor del Equipo Médico
tests/
  test_triage.py # Tests de triage y scores
```

---

## Setup paso a paso

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Google Sheets — Service Account

1. Ir a [Google Cloud Console](https://console.cloud.google.com/)
2. Crear un proyecto → Habilitar **Google Sheets API** y **Google Drive API**
3. Crear una **Service Account** → Descargar el JSON de credenciales
4. Crear un Google Sheet con estas pestañas:
   - `registros`
   - `pacientes`
   - `consentimientos`
   - `acciones`
5. Compartir el Sheet con el email de la Service Account (`ibd-companion@...iam.gserviceaccount.com`)

### 3. Configurar secrets

Copiar `.streamlit/secrets.toml` (ya existe como template) y completar con tus credenciales:

```toml
[gcp_service_account]
type = "service_account"
project_id = "TU_PROJECT_ID"
private_key_id = "..."
private_key = "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n"
client_email = "ibd-companion@TU_PROJECT_ID.iam.gserviceaccount.com"
# ... (resto del JSON de la Service Account)

[sheets]
spreadsheet_id = "EL_ID_DE_TU_SPREADSHEET"

[smtp]
host = "smtp.gmail.com"
port = 587
user = "tu_email@gmail.com"
password = "TU_APP_PASSWORD"

[app]
team_pin = "TU_PIN_EQUIPO"
consent_version = "v1.0"
consent_fecha = "2026-06-01"
```

### 4. Registrar el primer paciente

Agregar manualmente en la pestaña `pacientes` del Sheet:

| ID_Paciente | Nombre | Email | Enfermedad | Basal_Deposiciones | Medicacion_Actual | Fecha_Alta | Activo | PIN |
|---|---|---|---|---|---|---|---|---|
| PAC-001 | Juan García | juan@email.com | CU | 1 | Mesalazina 4g/día | 2026-06-01 | True | (hash SHA-256 del PIN) |

Para generar el hash del PIN:
```python
import hashlib
print(hashlib.sha256("1234".encode()).hexdigest())
```

### 5. Correr la app

**Visor del Paciente:**
```bash
streamlit run patient_app.py
```

**Dashboard del Equipo:**
```bash
streamlit run dashboard_app.py
```

Para correr ambas simultáneamente en puertos diferentes:
```bash
streamlit run patient_app.py --server.port 8501 &
streamlit run dashboard_app.py --server.port 8502
```

---

## Tests

```bash
python tests/test_triage.py
```

Cubre los 5 puntos del **Definition of Done**:
1. ✅ CU remisión → VERDE
2. ✅ CU actividad leve-moderada → AMARILLO
3. ✅ CU brote grave / sospecha ASUC → ROJO
4. ✅ EC remisión → VERDE
5. ✅ EC severo → ROJO
6. ✅ No adherencia → nunca VERDE

---

## Deploy en Streamlit Community Cloud

1. Subir el proyecto a un repositorio privado de GitHub
2. Ir a [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Seleccionar el repo → File: `patient_app.py` o `dashboard_app.py`
4. En **Advanced settings → Secrets**: pegar el contenido de `secrets.toml`
5. Deploy

**¡No commitear el `secrets.toml` con credenciales reales al repo!**
Agregar `.streamlit/secrets.toml` al `.gitignore`.

---

## Cumplimiento legal (Argentina)

Este sistema **soporta** el cumplimiento de:
- Ley 25.326 — Protección de Datos Personales (datos sensibles de salud)
- Ley 26.529 — Derechos del Paciente y Consentimiento Informado
- Ley 27.553 — Teleasistencia en Salud
- Ley 25.506 — Firma Digital

**La validación legal y ética local (CEI, habilitación como dispositivo médico si aplica)
es responsabilidad del equipo institucional.**

---

## Ante una emergencia

El sistema **no reemplaza la guardia médica**.
Ante duda de brote grave (ASUC, obstrucción, perforación): derivar a guardia.
Número de emergencias: **107**.
