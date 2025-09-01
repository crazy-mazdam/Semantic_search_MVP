from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

class DocumentMetadata(BaseModel):
    """
    Unified schema for document-level metadata.
    Stored as JSON in data/metadata/{doc_id}.json
    """
    doc_id: str = Field(..., description="MD5 hash of the PDF file content, unique per document")
    title: str = Field(..., description="Document title (required)")
    authors: Optional[List[str]] = Field(default_factory=list, description="List of authors")
    year: Optional[int] = Field(None, description="Year of publication")
    doc_type: Optional[str] = Field(
        None, description="Document type: book, paper, article, report, other"
    )
    tags: Optional[List[str]] = Field(default_factory=list, description="Optional thematic tags")
    ingested_at: datetime = Field(default_factory=datetime.utcnow, description="Ingestion timestamp")
    source_path: Optional[str] = Field(None, description="Relative path to original PDF file")

    # Pydantic v2: use field_validator instead of validator
    @field_validator("year")
    @classmethod
    def validate_year(cls, v):
        if v is not None and (v < 1000 or v > datetime.utcnow().year + 1):
            raise ValueError(f"Year {v} is out of valid range")
        return v

    @field_validator("doc_type")
    @classmethod
    def validate_doc_type(cls, v):
        allowed = [None, "book", "paper", "article", "report", "other"]
        if v not in allowed:
            raise ValueError(f"doc_type must be one of {allowed}, got {v}")
        return v

    class Config:
        extra = "forbid"
        validate_assignment = True
        json_schema_extra = {
            "example": {
                "doc_id": "f6a8d0e9...",
                "title": "Asymmetric Demography and the Global Economy",
                "authors": ["José María Fanelli"],
                "year": 2015,
                "doc_type": "book",
                "tags": ["demography", "macroeconomics"],
                "ingested_at": "2025-08-29T10:35:00",
                "source_path": "data/pdfs/Asymmetric_Demography.pdf"
            }
        }
