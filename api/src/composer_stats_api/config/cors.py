from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI


def install_cors(app: FastAPI) -> None:
    # Fixed, development-friendly CORS. All configuration is driven from the frontend.
    allowed_origins = ["http://localhost:3000"]
    allowed_origin_regex = r"https?://(localhost|127\.0\.0\.1)(:\d+)?$"
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=allowed_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )


