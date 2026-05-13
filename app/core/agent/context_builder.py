from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo

from app.services.brand_knowledge_service import (
    build_brand_context_for_prompt,
    get_brand_knowledge_list,
)
from app.services.catalog_service import build_catalog_context, load_catalog
from app.services.context_policy_service import (
    build_context_policy,
    select_relevant_catalog_models,
)
from app.services.dealer_location_service import (
    build_dealer_context_for_prompt,
    get_dealers_list,
)
from app.services.internal_knowledge_service import (
    get_business_rules_list,
    get_internal_context,
)
from app.services.vector_retrieval_service_v3 import retrieve_relevant_context_v3


BRAND_CONTEXT_MODE = "structured"  # opciones: "structured" o "rag"
CATALOG_CONTEXT_MODE = "structured"
DEALER_CONTEXT_MODE = "structured"
RULES_CONTEXT_MODE = "structured"


def build_agent_context(
    tenant_config,
    user_message: str,
    lead_state: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Construye el contexto final que se entrega al LLM.

    Esta extracción conserva la lógica previa de premium_agent.py para no
    cambiar comportamiento durante la Fase 2.
    """
    brand = tenant_config.brand
    market = tenant_config.market
    timezone = tenant_config.timezone

    catalog = load_catalog(
        brand=brand,
        market=market,
        path=tenant_config.catalog_path,
    )

    dealers = get_dealers_list(
        brand=brand,
        market=market,
        path=tenant_config.dealers_path,
    )

    brand_knowledge = get_brand_knowledge_list(
        brand=brand,
        market=market,
        path=tenant_config.brand_knowledge_path,
    )

    business_rules = get_business_rules_list(
        brand=brand,
        market=market,
    )

    context_policy = build_context_policy(
        user_message=user_message,
        lead_state=lead_state,
        catalog=catalog,
    )

    print("========== CONTEXT POLICY DEBUG ==========")
    print("Context policy:", context_policy)
    print("==========================================")

    needs_rag = (
        CATALOG_CONTEXT_MODE == "rag"
        or DEALER_CONTEXT_MODE == "rag"
        or BRAND_CONTEXT_MODE == "rag"
        or RULES_CONTEXT_MODE == "rag"
    )

    if needs_rag:
        rag_context = retrieve_relevant_context_v3(
            user_message=user_message,
            lead_state=lead_state,
            catalog=catalog,
            dealers=dealers,
            brand_knowledge=brand_knowledge,
            business_rules=business_rules,
        )
    else:
        rag_context = {
            "models": [],
            "dealers": [],
            "brand_context": "",
            "rules_context": "",
        }

    models = rag_context.get("models", [])
    dealer_context_data = rag_context.get("dealers", [])

    if needs_rag:
        print("USANDO VECTOR RETRIEVAL V3")
        print("MODELOS RECUPERADOS:", [m.get("model") for m in models])
        print("DEALERS RECUPERADOS:", [d.get("name") for d in dealer_context_data])
    else:
        print("RAG V3 DESACTIVADO PARA ESTA RESPUESTA")
        print("USANDO CONTEXTO ESTRUCTURADO")

    if CATALOG_CONTEXT_MODE == "structured":
        catalog_mode = context_policy.get("catalog_mode", "all")

        if catalog_mode == "all":
            catalog_context = build_catalog_context(catalog)

        elif catalog_mode == "selected":
            selected_catalog_models = select_relevant_catalog_models(
                catalog=catalog,
                user_message=user_message,
                lead_state=lead_state,
            )

            catalog_context = build_catalog_context(selected_catalog_models)

        else:
            catalog_context = ""
    else:
        catalog_context = build_catalog_context(models)

    print("========== CATALOG CONTEXT DEBUG ==========")
    print("Catalog mode:", catalog_mode if CATALOG_CONTEXT_MODE == "structured" else "rag")
    print("Catalog context chars:", len(catalog_context or ""))
    print("Catalog contains EX30:", "EX30" in (catalog_context or ""))
    print("Catalog contains EX40:", "EX40" in (catalog_context or ""))
    print("Catalog contains XC60:", "XC60" in (catalog_context or ""))
    print("Catalog contains XC90:", "XC90" in (catalog_context or ""))
    print("Catalog contains autonomía:", "autonomía" in (catalog_context or "").lower() or "autonomia" in (catalog_context or "").lower())
    print("===========================================")

    internal_context = get_internal_context(
        user_message=user_message,
        lead_state=lead_state,
        brand=brand,
        market=market,
    )

    if BRAND_CONTEXT_MODE == "structured":
        if context_policy.get("include_brand"):
            brand_context = build_brand_context_for_prompt(
                brand_knowledge=brand_knowledge,
            )
        else:
            brand_context = ""
    else:
        brand_context = rag_context.get("brand_context", "")

    if DEALER_CONTEXT_MODE == "structured":
        if context_policy.get("include_dealers"):
            dealer_context = build_dealer_context_for_prompt(
                dealers=dealers,
                lead_state=lead_state,
                user_message=user_message,
            )
        else:
            dealer_context = ""
    else:
        dealer_context = build_dealer_context_for_prompt(
            dealers=dealer_context_data,
            lead_state=lead_state,
            user_message=user_message,
        )

    if RULES_CONTEXT_MODE == "rag":
        rules_context = rag_context.get("rules_context", "")
    else:
        rules_context = ""

    print("========== STRUCTURED CONTEXT DEBUG ==========")
    print("Brand context chars:", len(brand_context or ""))
    print("Dealer context chars:", len(dealer_context or ""))
    print("Rules context chars:", len(rules_context or ""))
    print("Dealer context contains Bogotá:", "Bogotá" in dealer_context or "Bogota" in dealer_context)
    print("Dealer context contains Ibagué:", "Ibagué" in dealer_context or "Ibague" in dealer_context)
    print("Dealer context contains Barranquilla:", "Barranquilla" in dealer_context)
    print("Dealer context contains Re Industrias:", "Re Industrias" in dealer_context)
    print("Dealer context contains Massy:", "Massy" in dealer_context)
    print("Brand context contains seguridad:", "seguridad" in (brand_context or "").lower())
    print("Brand context contains electrificación:", "electrificación" in (brand_context or "").lower() or "electrificacion" in (brand_context or "").lower())
    print("=============================================")

    weekday_labels = [
        "lunes",
        "martes",
        "miércoles",
        "jueves",
        "viernes",
        "sábado",
        "domingo",
    ]

    now_bogota = datetime.now(ZoneInfo(timezone))
    weekday_name = weekday_labels[now_bogota.weekday()]

    current_date_context = (
        f"Fecha actual del sistema: {now_bogota.strftime('%Y-%m-%d')}.\n"
        f"Día de la semana: {weekday_name}.\n"
        f"Zona horaria: {timezone}.\n"
        "Usa esta fecha como referencia para entender expresiones como "
        "'mañana', 'este sábado' o 'próximo martes'. "
        "La fecha normalizada final la calcula el backend."
    )

    final_context = f"""
FECHA ACTUAL:
{current_date_context}

CATÁLOGO RELEVANTE:
{catalog_context}

CONOCIMIENTO DE MARCA:
{brand_context if brand_context else "No aplica para esta conversación."}

CONCESIONARIOS / SEDES:
{dealer_context if dealer_context else "No hay contexto de sedes disponible. No inventar sedes, direcciones, entregas ni disponibilidad local."}

CONTEXTO DE NEGOCIO:
{internal_context}

REGLAS INTERNAS RECUPERADAS:
{rules_context if rules_context else "No aplica para esta conversación."}
""".strip()

    return {
        "final_context": final_context,
        "catalog": catalog,
        "dealers": dealers,
        "brand_knowledge": brand_knowledge,
        "business_rules": business_rules,
        "context_policy": context_policy,
        "now": now_bogota,
    }
