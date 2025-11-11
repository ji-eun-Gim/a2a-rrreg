"""Compatibility shim so you can run:
    uvicorn jws_server:app --reload --port 8001

This module simply re-exports `app` from jws.py.
"""

from jws import app  # noqa: F401

__all__ = ["app"]

