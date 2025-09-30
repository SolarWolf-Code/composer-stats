import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI


def install_cors(app: FastAPI) -> None:
    # Configure CORS for both development and production
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:3123",
        "http://localhost:7949",
        "http://localhost:7950",
        "https://icstats.solarwolf.xyz",
    ]
    
    # Add any additional origins from environment
    extra_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
    for origin in extra_origins:
        if origin.strip():
            allowed_origins.append(origin.strip())
    
    # Regex to allow localhost and 127.0.0.1 with any port
    allowed_origin_regex = r"https?://(localhost|127\.0\.0\.1)(:\d+)?$"
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=allowed_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
