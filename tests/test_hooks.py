"""
tests/test_hooks.py

Tests for infra/hooks/pre_tool_use.py and infra/hooks/post_tool_use.py

The hooks are the last enforcement layer before tool execution.
A regression here means governance controls can be bypassed without detection.
These tests verify that the blocks fire correctly and that the fallback
(never crash, always allow) invariant is maintained.
"""

import sys
import os
import pytest

# Hooks import from project root — ensure it is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from infra.hooks import pre_tool_use, post_tool_use


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _event(tool: str, **inputs) -> dict:
    return {"tool": tool, "inputs": inputs}


# ---------------------------------------------------------------------------
# pre_tool_use — publication gate
# ---------------------------------------------------------------------------

class TestPublicationGate:

    PUBLISH_TOOLS = [
        "publish_artifact",
        "send_to_portal",
        "distribute_document",
        "export_document",
        "email_document",
        "upload_to_dataroom",
    ]

    def test_publish_tool_blocked_when_mock(self):
        for tool in self.PUBLISH_TOOLS:
            result = pre_tool_use.handle(_event(tool, is_mock=True, draft_approved=True, approval_status="approved"))
            assert result["action"] == "block", f"{tool} should be blocked when is_mock=True"

    def test_publish_tool_blocked_when_not_approved(self):
        result = pre_tool_use.handle(_event(
            "publish_artifact",
            is_mock=False,
            draft_approved=False,
        ))
        assert result["action"] == "block"

    def test_publish_tool_blocked_external_without_approval_id(self):
        result = pre_tool_use.handle(_event(
            "publish_artifact",
            is_mock=False,
            draft_approved=True,
            approval_status="approved",
            target_channel="external",
            # no approval_id
        ))
        assert result["action"] == "block"

    def test_publish_tool_allowed_internal_approved_not_mock(self):
        result = pre_tool_use.handle(_event(
            "publish_artifact",
            is_mock=False,
            draft_approved=True,
            approval_status="approved",
            target_channel="internal",
        ))
        assert result["action"] == "allow"

    def test_publish_tool_allowed_external_with_approval_id(self):
        result = pre_tool_use.handle(_event(
            "publish_artifact",
            is_mock=False,
            draft_approved=True,
            approval_status="approved",
            target_channel="external",
            approval_id="appr-abc123",
        ))
        assert result["action"] == "allow"

    def test_non_publish_tool_not_intercepted_by_publication_gate(self):
        """Read tool should not hit publication gate at all."""
        result = pre_tool_use.handle(_event("Read", file_path="data/samples/sample_deal_inputs.json"))
        assert result["action"] == "allow"


# ---------------------------------------------------------------------------
# pre_tool_use — audit log protection
# ---------------------------------------------------------------------------

class TestAuditLogProtection:

    def test_rm_audit_log_blocked(self):
        result = pre_tool_use.handle(_event("Bash", command="rm data/audit_log.jsonl"))
        assert result["action"] == "block"

    def test_redirect_truncate_audit_log_blocked(self):
        result = pre_tool_use.handle(_event("Bash", command="> data/audit_log.jsonl"))
        assert result["action"] == "block"

    def test_truncate_audit_log_blocked(self):
        result = pre_tool_use.handle(_event("Bash", command="truncate -s 0 audit_log.jsonl"))
        assert result["action"] == "block"

    def test_safe_bash_command_allowed(self):
        result = pre_tool_use.handle(_event("Bash", command="ls data/"))
        assert result["action"] == "allow"

    def test_audit_log_append_is_allowed(self):
        """Appending to the log (>>) is safe and must not be blocked."""
        result = pre_tool_use.handle(_event("Bash", command="echo '{}' >> data/audit_log.jsonl"))
        assert result["action"] == "allow"


# ---------------------------------------------------------------------------
# pre_tool_use — bash safety gate
# ---------------------------------------------------------------------------

class TestBashSafetyGate:

    def test_rm_rf_blocked(self):
        result = pre_tool_use.handle(_event("Bash", command="rm -rf /tmp/test"))
        assert result["action"] == "block"

    def test_rm_rfv_blocked(self):
        result = pre_tool_use.handle(_event("Bash", command="rm -rfv /tmp/test"))
        assert result["action"] == "block"

    def test_git_push_force_blocked(self):
        result = pre_tool_use.handle(_event("Bash", command="git push origin main --force"))
        assert result["action"] == "block"

    def test_git_reset_hard_blocked(self):
        result = pre_tool_use.handle(_event("Bash", command="git reset --hard HEAD~1"))
        assert result["action"] == "block"

    def test_chmod_777_blocked(self):
        result = pre_tool_use.handle(_event("Bash", command="chmod 777 /etc/passwd"))
        assert result["action"] == "block"

    def test_sudo_blocked(self):
        result = pre_tool_use.handle(_event("Bash", command="sudo apt install curl"))
        assert result["action"] == "block"

    def test_safe_git_status_allowed(self):
        result = pre_tool_use.handle(_event("Bash", command="git status"))
        assert result["action"] == "allow"

    def test_safe_pytest_allowed(self):
        result = pre_tool_use.handle(_event("Bash", command="python3 -m pytest tests/"))
        assert result["action"] == "allow"


# ---------------------------------------------------------------------------
# pre_tool_use — file write safety
# ---------------------------------------------------------------------------

class TestFileWriteSafety:

    def test_write_env_blocked(self):
        result = pre_tool_use.handle(_event("Write", file_path=".env"))
        assert result["action"] == "block"

    def test_write_env_local_blocked(self):
        result = pre_tool_use.handle(_event("Write", file_path=".env.local"))
        assert result["action"] == "block"

    def test_write_nested_env_blocked(self):
        result = pre_tool_use.handle(_event("Write", file_path="config/.env"))
        assert result["action"] == "block"

    def test_write_audit_log_blocked(self):
        result = pre_tool_use.handle(_event("Write", file_path="data/audit_log.jsonl"))
        assert result["action"] == "block"

    def test_edit_audit_log_blocked(self):
        result = pre_tool_use.handle(_event("Edit", file_path="data/audit_log.jsonl"))
        assert result["action"] == "block"

    def test_write_normal_file_allowed(self):
        result = pre_tool_use.handle(_event("Write", file_path="app/services/new_service.py"))
        assert result["action"] == "allow"

    def test_write_docs_allowed(self):
        result = pre_tool_use.handle(_event("Write", file_path="docs/new-doc.md"))
        assert result["action"] == "allow"


# ---------------------------------------------------------------------------
# pre_tool_use — hook error invariant
# ---------------------------------------------------------------------------

class TestHookErrorInvariant:

    def test_malformed_event_does_not_crash(self):
        """Hook must not raise; must return allow on any exception."""
        result = pre_tool_use.handle({"tool": None, "inputs": None})
        assert result["action"] == "allow"

    def test_empty_event_does_not_crash(self):
        result = pre_tool_use.handle({})
        assert result["action"] == "allow"

    def test_result_always_has_checks_list(self):
        result = pre_tool_use.handle(_event("Read", file_path="docs/README.md"))
        assert "checks" in result
        assert isinstance(result["checks"], list)


# ---------------------------------------------------------------------------
# post_tool_use — provenance tagging
# ---------------------------------------------------------------------------

class TestPostToolUseProvenance:

    def _run(self, tool: str, outputs=None) -> dict:
        event = {"tool": tool, "inputs": {}, "outputs": outputs or {}}
        return post_tool_use.handle(event)

    def test_always_returns_continue(self):
        result = self._run("Read")
        assert result["action"] == "continue"

    def test_known_engine_tool_gets_calculated_tag(self):
        from infra.hooks.post_tool_use import _resolve_provenance
        assert _resolve_provenance("cashflow_engine_run") == "[calculated]"
        assert _resolve_provenance("run_scenario") == "[calculated]"
        assert _resolve_provenance("get_scenario_result") == "[calculated]"

    def test_data_retrieval_gets_retrieved_tag(self):
        from infra.hooks.post_tool_use import _resolve_provenance
        assert _resolve_provenance("get_pool_data") == "[retrieved]"
        assert _resolve_provenance("Read") == "[retrieved]"

    def test_drafting_tools_get_generated_tag(self):
        from infra.hooks.post_tool_use import _resolve_provenance
        assert _resolve_provenance("draft_investor_summary") == "[generated]"
        assert _resolve_provenance("generate_summary") == "[generated]"
        assert _resolve_provenance("compose_ic_memo") == "[generated]"

    def test_internal_tools_get_internal_tag(self):
        from infra.hooks.post_tool_use import _resolve_provenance
        assert _resolve_provenance("Bash") == "[internal]"
        assert _resolve_provenance("Write") == "[internal]"
        assert _resolve_provenance("Edit") == "[internal]"

    def test_unknown_tool_gets_unknown_tag(self):
        from infra.hooks.post_tool_use import _resolve_provenance
        assert _resolve_provenance("some_exotic_tool_xyz") == "[unknown]"

    def test_prefix_match_cashflow_engine(self):
        from infra.hooks.post_tool_use import _resolve_provenance
        assert _resolve_provenance("cashflow_engine_v2_run") == "[calculated]"

    def test_prefix_match_get_portfolio(self):
        from infra.hooks.post_tool_use import _resolve_provenance
        assert _resolve_provenance("get_portfolio_metrics") == "[retrieved]"


# ---------------------------------------------------------------------------
# post_tool_use — mock detection
# ---------------------------------------------------------------------------

class TestPostToolUseMockDetection:

    def test_detects_mock_at_top_level(self):
        from infra.hooks.post_tool_use import _detect_mock
        assert _detect_mock({"_mock": "MOCK_ENGINE_OUTPUT", "equity_irr": 0.14}) is True

    def test_detects_mock_one_level_deep(self):
        from infra.hooks.post_tool_use import _detect_mock
        assert _detect_mock({"outputs": {"_mock": "MOCK_ENGINE_OUTPUT"}}) is True

    def test_no_mock_when_absent(self):
        from infra.hooks.post_tool_use import _detect_mock
        assert _detect_mock({"equity_irr": 0.14}) is False

    def test_no_mock_for_non_dict(self):
        from infra.hooks.post_tool_use import _detect_mock
        assert _detect_mock("string output") is False
        assert _detect_mock(None) is False


# ---------------------------------------------------------------------------
# post_tool_use — anomaly detection
# ---------------------------------------------------------------------------

class TestPostToolUseAnomalyDetection:

    def test_engine_none_output_flagged(self):
        from infra.hooks.post_tool_use import _detect_anomaly
        result = _detect_anomaly("cashflow_engine_run", None)
        assert result != ""

    def test_engine_empty_outputs_flagged(self):
        from infra.hooks.post_tool_use import _detect_anomaly
        result = _detect_anomaly("run_scenario", {"outputs": {}})
        assert result != ""

    def test_engine_with_valid_outputs_no_anomaly(self):
        from infra.hooks.post_tool_use import _detect_anomaly
        result = _detect_anomaly("cashflow_engine_run", {"outputs": {"equity_irr": 0.14}})
        assert result == ""

    def test_read_none_output_flagged(self):
        from infra.hooks.post_tool_use import _detect_anomaly
        result = _detect_anomaly("Read", None)
        assert result != ""

    def test_non_engine_tool_none_output_not_flagged(self):
        from infra.hooks.post_tool_use import _detect_anomaly
        result = _detect_anomaly("Bash", None)
        assert result == ""
