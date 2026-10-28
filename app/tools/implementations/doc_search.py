"""Local Document and Benchmark Search Tool.
Searches offline technical benchmark documentation from data/fixtures/technical_benchmarks.json.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.exceptions import ToolExecutionException
from app.tools.base import BaseTool, RiskTier, ToolPermission


class DocSearchInput(BaseModel):
    query: str = Field(..., description="Query for benchmark metrics (latency, QPS, RAM, candidate name)")
    top_k: int = Field(default=3, ge=1, le=10, description="Max benchmark results")


class BenchmarkMetric(BaseModel):
    candidate: str
    p99_latency_ms: Optional[float]
    throughput_qps: Optional[int]
    ram_usage_gb_uncompressed: Optional[float]
    ram_usage_gb_quantized: Optional[float]
    build_time_minutes: Optional[int]


class DocSearchOutput(BaseModel):
    query: str
    environment: str
    metrics: List[BenchmarkMetric]
    provenance: str = "data/fixtures/technical_benchmarks.json"


class DocSearchTool(BaseTool):
    name = "doc_search"
    description = "Search verified technical performance benchmarks (latency, QPS, memory usage) for vector databases."
    input_schema = DocSearchInput
    output_schema = DocSearchOutput
    risk_tier = RiskTier.LOW
    requires_approval = False
    required_permission = ToolPermission.READ
    timeout_seconds = 10.0
    max_retries = 2
    is_idempotent = True

    def __init__(self, fixture_path: str = "data/fixtures/technical_benchmarks.json"):
        self.fixture_path = Path(fixture_path)

    async def execute(self, arguments: DocSearchInput, context: Optional[Dict[str, Any]] = None) -> DocSearchOutput:
        if not self.fixture_path.exists():
            raise ToolExecutionException(
                f"Benchmark fixture not found at {self.fixture_path}",
                is_recoverable=False
            )

        try:
            with open(self.fixture_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            bench = data.get("benchmarks", {})
            env = bench.get("benchmark_environment", "Local Reference Hardware")
            raw_metrics = bench.get("metrics", [])
        except Exception as e:
            raise ToolExecutionException(f"Failed to read benchmark fixture: {str(e)}", is_recoverable=False)

        q_tokens = [w for w in arguments.query.lower().split() if len(w) > 2]
        matched = []
        for m in raw_metrics:
            c_name = m["candidate"].lower()
            if not q_tokens:
                matched.append(m)
            elif any(t in c_name or t in ["latency", "qps", "ram", "performance", "benchmark", "benchmarks", "speed", "metrics"] for t in q_tokens):
                matched.append(m)

        # Fallback to returning all if no specific match
        if not matched:
            matched = raw_metrics

        selected = matched[:arguments.top_k]
        result_metrics = [BenchmarkMetric(**m) for m in selected]

        return DocSearchOutput(
            query=arguments.query,
            environment=env,
            metrics=result_metrics,
            provenance=str(self.fixture_path)
        )
