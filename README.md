# AI Sales Agent Template
## Agente Conversacional Premium para Venta Automotriz

Este proyecto implementa un agente conversacional para ventas automotrices, diseñado para responder preguntas de clientes, recomendar vehículos, calificar leads y apoyar flujos de agendamiento para marcas o concesionarios.

El sistema está construido como una plantilla reutilizable multi-tenant. Cada tenant puede tener su propio catálogo, reglas comerciales, conocimiento de marca, sedes, prompt y comportamiento conversacional.

---

## 1. Objetivo del proyecto

El objetivo es construir una base técnica demostrable para agentes IA comerciales en el sector automotriz.

El agente debe poder:

- Responder preguntas sobre vehículos.
- Recomendar modelos según necesidad del cliente.
- Capturar información del lead.
- Identificar intención de compra, visita o agendamiento.
- Mantener contexto conversacional por sesión.
- Usar conocimiento específico por marca o concesionario.
- Devolver respuestas estructuradas en JSON.
- Integrarse con frontends, widgets web, n8n o CRMs.

---

## 2. Casos de uso principales

### 2.1 Recomendación de vehículo

El usuario puede preguntar por un modelo específico o describir una necesidad.

Ejemplos:

- "Quiero conocer la Volvo EX30"
- "Busco una SUV familiar"
- "Quiero una camioneta eléctrica para ciudad"
- "Estoy interesado en la Tracker Turbo en Pereira"

El agente debe usar el contexto del tenant para responder con información relevante y continuar la conversación.

---

### 2.2 Calificación de lead

El agente captura progresivamente datos del cliente:

- Nombre
- Teléfono
- Correo
- Ciudad
- Vehículo de interés
- Presupuesto
- Método de pago
- Tiempo estimado de compra
- Vehículo actual
- Si tiene retoma
- Motivación principal
- Contexto familiar o de uso

Con esta información actualiza un estado estructurado del lead.

---

### 2.3 Agendamiento

El agente puede ayudar a agendar una visita o continuar el flujo cuando el usuario muestra interés en ver un vehículo.

Datos esperados para agendamiento:

1. Ciudad
2. Día
3. Hora
4. Nombre
5. Teléfono
6. Correo

El flujo puede ser refinado por tenant desde el prompt.

---

### 2.4 Direcciones y sedes

Para tenants con sedes físicas, el agente puede entregar direcciones directamente.

Ejemplo para Caminos Eje Cafetero:

- Taller Belmonte Pereira: Av. 30 de Agosto No 94-165, barrio Belmonte, Pereira.
- ChevyExpress Pereira: Cra. 12b #9-52, Pereira.
- Teléfono: 313 5000.

Regla importante: el agente no debe decir "te envío la dirección" sin incluir la dirección directamente.

---

## 3. Arquitectura general

Arquitectura lógica:

```text
Cliente / Widget / Web
        ↓
FastAPI
        ↓
Premium Agent Endpoint
        ↓
Tenant Context Loader
        ↓
Prompt + Brand Knowledge + Catalog + Dealer Info
        ↓
LLM Provider
        ↓
Structured JSON Response
        ↓
Frontend / n8n / CRM
```

---

## 4. Stack técnico

- Python
- FastAPI
- Pydantic
- Uvicorn
- JSON para catálogos y knowledge base
- Prompts por tenant
- LLM externo vía API
- PowerShell para pruebas locales
- Docker para despliegue
- GitHub para control de versiones
- VPS Ubuntu para producción
- Caddy como reverse proxy con HTTPS automático

---

## 5. Estructura esperada del proyecto

```text
ai-sales-agent-template/
│
├── app/
│   ├── main.py
│   ├── premium_agent.py
│   ├── prompts/
│   │   ├── volvo_colombia_prompt.txt
│   │   └── caminos_eje_cafetero_prompt.txt
│   └── ...
│
├── data/
│   ├── brand_knowledge/
│   │   ├── volvo_colombia.json
│   │   └── caminos_eje_cafetero.json
│   │
│   ├── catalogs/
│   │   ├── volvo_colombia.json
│   │   └── caminos_eje_cafetero.json
│   │
│   └── tenants/
│       └── ...
│
├── static/
├── templates/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

La estructura puede variar, pero la idea base es separar:

- lógica core
- prompts
- catálogos
- conocimiento de marca
- configuración por tenant

---

## 6. Tenants actuales

### 6.1 Volvo Colombia

Tenant orientado a un agente premium para vehículos Volvo en Colombia.

Características:

- Conocimiento de marca Volvo.
- Catálogo de modelos como EX30, EX40, XC60, XC90.
- Recomendación según estilo de vida, familia, uso urbano o interés eléctrico.
- Captura progresiva de lead.
- Respuestas prudentes sobre beneficios regulatorios.

---

### 6.2 Caminos Eje Cafetero

Tenant orientado a Caminos, concesionario Chevrolet en el Eje Cafetero.

Características:

- Catálogo Chevrolet.
- Manejo de sedes por ciudad.
- Respuestas sobre modelos como Tracker Turbo.
- Soporte conversacional para agendamiento.
- Entrega directa de direcciones de sedes.
- Manejo de respuestas afirmativas cortas como "sí", "claro", "dale", "ok", "perfecto", "agéndala".

---

## 7. Endpoint principal

### POST `/premium-agent`

Ejemplo de request:

```json
{
  "session_id": "demo-session-1",
  "tenant_id": "caminos_eje_cafetero",
  "user_message": "Quiero ver la Tracker Turbo en Pereira"
}
```

Ejemplo de respuesta esperada:

```json
{
  "assistant_reply": "¡Claro! La Tracker Turbo es una excelente opción para Pereira. ¿Te gustaría agendar una visita para verla?",
  "quick_replies": {},
  "updated_lead_state": {
    "lead_name": "",
    "phone": "",
    "email": "",
    "city": "Pereira",
    "brand": "Chevrolet",
    "vehicle_interest": "Tracker Turbo",
    "vehicle_segment": "SUV compacta urbana",
    "budget_range": "",
    "payment_method": "",
    "purchase_timeframe": "",
    "current_vehicle": "",
    "has_trade_in": null,
    "lifestyle_profile": "",
    "family_context": "",
    "primary_motivation": "",
    "interest_type": "showroom_visit",
    "lead_temperature": "frio",
    "priority_score": 25,
    "qualified": false,
    "pending_questions": [],
    "summary": "Cliente interesado en ver la Tracker Turbo en Pereira.",
    "appointment_date": "",
    "appointment_time": "",
    "appointment_location": "",
    "appointment_date_iso": ""
  },
  "next_action": "continue_conversation",
  "confidence": 0.9
}
```

---

## 8. Instalación local

### 8.1 Crear ambiente virtual

```powershell
python -m venv .venv
```

### 8.2 Activar ambiente virtual

```powershell
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la activación:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Luego volver a activar:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 8.3 Instalar dependencias

```powershell
pip install -r requirements.txt
```

### 8.4 Ejecutar servidor local

```powershell
uvicorn app.main:app --reload --port 8001
```

Abrir:

```text
http://127.0.0.1:8001
```

---

## 9. Pruebas con PowerShell

### 9.1 Probar Caminos - interés inicial

```powershell
$body = @{
  session_id = "caminos-si-test-1"
  tenant_id = "caminos_eje_cafetero"
  user_message = "Quiero ver la Tracker Turbo en Pereira"
} | ConvertTo-Json -Compress

Invoke-RestMethod `
  -Method POST `
  -Uri "http://127.0.0.1:8001/premium-agent" `
  -ContentType "application/json; charset=utf-8" `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

---

### 9.2 Probar continuidad con respuesta afirmativa

```powershell
$body = @{
  session_id = "caminos-si-test-1"
  tenant_id = "caminos_eje_cafetero"
  user_message = "sí"
} | ConvertTo-Json -Compress

Invoke-RestMethod `
  -Method POST `
  -Uri "http://127.0.0.1:8001/premium-agent" `
  -ContentType "application/json; charset=utf-8" `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

---

### 9.3 Probar dirección de Pereira

```powershell
$body = @{
  session_id = "caminos-address-test-1"
  tenant_id = "caminos_eje_cafetero"
  user_message = "Me das la direccion de la sede de Pereira?"
} | ConvertTo-Json -Compress

Invoke-RestMethod `
  -Method POST `
  -Uri "http://127.0.0.1:8001/premium-agent" `
  -ContentType "application/json; charset=utf-8" `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

Respuesta esperada:

```text
Claro, en Pereira tenemos dos sedes: Taller Belmonte Pereira en Av. 30 de Agosto No 94-165, barrio Belmonte, y ChevyExpress Pereira en Cra. 12b #9-52. Ambas con teléfono 313 5000.
```

---

## 10. Manejo de encoding en PowerShell

Si aparecen caracteres raros como:

```text
telÃ©fono
Â¿Te gustarÃa
```

ejecutar:

```powershell
chcp 65001
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8
```

Y enviar el body como bytes UTF-8:

```powershell
-Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

---

## 11. Validaciones antes de commit

### 11.1 Revisar archivos modificados

```powershell
git status
```

### 11.2 Validar diff

```powershell
git diff -- app/prompts/caminos_eje_cafetero_prompt.txt data/brand_knowledge/caminos_eje_cafetero.json
```

### 11.3 Validar espacios y formato

```powershell
git diff --check
```

Warnings de LF/CRLF en Windows no bloquean necesariamente el commit.

### 11.4 Validar JSON

```powershell
python -m json.tool data/brand_knowledge/caminos_eje_cafetero.json > $null
```

### 11.5 Buscar reglas sin ripgrep

Si `rg` no está instalado:

```powershell
Select-String -Path `
  app/prompts/caminos_eje_cafetero_prompt.txt, `
  data/brand_knowledge/caminos_eje_cafetero.json `
  -Pattern "RESPUESTAS AFIRMATIVAS|Taller Belmonte Pereira|ChevyExpress Pereira|no digas que enviaras la direccion"
```

---

## 12. Commit recomendado para mini fix Caminos

No usar `git add .` si hay otros archivos modificados.

```powershell
git add app/prompts/caminos_eje_cafetero_prompt.txt data/brand_knowledge/caminos_eje_cafetero.json
git commit -m "Improve Caminos affirmative continuity and address handling"
git push
```

---

## 13. Despliegue en VPS

Servidor actual:

```text
VPS Contabo
IP: 173.212.236.118
Dominio: nxtsln.cloud
```

Infraestructura base:

- Ubuntu
- Docker
- Docker Compose
- Caddy
- HTTPS automático
- GitHub como fuente de despliegue

Patrón recomendado:

```text
Local VSCode
  ↓ git commit
GitHub
  ↓ git pull
VPS
  ↓ docker compose up -d --build
Producción
```

---

## 14. Reglas importantes de despliegue multi-demo

Ya existe un Caddy controlando puertos 80 y 443 en el VPS.

Para nuevos demos:

- No crear otro Caddy.
- No publicar puertos 80/443 en nuevos contenedores.
- Conectar nuevas apps a la red Docker existente.
- Agregar subdominios al Caddyfile global.

Ejemplo:

```text
fleet.nxtsln.cloud     → fleet demo
demo.nxtsln.cloud      → segundo demo
n8n.nxtsln.cloud       → n8n
api.nxtsln.cloud       → backend API
```

---

## 15. Pendientes conocidos

### 15.1 Continuidad con "sí"

El agente ya entiende que "sí" puede continuar el flujo de agendamiento, pero en una prueba saltó a pedir teléfono/correo antes de día/hora.

Comportamiento deseado futuro:

Si el usuario ya tiene ciudad y modelo, pero no tiene día ni hora:

```text
Usuario: sí
Respuesta esperada: Perfecto, agendemos tu visita para conocer la Tracker Turbo en Pereira. ¿Qué día te gustaría asistir?
```

Este ajuste puede hacerse más adelante desde prompt/knowledge.

---

### 15.2 Pruebas desde web

Pendiente validar el comportamiento completo desde el widget o frontend web, no solo desde PowerShell.

---

## 16. Buenas prácticas del proyecto

- Mantener prompts por tenant.
- Mantener knowledge por tenant.
- No mezclar fixes de un tenant con otro.
- No tocar core si el cambio puede resolverse por prompt/knowledge.
- Hacer commits pequeños y descriptivos.
- Validar JSON antes de commit.
- Probar local antes de desplegar.
- Evitar exponer credenciales en GitHub.
- No subir archivos `.env`.

---

## 17. Valor profesional del proyecto

Este proyecto demuestra competencias relevantes para transición profesional hacia IA aplicada:

- Diseño de agentes conversacionales.
- Prompt engineering aplicado a negocio.
- Arquitectura multi-tenant.
- Integración FastAPI + LLM.
- Manejo de contexto por tenant.
- Automatización de leads.
- Estructuración de salida JSON.
- Deploy en VPS con Docker.
- Uso de GitHub como flujo profesional.
- Testing funcional con PowerShell.
- Preparación para integración con n8n, CRM o frontend web.

---

## 18. Resumen ejecutivo

AI Sales Agent Template es una base reutilizable para construir agentes IA de ventas automotrices por marca o concesionario. Permite responder preguntas, recomendar vehículos, calificar leads y apoyar agendamientos usando contexto específico por tenant.

Actualmente incluye trabajo con Volvo Colombia y Caminos Eje Cafetero, con mejoras recientes para manejo de direcciones y respuestas afirmativas cortas. El proyecto está preparado para seguir evolucionando hacia demos comerciales, integración con n8n, despliegue en VPS y conexión con CRMs.
