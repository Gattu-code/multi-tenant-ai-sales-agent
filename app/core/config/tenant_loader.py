import json
from pathlib import Path
from typing import Optional

from app.core.config.tenant_config import TenantConfig


DEFAULT_TENANT_ID = "volvo_colombia"
CLIENTS_DIR = Path("app/clients")


def load_tenant_config(tenant_id: Optional[str] = None) -> TenantConfig:
    """
    Carga la configuracion del tenant solicitado.

    Si no se envia tenant_id, conserva el comportamiento historico usando
    Volvo Colombia como tenant por defecto.
    """
    resolved_tenant_id = tenant_id or DEFAULT_TENANT_ID
    config_path = CLIENTS_DIR / resolved_tenant_id / "tenant.json"

    if not config_path.exists():
        raise ValueError(f"Tenant config no encontrado: {resolved_tenant_id}")

    with config_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return TenantConfig(**data)
