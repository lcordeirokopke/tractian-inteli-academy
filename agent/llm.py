"""Instâncias de LLM usadas pelo agente — Estágio 3 do plano de execução Fase 2.

kimi_k3 (usado por `d_planner`) via endpoint OpenAI-compatible da NVIDIA NIM; gemini_flash
(`d_replanner`) e gemini_flash_lite (`orient_response`) via Google Generative AI. Cada instância é
usada com `.with_structured_output(...)` nos nodes que a consomem.

Credenciais carregadas de um `.env` na RAIZ do repositório (não em `agent/`) — nunca logadas.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

NIM_BASE_URL = os.environ.get("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
NIM_API_KEY = os.environ.get("NIM_API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

kimi_k3 = ChatOpenAI(
    model="moonshotai/kimi-k3", base_url=NIM_BASE_URL, api_key=NIM_API_KEY
)  # d_planner — "kimi-k3" sozinho não existe no catálogo NIM, precisa do namespace "moonshotai/"
gemini_flash = ChatGoogleGenerativeAI(model="gemini-3.7-flash", google_api_key=GOOGLE_API_KEY)  # d_replanner
gemini_flash_lite = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite", google_api_key=GOOGLE_API_KEY
)  # orient_response
