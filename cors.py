from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

def add_cors(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 开发时可放宽，上线后需限制
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )