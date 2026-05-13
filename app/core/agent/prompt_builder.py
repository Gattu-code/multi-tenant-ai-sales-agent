import json
from pathlib import Path
from typing import Any, Dict, List, Optional


# Ruta del prompt base del agente
PROMPT_PATH = Path("app/prompts/premium_prompt.txt")


def load_base_prompt(prompt_path: Optional[str] = None) -> str:
    """
    Carga desde archivo el prompt base del agente.

    Returns:
        str: contenido del archivo premium_prompt.txt.
    """
    path = Path(prompt_path) if prompt_path else PROMPT_PATH
    return path.read_text(encoding="utf-8")


def build_prompt(
    user_message: str,
    lead_state: Dict[str, Any],
    conversation_history: Optional[List[Dict[str, str]]] = None,
    context: str = "",
    prompt_path: Optional[str] = None,
) -> str:
    """
    Construye el prompt final enviado al LLM.

    Responsabilidad:
    - Combinar instrucciones base del agente.
    - Incluir contexto RAG V3 multi-fuente.
    - Incluir historial reciente y estado actual del lead.
    - Exigir salida en JSON válido.

    Contexto esperado:
    - catálogo de modelos recuperados,
    - conocimiento de marca,
    - concesionarios / sedes,
    - reglas internas de negocio.

    Args:
        user_message (str): último mensaje del cliente.
        lead_state (Dict[str, Any]): estado acumulado del lead.
        conversation_history (Optional[List[Dict[str, str]]]): historial reciente.
        context (str): contexto final construido por RAG V3.

    Returns:
        str: prompt completo listo para enviar al modelo.
    """
    base_prompt = load_base_prompt(prompt_path=prompt_path)

    history_text = json.dumps(
        conversation_history or [],
        ensure_ascii=False,
        separators=(",", ":"),
    )

    lead_text = json.dumps(
        lead_state or {},
        ensure_ascii=False,
        separators=(",", ":"),
    )

    prompt = f"""
{base_prompt}

----------------------------------------
CONTEXTO RAG V3 DISPONIBLE
----------------------------------------
{context if context else "No hay contexto adicional disponible."}

----------------------------------------
HISTORIAL RECIENTE
----------------------------------------
{history_text}

----------------------------------------
ESTADO ACTUAL DEL LEAD
----------------------------------------
{lead_text}

----------------------------------------
MENSAJE ACTUAL DEL CLIENTE
----------------------------------------
{user_message}

----------------------------------------
REGLAS FINALES DE SALIDA
----------------------------------------
- Responde únicamente en JSON válido.
- No incluyas texto antes ni después del JSON.
- Usa solo la información disponible en el contexto.
- No inventes modelos, sedes, direcciones, precios, autonomías ni beneficios.
- No preguntes datos que ya estén en el estado del lead.
- Haz máximo 1 pregunta útil en assistant_reply.
""".strip()

    return prompt
