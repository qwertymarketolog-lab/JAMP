from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class AttachmentType(str, Enum):
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"


class AttachmentUploadRequest(BaseModel):
    filename: str = Field(..., description="Имя файла с расширением")
    content_type: str = Field(..., description="MIME-тип файла")
    size_bytes: int = Field(..., gt=0, description="Размер файла в байтах")


class AttachmentResponse(BaseModel):
    attachment_id: str = Field(..., description="Уникальный идентификатор аттачмента (att_*)")
    upload_url: HttpUrl = Field(..., description="Pre-signed URL для загрузки в S3/MinIO")
    storage_path: str = Field(..., description="Внутренний URI хранилища (s3://...)")
    sha256: Optional[str] = Field(None, description="SHA-256 хэш файла после загрузки")


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    attachments: Optional[List[str]] = Field(default=[], description="Список attachment_id")


class ChatCompletionOptions(BaseModel):
    adapters: List[str] = Field(default=["default"], description="Список подключаемых адаптеров")
    require_evidence: bool = Field(default=True, description="Требовать ли публикацию provenances/evidence")
    timeout_seconds: int = Field(default=30, ge=1, le=120)


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., description="Capability / Model ID (e.g., capability/marketplace-router)")
    messages: List[ChatMessage]
    stream: bool = Field(default=False, description="Флаг потоковой SSE-отдачи")
    options: Optional[ChatCompletionOptions] = Field(
        default_factory=ChatCompletionOptions
    )


class EvidencePayload(BaseModel):
    evidence_id: str
    provenance_hash: str
    data: Dict[str, Any]
    created_at: str


class ChatCompletionResponse(BaseModel):
    id: str = Field(..., description="Идентификатор сессии/запроса")
    model: str
    message: ChatMessage
    evidence: Optional[EvidencePayload] = None
    finish_reason: str = Field(default="stop")


class ExecutionRequest(BaseModel):
    capability: str = Field(..., description="Название вызываемого capability")
    input_payload: Dict[str, Any] = Field(..., description="Входные параметры")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    execution_id: str
    status: str = Field(..., pattern="^(SUCCESS|FAILED|REFUSED)$")
    result: Dict[str, Any]
    evidence_hash: str
    error_message: Optional[str] = None
