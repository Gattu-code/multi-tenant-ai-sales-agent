from typing import Any, Dict, Optional

import requests

from app.config import (
    AUTOMATION_ENABLED,
    AUTOMATION_TIMEOUT_SECONDS,
    AUTOMATION_WEBHOOK_URL,
)


AUTOMATION_ACTIONS = {
    "send_to_sales_advisor",
    "high_priority_lead",
    "schedule_test_drive",
}


def should_trigger_automation(next_action: str) -> bool:
    """
    Define que acciones comerciales salen del chat hacia automatizaciones.
    """
    return next_action in AUTOMATION_ACTIONS


def send_automation_event(
    tenant_id: str,
    session_id: str,
    user_message: str,
    result: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Envia un evento opcional a n8n sin afectar la respuesta del chat.
    """
    next_action = result.get("next_action", "")

    if not AUTOMATION_ENABLED:
        return

    if not AUTOMATION_WEBHOOK_URL:
        print("[AUTOMATION] AUTOMATION_ENABLED=true pero AUTOMATION_WEBHOOK_URL esta vacio.")
        return

    if not should_trigger_automation(next_action):
        return

    payload = {
        "event_type": "sales_agent_next_action",
        "tenant_id": tenant_id,
        "session_id": session_id,
        "next_action": next_action,
        "user_message": user_message,
        "assistant_reply": result.get("assistant_reply", ""),
        "lead_state": result.get("updated_lead_state", {}),
        "confidence": result.get("confidence", 0.0),
        "metadata": metadata or {},
        "source": "fastapi",
    }

    try:
        response = requests.post(
            AUTOMATION_WEBHOOK_URL,
            json=payload,
            timeout=AUTOMATION_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except Exception as exc:
        print(f"[AUTOMATION] Error enviando webhook: {exc}")
