"""API v1 routes.

This module re-exports the shared router so it can be mounted at
the ``/api/v1`` prefix without duplicating any endpoint code.
"""

from app.routers.api import router

__all__ = ["router"]
