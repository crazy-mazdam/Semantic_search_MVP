from __future__ import annotations
from typing import List, Optional, Literal
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, model_validator

class DocumentMetadata(BaseModel):
    """
    Unified schema for document-level metadata.
    Stored as JSON in data/indexes/metadata/{doc_id}.json
    """
    # Lifecycle
    status: Literal["draft", "ready"] = "draft"   # 'draft' until user confirms required fields
    ingested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Ingestion timestamp (UTC)"
    )

    # Identity
    doc_id: str = Field(..., description="MD5 hash of the PDF file content, unique per document")
    source_path: Optional[str] = Field(None, description="Relative/abs path to original PDF file")

    # Descriptive fields
    title: Optional[str] = Field(None, description="Document title (required when status='ready')")
    title_guess: Optional[str] = Field(None, description="Heuristic/auto-suggested title (from filename or extraction)")
    authors: Optional[List[str]] = Field(default_factory=list, description="List of authors")
    year: Optional[int] = Field(None, description="Year of publication")
    doc_type: Optional[str] = Field(
        None, description="Document type: book, paper, article, report, other"
    )
    tags: Optional[List[str]] = Field(default_factory=list, description="Optional thematic tags")

    # --- Validators (Pydantic v2) ---
    @field_validator("year")
    @classmethod
    def validate_year(cls, v):
        if v is not None and (v < 1000 or v > datetime.now(timezone.utc).year + 1):
            raise ValueError(f"Year {v} is out of valid range")
        return v

    @field_validator("doc_type")
    @classmethod
    def validate_doc_type(cls, v):
        allowed = [None, "book", "paper", "article", "report", "other"]
        if v not in allowed:
            raise ValueError(f"doc_type must be one of {allowed}, got {v}")
        return v

    @model_validator(mode="after")
    def require_title_when_ready(self):
        # If status is 'ready', title must be present and non-empty.
        if self.status == "ready":
            if not (self.title and self.title.strip()):
                raise ValueError("title is required when status='ready'")
        return self

    class Config:
        extra = "ignore"          # tolerate older JSONs with extra keys
        validate_assignment = True
        json_schema_extra = {
            "example": {
                "status": "ready",
                "doc_id": "f6a8d0e9...",
                "title": "Asymmetric Demography and the Global Economy",
                "authors": ["José María Fanelli"],
                "year": 2015,
                "doc_type": "book",
                "tags": ["demography", "macroeconomics"],
                "ingested_at": "2025-08-29T10:35:00Z",
                "source_path": "data/pdfs/Asymmetric_Demography.pdf"
            }
        }
