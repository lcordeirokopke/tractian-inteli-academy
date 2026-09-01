"""Validação Pydantic dos payloads da API (campo `data` do `QueryEnvelope`) — Estágio 1 do plano de
execução Fase 2. Espelha os DTOs de `case/CONTEXTO_PROJETO.md` §3.

Os `TypedDict` de `agent/state.py` seguem soltos (LangGraph exige TypedDict/dataclass simples nos
campos de state); é o conteúdo de `collected[tool_name]["data"]` que é validado contra os modelos
abaixo antes de entrar em `DiagnosticState.collected` (feito em `agent/diagnostic/executor.py`,
Estágio 4).
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class BaselineFeature(BaseModel):
    feature: str
    reference: float
    tolerance: float


class Baseline(BaseModel):
    asset_id: str
    point_id: str
    state: Literal["learning", "established", "invalidated"]
    detection_mode: Literal["baseline", "symptom"]
    established_at: Optional[str] = None
    invalidated_at: Optional[str] = None
    invalidation_reason: Optional[str] = None
    features: list[BaselineFeature] = Field(default_factory=list)
    learnable: bool


class AnalysisEvidence(BaseModel):
    metric: str
    value: float
    reference: Optional[float] = None
    note: str


class Analysis(BaseModel):
    id: str
    asset_id: str
    point_id: str
    type: Literal[
        "none", "imbalance", "misalignment", "bearing_fault", "electrical_fault", "looseness", "lubrication"
    ]  # "none" = nenhuma falha detectada (majoritário nos dados reais); o contrato OpenAPI não
    # fecha esse campo como enum (só `examples`), mas fixamos os 7 valores observados
    detection_mode: Literal["baseline", "symptom"]
    severity: Literal["none", "low", "medium", "high", "critical"]
    confidence: float
    baseline_state_at_detection: Literal["learning", "established", "invalidated", "not_applicable"]
    evidence: list[AnalysisEvidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    model_version: str
    created_at: str
    status: Literal["current", "stale", "pending", "inconclusive"]


class ModelCoverage(BaseModel):
    machine_type: str
    supported: bool
    can_learn_baseline: bool
    note: Optional[str] = None


class ModelRequirements(BaseModel):
    min_completeness: float
    min_snr_db: float
    min_rotation_rpm: Optional[float] = None


class Model(BaseModel):
    id: str
    version: str
    coverage: list[ModelCoverage] = Field(default_factory=list)
    requirements: ModelRequirements
    processing_state: Literal["idle", "running", "pending", "delayed", "failed"]
    last_run_at: Optional[str] = None


class DataQuality(BaseModel):
    asset_id: str
    point_id: str
    completeness: float
    freshness_minutes: int
    snr_db: float
    staleness_flag: bool


class SpectrumPeak(BaseModel):
    freq_hz: float
    amplitude_mm_s: float
    note: Optional[str] = None


class Spectrum(BaseModel):
    asset_id: str
    point_id: str
    frequency_resolution_hz: Optional[float] = None  # nunca populado pela API real (ausente em
    # data/spectra.parquet para qualquer ativo) — não usado por apply_decision_rule/spectrum_confirms
    peaks: list[SpectrumPeak] = Field(default_factory=list)
    bands_missing: list[str] = Field(default_factory=list)
    collected_at: str


ENVELOPE_SCHEMA_BY_TOOL: dict[str, type[BaseModel]] = {
    "get_baseline": Baseline,
    "get_analysis": Analysis,
    "list_analyses": Analysis,  # validado item a item — mas atenção: a API real (api/app/main.py)
    # envelopa como `envelope["data"]["analyses"]` (lista), não `envelope["data"]` diretamente;
    # d_executor (Estágio 4) precisa extrair `data["analyses"]` antes de iterar e validar
    "get_model": Model,
    "get_data_quality": DataQuality,
    "get_spectrum": Spectrum,
}
