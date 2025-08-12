from fastapi import FastAPI
from .config.cors import install_cors
from .routers.health import router as health_router
from .routers.performance import router as performance_router


def create_app() -> FastAPI:
    app = FastAPI(title="Composer Stats API", version="0.3.0")
    install_cors(app)
    app.include_router(health_router)
    app.include_router(performance_router, prefix="/api", tags=["performance"])
    return app


app = create_app()


