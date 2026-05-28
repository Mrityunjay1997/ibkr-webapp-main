from __future__ import annotations

from typing import Any


def register_order_routes(app: Any) -> None:
    """Register order-related API routes from a single Orders module seam."""
    from orders.held_orders_api import register_held_orders_routes

    register_held_orders_routes(app)
