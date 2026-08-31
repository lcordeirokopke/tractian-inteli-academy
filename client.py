"""Cliente HTTP para a API industrial Tractian.

Um método por operationId do contrato (`docs/api-contract.openapi.yaml`). Não depende de MCP —
pode ser reusado tanto pelo servidor MCP (`agent/mcp_server.py`) quanto por scripts de avaliação.
"""

import os
from typing import Any

import httpx

API_BASE_URL = os.environ.get("TRACTIAN_API_URL", "http://localhost:8000")


class TractianAPIError(Exception):
    """Erro retornado pela API Tractian (4xx/5xx), no formato do schema `Error` do contrato."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(f"[{status_code}] {code}: {message}")


class TractianClient:
    def __init__(self, base_url: str = API_BASE_URL, timeout: float = 10.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TractianClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- internals ------------------------------------------------------

    @staticmethod
    def _headers(user_id: str | None) -> dict[str, str]:
        return {"x-user-id": user_id} if user_id else {}

    @staticmethod
    def _handle_response(resp: httpx.Response) -> dict[str, Any]:
        if resp.status_code >= 400:
            try:
                body = resp.json()
                code = body.get("code", "UNKNOWN_ERROR")
                message = body.get("message", resp.text)
            except ValueError:
                code = "UNKNOWN_ERROR"
                message = resp.text or resp.reason_phrase
            raise TractianAPIError(resp.status_code, code, message)
        return resp.json()

    def _get(
        self, path: str, *, user_id: str | None = None, seed: str | None = None, **params: Any
    ) -> dict[str, Any]:
        query = {k: v for k, v in {**params, "seed": seed}.items() if v is not None}
        resp = self._client.get(path, headers=self._headers(user_id), params=query)
        return self._handle_response(resp)

    def _post(
        self, path: str, *, user_id: str, justification: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body = {"justification": justification, "params": params or {}}
        resp = self._client.post(path, headers=self._headers(user_id), json=body)
        return self._handle_response(resp)

    def _patch(self, path: str, *, user_id: str, justification: str, **extra: Any) -> dict[str, Any]:
        body = {"justification": justification, **extra}
        resp = self._client.patch(path, headers=self._headers(user_id), json=body)
        return self._handle_response(resp)

    # -- Contexto ---------------------------------------------------------

    def get_company(self, company_id: str, *, seed: str | None = None) -> dict[str, Any]:
        return self._get(f"/companies/{company_id}", seed=seed)

    def list_assets_by_company(self, company_id: str, *, seed: str | None = None) -> dict[str, Any]:
        return self._get(f"/companies/{company_id}/assets", seed=seed)

    def get_current_user(self, user_id: str) -> dict[str, Any]:
        return self._get("/users/me", user_id=user_id)

    # -- Ativos -------------------------------------------------------------

    def get_asset(self, asset_id: str, *, seed: str | None = None) -> dict[str, Any]:
        return self._get(f"/assets/{asset_id}", seed=seed)

    def update_asset_config(
        self, asset_id: str, *, user_id: str, justification: str, changes: dict[str, Any]
    ) -> dict[str, Any]:
        return self._patch(f"/assets/{asset_id}", user_id=user_id, justification=justification, changes=changes)

    # -- Análises -------------------------------------------------------------

    def list_analyses(
        self, asset_id: str, *, status: str | None = None, seed: str | None = None
    ) -> dict[str, Any]:
        return self._get(f"/assets/{asset_id}/analyses", status=status, seed=seed)

    def get_analysis(self, analysis_id: str, *, seed: str | None = None) -> dict[str, Any]:
        return self._get(f"/analyses/{analysis_id}", seed=seed)

    def reprocess_analysis(
        self, analysis_id: str, *, user_id: str, justification: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._post(
            f"/analyses/{analysis_id}/reprocess", user_id=user_id, justification=justification, params=params
        )

    def request_specialist_analysis(
        self, analysis_id: str, *, user_id: str, justification: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._post(
            f"/analyses/{analysis_id}/request-specialist",
            user_id=user_id,
            justification=justification,
            params=params,
        )

    # -- Dados técnicos -------------------------------------------------------------

    def get_baseline(
        self, asset_id: str, *, point_id: str | None = None, seed: str | None = None
    ) -> dict[str, Any]:
        return self._get(f"/assets/{asset_id}/baseline", point_id=point_id, seed=seed)

    def get_rms_series(
        self, asset_id: str, *, point_id: str | None = None, seed: str | None = None
    ) -> dict[str, Any]:
        return self._get(f"/assets/{asset_id}/rms", point_id=point_id, seed=seed)

    def get_spectrum(
        self, asset_id: str, *, point_id: str | None = None, seed: str | None = None
    ) -> dict[str, Any]:
        return self._get(f"/assets/{asset_id}/spectrum", point_id=point_id, seed=seed)

    def get_data_quality(self, asset_id: str, *, seed: str | None = None) -> dict[str, Any]:
        return self._get(f"/assets/{asset_id}/data-quality", seed=seed)

    # -- Modelos -------------------------------------------------------------

    def get_model(self, model_id: str, *, seed: str | None = None) -> dict[str, Any]:
        return self._get(f"/models/{model_id}", seed=seed)

    def request_retraining(
        self, model_id: str, *, user_id: str, justification: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._post(
            f"/models/{model_id}/request-retraining", user_id=user_id, justification=justification, params=params
        )

    # -- Conhecimento -------------------------------------------------------------

    def search_knowledge(
        self, q: str, *, type: str | None = None, seed: str | None = None
    ) -> dict[str, Any]:
        return self._get("/knowledge/search", q=q, type=type, seed=seed)

    def get_knowledge_doc(self, doc_id: str, *, seed: str | None = None) -> dict[str, Any]:
        return self._get(f"/knowledge/{doc_id}", seed=seed)

    # -- Ações / Escalonamento -------------------------------------------------------------

    def escalate_case(
        self, case_id: str, *, user_id: str, justification: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._post(f"/cases/{case_id}/escalate", user_id=user_id, justification=justification, params=params)
