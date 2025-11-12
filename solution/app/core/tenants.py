"""Tenant helpers shared across API layers."""

from typing import Iterable, List

TENANT_CHOICES = [
    {"value": "customer-service", "label": "Customer Service"},
    {"value": "logistics", "label": "Logistics"},
]

_VALID_TENANTS = {item["value"] for item in TENANT_CHOICES}


def normalize_tenants(values: object) -> List[str]:
    """Normalize arbitrary tenant inputs into a unique, ordered list of slugs."""
    if isinstance(values, str):
        candidates: Iterable[object] = [values]
    elif isinstance(values, Iterable):
        candidates = values
    else:
        candidates = []

    normalized: List[str] = []
    seen = set()
    for value in candidates:
        if not isinstance(value, str):
            continue
        slug = value.strip().lower()
        if slug in _VALID_TENANTS and slug not in seen:
            normalized.append(slug)
            seen.add(slug)
    return normalized


def extract_tenants(raw: object) -> List[str]:
    """Return a normalized list of tenants from arbitrary payload structure."""
    if isinstance(raw, dict):
        return normalize_tenants(raw.get("tenants"))
    if raw is None:
        return []
    return normalize_tenants(raw)
