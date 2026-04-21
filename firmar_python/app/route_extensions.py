"""Wraps register_routes so /rest/issuer-certs/resolve is registered without editing main.py or routes.py."""


def ensure_issuer_resolve_registered() -> None:
    import app.routes.routes as routes_module
    from app.routes.issuer_resolve_route import register_issuer_resolve_routes

    if getattr(routes_module.register_routes, "_issuer_resolve_wrapped", False):
        return

    _original = routes_module.register_routes

    def register_routes_with_issuer_resolve(app):
        _original(app)
        register_issuer_resolve_routes(app)

    register_routes_with_issuer_resolve._issuer_resolve_wrapped = True  # type: ignore[attr-defined]
    routes_module.register_routes = register_routes_with_issuer_resolve  # type: ignore[method-assign]
