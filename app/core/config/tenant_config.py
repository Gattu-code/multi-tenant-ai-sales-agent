from pydantic import BaseModel


class TenantConfig(BaseModel):
    """
    Configuracion minima de un tenant.

    Fase 1 mantiene los archivos actuales en su ubicacion original y solo
    centraliza los valores que antes vivian hardcodeados en el agente.
    """

    tenant_id: str
    brand: str
    brand_name: str
    market: str
    market_name: str
    timezone: str
    currency: str
    prompt_path: str
    catalog_path: str
    dealers_path: str
    brand_knowledge_path: str
