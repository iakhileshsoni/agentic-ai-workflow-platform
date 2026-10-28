"""LLM Adapter Module.
Connects to local Ollama runtime and provides seamless deterministic fallback when offline.
"""
import json
import logging
from typing import Any, Dict, Optional
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.schemas.plan import ExecutionPlan, PlanStep


class LLMAdapter:
    """Dispatches prompts to local Ollama runtime with zero-downtime mock fallback."""

    def __init__(
        self,
        base_url: str = settings.OLLAMA_BASE_URL,
        model: str = settings.LLM_MODEL,
        timeout: float = settings.LLM_TIMEOUT_SECONDS,
        fallback_mock: bool = settings.LLM_FALLBACK_MOCK,
    ):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.fallback_mock = fallback_mock

    async def is_available(self) -> bool:
        """Check if local Ollama daemon is reachable."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def generate_plan(self, objective: str, tool_catalog_summary: str) -> ExecutionPlan:
        """Generate structured plan via Ollama or deterministic fallback."""
        if await self.is_available():
            try:
                plan = await self._call_ollama_for_plan(objective, tool_catalog_summary)
                if plan:
                    return plan
            except Exception as e:
                logger.warning(f"Ollama call failed ({e}); falling back to deterministic planner")

        if self.fallback_mock:
            return self._generate_deterministic_mock_plan(objective)

        raise RuntimeError("Local LLM is unavailable and fallback mock is disabled.")

    async def _call_ollama_for_plan(self, objective: str, tool_catalog: str) -> Optional[ExecutionPlan]:
        """Send planning prompt to Ollama with format='json'."""
        prompt = (
            f"You are a workflow planner. Plan this objective: '{objective}'.\n"
            f"Available tools:\n{tool_catalog}\n"
            "Respond ONLY with a JSON object matching this schema:\n"
            "{\n"
            '  "objective": "...",\n'
            '  "steps": [\n'
            '    {\n'
            '      "step_id": "step_1",\n'
            '      "step_name": "...",\n'
            '      "tool_name": "...",\n'
            '      "arguments": {},\n'
            '      "dependencies": [],\n'
            '      "expected_output": "...",\n'
            '      "requires_approval": false\n'
            "    }\n"
            "  ],\n"
            '  "constraints": {},\n'
            '  "rationale": "..."\n'
            "}"
        )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_ctx": 4096,
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(f"{self.base_url}/api/generate", json=payload)
            if res.status_code == 200:
                raw_json = res.json().get("response", "{}")
                data = json.loads(raw_json)
                return ExecutionPlan.model_validate(data)

        return None

    def _generate_deterministic_mock_plan(self, objective: str) -> ExecutionPlan:
        """Deterministic, grounded plan generator for offline testability."""
        obj_lower = objective.lower()

        # Vector Database research demonstration scenario
        if "vector" in obj_lower or "database" in obj_lower or "research" in obj_lower:
            return ExecutionPlan(
                objective=objective,
                steps=[
                    PlanStep(
                        step_id="step_1",
                        step_name="Retrieve Vector DB Specifications",
                        tool_name="dataset_search",
                        arguments={
                            "database_ids": ["qdrant", "milvus", "pinecone"],
                            "limit": 3
                        },
                        dependencies=[],
                        expected_output="Capability, architecture, and pricing records for Qdrant, Milvus, and Pinecone",
                        requires_approval=False
                    ),
                    PlanStep(
                        step_id="step_2",
                        step_name="Retrieve Benchmark Latency and Throughput",
                        tool_name="doc_search",
                        arguments={
                            "query": "latency and throughput performance",
                            "top_k": 3
                        },
                        dependencies=[],
                        expected_output="Verified empirical latency and QPS benchmark metrics",
                        requires_approval=False
                    ),
                    PlanStep(
                        step_id="step_3",
                        step_name="Construct Feature and Trade-off Comparison Matrix",
                        tool_name="comparison",
                        arguments={
                            "candidates": "{{step_1.databases}}",
                            "criteria": ["license", "deployment_options", "supported_distance_metrics", "pricing_tier", "strengths", "trade_offs"]
                        },
                        dependencies=["step_1"],
                        expected_output="Normalized comparison matrix and trade-off synthesis",
                        requires_approval=False
                    ),
                    PlanStep(
                        step_id="step_4",
                        step_name="Validate Evidence Completeness",
                        tool_name="result_validator",
                        arguments={
                            "step_outputs": "{{all_outputs}}",
                            "required_fields": ["matrix", "metrics"],
                            "min_evidence_items": 3
                        },
                        dependencies=["step_2", "step_3"],
                        expected_output="Verification confirmation that all required research evidence is present",
                        requires_approval=False
                    ),
                    PlanStep(
                        step_id="step_5",
                        step_name="Synthesize Final Research and Recommendation Report",
                        tool_name="report_generator",
                        arguments={
                            "objective": objective,
                            "comparison_data": "{{step_3}}",
                            "benchmark_data": "{{step_2}}"
                        },
                        dependencies=["step_4"],
                        expected_output="Complete executive Markdown recommendation report",
                        requires_approval=False
                    )
                ],
                constraints={"max_steps": 5, "timeout_seconds": 120.0},
                rationale="Multi-step research pipeline: dataset extraction -> benchmark lookup -> matrix normalization -> evidence validation -> report generation."
            )

        # Simple Arithmetic / Calculator scenario
        if "calculate" in obj_lower or "add" in obj_lower or "multiply" in obj_lower or "math" in obj_lower:
            return ExecutionPlan(
                objective=objective,
                steps=[
                    PlanStep(
                        step_id="step_1",
                        step_name="Compute Arithmetic Operation",
                        tool_name="calculator",
                        arguments={"operation": "multiply", "a": 42.0, "b": 10.0},
                        dependencies=[],
                        expected_output="Mathematical calculation result",
                        requires_approval=False
                    )
                ],
                constraints={"max_steps": 1},
                rationale="Direct deterministic calculator execution."
            )

        # Default fallback general plan
        return ExecutionPlan(
            objective=objective,
            steps=[
                PlanStep(
                    step_id="step_1",
                    step_name="Query Approved Data Store",
                    tool_name="dataset_search",
                    arguments={"limit": 2},
                    dependencies=[],
                    expected_output="Matching dataset records",
                    requires_approval=False
                )
            ],
            constraints={"max_steps": 1},
            rationale="Single step search fallback."
        )


llm_adapter = LLMAdapter()
