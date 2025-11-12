"""Tenant helpers shared across API layers."""

import json
import os
from typing import Iterable, List

_DEFAULT_CHOICES = [
    {"value": "customer-service", "label": "Customer Service"},
    {"value": "logistics", "label": "Logistics"},
]


def _load_env_tenants() -> List[dict]:
    raw_json = os.getenv("SOLUTION_TENANTS_JSON")
    if raw_json:
        try:
            data = json.loads(raw_json)
            choices = []
            for value in data:
                if isinstance(value, str) and value.strip():
                    slug = value.strip().lower()
                    choices.append({"value": slug, "label": slug})
            if choices:
                return choices
        except json.JSONDecodeError:
            pass

    raw = os.getenv("SOLUTION_TENANTS", "")
    items = []
    if isinstance(raw, str):
        for entry in raw.split(","):
            entry = entry.strip()
            if entry:
                items.append(entry)
    if items:
        return [{"value": item.lower(), "label": item} for item in items]

    return _DEFAULT_CHOICES


TENANT_CHOICES = _load_env_tenants()
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
