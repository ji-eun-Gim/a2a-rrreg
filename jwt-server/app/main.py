# 앱 진입점
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from . import users, tenants

app = FastAPI(title="JWT Auth Server", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(tenants.router)
