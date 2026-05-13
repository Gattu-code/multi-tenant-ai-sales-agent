"""
Módulo: premium_agent

Responsabilidad:
Orquestar la interacción entre:
- el estado actual del lead,
- el prompt base del agente,
- el historial de conversación,
- el catálogo/contexto comercial,
- y el modelo de IA en ai_provider
OpenRouter/Gemini para generación y Ollama para embeddings

Este módulo:
1. construye el prompt final,
2. llama al modelo,
3. interpreta la respuesta JSON,
4. actualiza el estado del lead,
5. recalcula el estado comercial.
"""

import json
from typing import Any, Dict, List, Optional
from app.config import EXTERNAL_LLM_MODEL
from app.core.agent.context_builder import build_agent_context
from app.core.agent.prompt_builder import build_prompt
from app.core.config.tenant_loader import load_tenant_config
from app.services.agent_observability_service import (
    build_agent_run_trace,
    record_agent_run,
)
from app.services.date_normalizer import resolve_appointment_date
from app.services.contact_validation_service import get_invalid_contact_fields
from app.services.ai_provider import generate_ai_response
from app.models.lead_model import LeadModel
from app.services.lead_normalizer import normalize_lead
from app.services.lead_router import decide_next_action
from app.storage.lead_store import save_lead

from app.utils.debug import debug_prompt

def safe_parse_json(raw_text: str) -> Dict[str, Any]:
    """
    Intenta convertir la respuesta del modelo en JSON.

    Estrategia:
    1. intenta parsear el texto completo,
    2. si falla, intenta extraer el bloque entre el primer '{' y el último '}'.

    Args:
        raw_text (str): texto bruto retornado por el modelo.

    Returns:
        dict: JSON interpretado.

    Raises:
        ValueError: si no se encuentra JSON válido.
    """
    raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")

        if start != -1 and end != -1 and end > start:
            candidate = raw_text[start:end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"No fue posible parsear el JSON del modelo: {exc}"
                ) from exc

        raise ValueError("La respuesta del modelo no contiene JSON válido.")

def sanitize_quick_replies(value, max_items: int = 8) -> list[str]:
    """
    Normaliza y valida las respuestas rápidas generadas por el LLM.

    Reglas:
    - Deben ser lista.
    - Máximo configurable de opciones.
    - Cada opción debe ser texto corto.
    - Se eliminan vacíos y duplicados.
    """
    if not isinstance(value, list):
        return []

    cleaned = []
    seen = set()

    for item in value:
        text = str(item or "").strip()

        if not text:
            continue

        if len(text) > 40:
            continue

        key = text.lower()

        if key in seen:
            continue

        seen.add(key)
        cleaned.append(text)

        if len(cleaned) >= max_items:
            break

    return cleaned

def normalize_agent_response(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Garantiza que existan las claves mínimas esperadas.

    Si el modelo omite alguna clave, se completa con valores por defecto.
    Si el modelo devuelve quick_replies, se conservan para sanitizarlas después.
    """
    return {
        "assistant_reply": parsed.get("assistant_reply", ""),
        "quick_replies": parsed.get("quick_replies", []),
        "updated_lead_state": parsed.get("updated_lead_state", {}),
        "next_action": parsed.get("next_action", "continue_conversation"),
        "confidence": parsed.get("confidence", 0.0),
    }


def process_lead_message(
    session_id: str,
    user_message: str,
    lead_state: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    catalog_context: str = "",
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Procesa un mensaje del usuario y devuelve la respuesta estructurada del agente AI.

    Flujo completo:
    1. Inicializa el estado del lead si no existe.
    2. Carga el catálogo activo y construye contexto de productos.
    3. Construye el prompt contextual para el modelo.
    4. Ejecuta la inferencia en el modelo (Ollama).
    5. Parsea y normaliza la respuesta del modelo.
    6. Actualiza el estado del LeadModel con la información inferida.
    7. Aplica reglas de negocio (normalización y enriquecimiento).
    8. Recalcula el estado comercial del lead.
    9. Decide la siguiente acción (lógica backend).
    10. Ajusta la respuesta si se requiere solicitar contacto.
    11. Persiste el lead si está en etapa de contacto.

    Args:
        user_message (str): mensaje actual del usuario.
        lead_state (dict, optional): estado previo del lead.
        conversation_history (list[dict], optional): historial previo.
        catalog_context (str): parámetro reservado para contexto de catálogo.
            Se sobrescribe dinámicamente con el catálogo activo.

    Returns:
        dict: respuesta estructurada del agente con:
            - assistant_reply (str)
            - updated_lead_state (dict)
            - next_action (str)
            - confidence (float)
    """
    # -----------------------------
    # 1. Inicialización del estado
    # -----------------------------
    tenant_config = load_tenant_config(tenant_id)

    lead_state = lead_state or LeadModel().model_dump()

    context_pack = build_agent_context(
        tenant_config=tenant_config,
        user_message=user_message,
        lead_state=lead_state,
    )

    final_context = context_pack["final_context"]
    dealers = context_pack["dealers"]
    now_bogota = context_pack["now"]

    # -----------------------------
    # 3. Construcción del prompt final
    # -----------------------------
    # Limitamos el historial reciente para controlar consumo de tokens
    # y mantener el foco conversacional.
    conversation_history = (conversation_history or [])[-4:]

    prompt = build_prompt(
        user_message=user_message,
        lead_state=lead_state,
        conversation_history=conversation_history,
        context=final_context,
        prompt_path=tenant_config.prompt_path,
    )
    
    # -----------------------------
    # DEBUG: Guardar último prompt real
    # -----------------------------
    print("========== FINAL PROMPT DEBUG ==========")
    print("Prompt chars:", len(prompt))
    print("Prompt contains EX30:", "EX30" in prompt)
    print("Prompt contains XC60:", "XC60" in prompt)
    print("Prompt contains dealers:", "vitrina" in prompt.lower() or "sede" in prompt.lower())
    print("Prompt contains brand knowledge:", "seguridad" in prompt.lower())
    print("========================================")

    with open("data/last_prompt_debug.txt", "w", encoding="utf-8") as f:
        f.write(prompt)

    # -----------------------------
    # 4. Llamada al modelo (LLM)
    # -----------------------------
    debug_prompt(prompt)
    raw_response = generate_ai_response(prompt)

    # -----------------------------
    # 5. Parseo y normalización
    # -----------------------------
    parsed = safe_parse_json(raw_response)
    parsed = normalize_agent_response(parsed)

    # -----------------------------
    # 6. Actualización del LeadModel
    # -----------------------------
    updated_state = parsed.get("updated_lead_state", {})

    lead = LeadModel(**lead_state)
    lead.update_from_dict(updated_state)

    # Normalización determinística de fecha de cita
    # Normalización determinística de fecha de cita
    normalized_date = resolve_appointment_date(
        user_message=user_message,
        current_appointment_date=lead.appointment_date,
        now=now_bogota,
    )

    if normalized_date.get("iso_date"):
        lead.appointment_date = normalized_date["iso_date"]

        if hasattr(lead, "appointment_date_iso"):
            lead.appointment_date_iso = normalized_date["iso_date"]

        print("========== DATE NORMALIZATION ==========")
        print("Date source:", normalized_date.get("source"))
        print("Normalized appointment_date:", normalized_date.get("iso_date"))
        print("Reason:", normalized_date.get("reason"))
        print("========================================")

    # Primera evaluación del estado comercial
    lead.refresh_business_state()
    # -----------------------------
    # 7. Normalización de negocio
    # -----------------------------
    lead = normalize_lead(lead)

    # -----------------------------
    # 8. Recalcular estado final
    # -----------------------------
    lead.refresh_business_state()

    # Sobrescribir el estado con el resultado final del backend
    parsed["updated_lead_state"] = lead.model_dump()
    
    # -----------------------------
    # Quick replies
    # -----------------------------
    # El LLM puede sugerir respuestas rápidas contextuales.
    # El backend las sanitiza para evitar ruido, duplicados o textos largos.
    max_quick_replies = 6

    assistant_reply_text = (parsed.get("assistant_reply") or "").lower()
    next_action = parsed.get("next_action") or ""

    if (
        next_action in [
            "dealer_city_selection_required",
            "dealer_selection_required",
        ]
        or "ciudades con vitrinas" in assistant_reply_text
        or "ciudades con sede" in assistant_reply_text
        or f"vitrinas {tenant_config.brand_name.lower()} disponibles" in assistant_reply_text
    ):
        max_quick_replies = 12

    parsed["quick_replies"] = sanitize_quick_replies(
        parsed.get("quick_replies", []),
        max_items=max_quick_replies,
    )

    # -----------------------------
    # 9. Decisión de siguiente acción
    # -----------------------------
    parsed["next_action"] = decide_next_action(
        lead=lead,
        current_action=parsed.get("next_action", "continue_conversation"),
    )
        
    # -----------------------------
    # 10. Ajuste de respuesta comercial
    # -----------------------------
    # El backend puede sobrescribir la respuesta del LLM cuando detecta:
    # - falta de teléfono o correo
    # - teléfono o correo inválidos
    # - falta de nombre antes de confirmar cita
    # - falta de sede específica antes de confirmar cita
    
    missing_contact_fields = []

    if not lead.phone:
        missing_contact_fields.append("teléfono")

    if not lead.email:
        missing_contact_fields.append("correo electrónico")

    if parsed.get("next_action") == "request_contact_info" and missing_contact_fields:
        if len(missing_contact_fields) == 2:
            contact_request = "tu número de teléfono y correo electrónico"
        else:
            contact_request = f"tu {missing_contact_fields[0]}"

        parsed["assistant_reply"] = (
            f"Perfecto, {lead.lead_name or ''}. Para avanzar con la visita, "
            f"¿me compartes {contact_request}?"
        ).replace("  ", " ").strip()

        parsed["quick_replies"] = []
        parsed.setdefault("updated_lead_state", lead.model_dump())
        parsed["updated_lead_state"]["pending_questions"] = []

    # -----------------------------
    # Solicitud de corrección de contacto inválido
    # -----------------------------
    invalid_contact_fields = get_invalid_contact_fields(lead)

    if parsed.get("next_action") == "request_valid_contact_info" and invalid_contact_fields:
        if len(invalid_contact_fields) == 2:
            contact_request = "un número de teléfono completo y un correo electrónico válido"
        elif invalid_contact_fields[0] == "teléfono":
            contact_request = "un número de teléfono completo"
        else:
            contact_request = "un correo electrónico válido"

        parsed["assistant_reply"] = (
            f"Gracias. Para confirmar tu visita, ¿me compartes {contact_request}?"
        )

        parsed["quick_replies"] = []
        parsed.setdefault("updated_lead_state", lead.model_dump())
        parsed["updated_lead_state"] = lead.model_dump()
        parsed["updated_lead_state"]["pending_questions"] = []

    # -----------------------------
    # Solicitud de nombre antes de confirmar cita
    # -----------------------------
    # Si ya tenemos los datos principales de la visita,
    # pero falta el nombre del cliente, no confirmamos todavía.
    if parsed.get("next_action") == "request_lead_name":
        parsed["assistant_reply"] = (
            "Perfecto, ya tengo los datos principales de la visita. "
            "¿Me confirmas tu nombre para dejarla registrada correctamente?"
        )

        parsed["quick_replies"] = []
        parsed.setdefault("updated_lead_state", lead.model_dump())
        parsed["updated_lead_state"]["pending_questions"] = []        
        

    # -----------------------------
    # Dealer obligatorio antes de confirmar cita
    # -----------------------------
    # Si el cliente ya tiene intención de visita y fecha/hora,
    # pero no hay sede/vitrina específica, no confirmamos la cita.
    # Primero pedimos seleccionar una sede válida.
    appointment_location = lead.appointment_location or {}

    has_dealer = (
        isinstance(appointment_location, dict)
        and appointment_location.get("dealer_name")
        and appointment_location.get("city")
    )

    if (
        lead.interest_type == "visita"
        and lead.appointment_date
        and lead.appointment_time
        and not has_dealer
    ):
        city = (lead.city or "").strip()

        dealer_names = []

        for dealer in dealers:
            dealer_city = str(dealer.get("city", "")).strip()

            if city and dealer_city.lower() == city.lower():
                dealer_name = dealer.get("name") or dealer.get("dealer_name")

                if dealer_name and dealer_name not in dealer_names:
                    dealer_names.append(dealer_name)

        if dealer_names:
            parsed["assistant_reply"] = (
                f"Perfecto, {lead.lead_name or ''}. Antes de confirmar tu visita, "
                f"¿en cuál sede te gustaría conocer el vehículo en {city}?"
            ).replace("  ", " ").strip()

            parsed["quick_replies"] = dealer_names[:6]
            parsed["next_action"] = "dealer_selection_required"
            parsed.setdefault("updated_lead_state", lead.model_dump())
            parsed["updated_lead_state"]["pending_questions"] = []

    # -----------------------------
    # 11. Persistencia del lead
    # -----------------------------
    # Guardamos cada interacción para mantener trazabilidad por conversación.

    # -----------------------------
    # Limpieza de preguntas pendientes
    # -----------------------------
    # La respuesta visible ya va en assistant_reply.
    # Evitamos que la UI muestre una segunda pregunta duplicada.
    parsed.setdefault("updated_lead_state", lead.model_dump())
    parsed["updated_lead_state"]["pending_questions"] = []
    
    # -----------------------------
    # Quick replies temporalmente desactivadas
    # -----------------------------
    # Se desactivan globalmente para estabilizar el flujo conversacional.
    # Mantener este bloque facilita reactivarlas luego sin borrar la lógica.
    parsed["quick_replies"] = []

    save_lead(session_id, parsed["updated_lead_state"])

    record_agent_run(
        trace=build_agent_run_trace(
            tenant_id=tenant_config.tenant_id,
            session_id=session_id,
            user_message=user_message,
            model=EXTERNAL_LLM_MODEL,
            prompt=prompt,
            assistant_reply=parsed.get("assistant_reply", ""),
            result=parsed,
            context_policy=context_pack.get("context_policy"),
        ),
        prompt=prompt,
    )

    # -----------------------------
    # 12. Retorno final
    # -----------------------------
    print("PENDING QUESTIONS FINAL:", parsed["updated_lead_state"].get("pending_questions"))
    return parsed
