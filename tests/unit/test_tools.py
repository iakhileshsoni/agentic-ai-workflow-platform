"""Unit Tests for Typed Local Tools."""
import pytest
from app.tools.implementations.calculator import CalculatorTool, CalculatorInput, CalcOperation
from app.tools.implementations.dataset_search import DatasetSearchTool, DatasetSearchInput
from app.tools.implementations.doc_search import DocSearchTool, DocSearchInput
from app.tools.implementations.comparison import ComparisonTool, ComparisonInput
from app.tools.implementations.report_generator import ReportGeneratorTool, ReportGeneratorInput
from app.tools.implementations.validator import ResultValidatorTool, ValidatorInput


@pytest.mark.asyncio
async def test_calculator_tool_operations():
    tool = CalculatorTool()

    # Addition
    res_add = await tool.execute(CalculatorInput(operation=CalcOperation.ADD, a=15.5, b=4.5))
    assert res_add.result == 20.0

    # Multiplication
    res_mul = await tool.execute(CalculatorInput(operation=CalcOperation.MULTIPLY, a=6.0, b=7.0))
    assert res_mul.result == 42.0

    # Percentage
    res_pct = await tool.execute(CalculatorInput(operation=CalcOperation.PERCENTAGE, a=25.0, b=100.0))
    assert res_pct.result == 25.0


@pytest.mark.asyncio
async def test_dataset_search_tool():
    tool = DatasetSearchTool(fixture_path="data/fixtures/vector_databases.json")

    # Search for specific candidates
    res = await tool.execute(DatasetSearchInput(database_ids=["qdrant", "milvus", "pinecone"]))
    assert res.returned_count == 3
    names = [db.name for db in res.databases]
    assert "Qdrant" in names
    assert "Milvus" in names
    assert "Pinecone" in names


@pytest.mark.asyncio
async def test_doc_search_tool():
    tool = DocSearchTool(fixture_path="data/fixtures/technical_benchmarks.json")

    res = await tool.execute(DocSearchInput(query="latency benchmark", top_k=3))
    assert len(res.metrics) > 0
    assert any(m.candidate == "Qdrant" for m in res.metrics)


@pytest.mark.asyncio
async def test_comparison_tool():
    tool = ComparisonTool()

    candidates = [
        {"name": "Qdrant", "license": "Apache 2.0", "trade_offs": ["Manual clustering"]},
        {"name": "Pinecone", "license": "Proprietary", "trade_offs": ["Cloud only"]}
    ]

    res = await tool.execute(ComparisonInput(candidates=candidates))
    assert len(res.candidate_names) == 2
    assert "Qdrant" in res.trade_off_summary
    assert "Pinecone" in res.trade_off_summary


@pytest.mark.asyncio
async def test_validator_tool():
    tool = ResultValidatorTool()

    step_outputs = {
        "step_1": {"databases": [{"name": "Qdrant"}]},
        "step_2": {"matrix": [{"feature": "license"}]}
    }

    # Pass case
    res_pass = await tool.execute(ValidatorInput(
        step_outputs=step_outputs,
        required_fields=["databases", "matrix"],
        min_evidence_items=2
    ))
    assert res_pass.is_valid is True
    assert len(res_pass.missing_fields) == 0

    # Fail case (missing field)
    res_fail = await tool.execute(ValidatorInput(
        step_outputs=step_outputs,
        required_fields=["databases", "nonexistent_field"],
        min_evidence_items=2
    ))
    assert res_fail.is_valid is False
    assert "nonexistent_field" in res_fail.missing_fields
