"""Security Tests for Approval Integrity and Tamper Resistance."""
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from app.approvals.service import ApprovalService
from app.core.exceptions import PlatformException
from app.core.security import compute_operation_hash
from app.db.session import AsyncSessionLocal
from app.schemas.approval import ApprovalDecision, ApprovalDecisionRequest


@pytest.mark.asyncio
async def test_double_approval_decision_rejected():
    task_id = str(uuid.uuid4())
    approval_id = str(uuid.uuid4())
    expiry = datetime.now(timezone.utc) + timedelta(minutes=10)

    async with AsyncSessionLocal() as session:
        service = ApprovalService(session)
        # Create approval record
        await service.repo.create_request(
            approval_id=approval_id,
            task_id=task_id,
            step_id="step_1",
            tool_name="sensitive_export_action",
            operation_hash="fake-hash-01",
            payload_summary={"target": "slack"},
            risk_level="CRITICAL",
            reason="Test",
            expires_at=expiry
        )

        # 1. First decision succeeds
        req = ApprovalDecisionRequest(decision=ApprovalDecision.APPROVED)
        res = await service.submit_decision(approval_id, req, "admin-user")
        assert res.decision == ApprovalDecision.APPROVED

        # 2. Duplicate decision attempt must be rejected
        with pytest.raises(PlatformException) as exc_info:
            await service.submit_decision(approval_id, req, "another-user")
        assert "already" in exc_info.value.message.lower()


def test_operation_hash_changes_if_arguments_are_tampered():
    task_id = "task-123"
    tool_name = "sensitive_export_action"

    args_legit = {"action": "export", "destination": "s3://internal-archive"}
    args_tampered = {"action": "export", "destination": "s3://public-leak-bucket"}

    hash_legit = compute_operation_hash(tool_name, args_legit, task_id)
    hash_tampered = compute_operation_hash(tool_name, args_tampered, task_id)

    # Hashes must differ, preventing argument substitution
    assert hash_legit != hash_tampered
