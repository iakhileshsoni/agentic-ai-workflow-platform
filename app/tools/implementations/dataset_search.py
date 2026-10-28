"""Local Dataset Search Tool.
Searches offline vector database records from data/fixtures/vector_databases.json.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.exceptions import ToolExecutionException
from app.tools.base import BaseTool, RiskTier, ToolPermission


class DatasetSearchInput(BaseModel):
    query: Optional[str] = Field(default=None, description="Keywords to match database name, features, or architecture")
    database_ids: Optional[List[str]] = Field(default=None, description="Specific database IDs, e.g. ['qdrant', 'milvus', 'pinecone']")
    limit: int = Field(default=5, ge=1, le=10, description="Maximum number of candidate records to return")


class VectorDatabaseRecord(BaseModel):
    id: str
    name: str
    license: str
    architecture: str
    indexing_algorithms: List[str]
    deployment_options: List[str]
    supported_distance_metrics: List[str]
    payload_filtering: str
    pricing_tier: Dict[str, str]
    strengths: List[str]
    trade_offs: List[str]


class DatasetSearchOutput(BaseModel):
    total_found: int
    returned_count: int
    databases: List[VectorDatabaseRecord]
    provenance: str = "data/fixtures/vector_databases.json"


class DatasetSearchTool(BaseTool):
    name = "dataset_search"
    description = "Retrieve structured capability, architecture, and pricing information for vector databases from the approved local dataset."
    input_schema = DatasetSearchInput
    output_schema = DatasetSearchOutput
    risk_tier = RiskTier.LOW
    requires_approval = False
    required_permission = ToolPermission.READ
    timeout_seconds = 10.0
    max_retries = 2
    is_idempotent = True

    def __init__(self, fixture_path: str = "data/fixtures/vector_databases.json"):
        self.fixture_path = Path(fixture_path)

    async def execute(self, arguments: DatasetSearchInput, context: Optional[Dict[str, Any]] = None) -> DatasetSearchOutput:
        if not self.fixture_path.exists():
            raise ToolExecutionException(
                f"Fixture dataset not found at {self.fixture_path}",
                is_recoverable=False
            )

        try:
            with open(self.fixture_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_dbs = data.get("vector_databases", [])
        except Exception as e:
            raise ToolExecutionException(f"Failed to load dataset: {str(e)}", is_recoverable=False)

        matches: List[Dict[str, Any]] = []

        for db in raw_dbs:
            # Filter by specific IDs if provided
            if arguments.database_ids:
                normalized_requested = [i.lower() for i in arguments.database_ids]
                if db["id"].lower() not in normalized_requested and db["name"].lower() not in normalized_requested:
                    continue

            # Filter by text query if provided
            if arguments.query:
                q = arguments.query.lower()
                blob = json.dumps(db).lower()
                if q not in blob:
                    continue

            matches.append(db)

        selected = matches[:arguments.limit]
        db_records = [VectorDatabaseRecord(**item) for item in selected]

        return DatasetSearchOutput(
            total_found=len(matches),
            returned_count=len(db_records),
            databases=db_records,
            provenance=str(self.fixture_path)
        )
