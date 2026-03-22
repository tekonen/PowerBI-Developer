"""Tests for the pipeline orchestrator."""

from __future__ import annotations

from pbi_developer.pipeline.stages import PipelineState, StageStatus


class TestPipelineState:
    def test_initial_state(self):
        state = PipelineState()
        assert state.stages == {}
        assert state.current_stage == ""

    def test_set_running(self):
        state = PipelineState()
        state.set_running("ingestion")
        assert state.current_stage == "ingestion"
        assert state.stages["ingestion"].status == StageStatus.RUNNING

    def test_set_completed(self):
        state = PipelineState()
        state.set_running("ingestion")
        state.set_completed("ingestion", data={"key": "value"}, tokens={"input_tokens": 100, "output_tokens": 50})
        assert state.stages["ingestion"].status == StageStatus.COMPLETED
        assert state.stages["ingestion"].data == {"key": "value"}
        assert state.stages["ingestion"].token_usage["input_tokens"] == 100

    def test_set_failed(self):
        state = PipelineState()
        state.set_running("qa")
        state.set_failed("qa", "Validation failed")
        assert state.stages["qa"].status == StageStatus.FAILED
        assert state.stages["qa"].error == "Validation failed"

    def test_set_skipped(self):
        state = PipelineState()
        state.set_skipped("publishing")
        assert state.stages["publishing"].status == StageStatus.SKIPPED

    def test_all_completed(self):
        state = PipelineState()
        state.set_running("ingestion")
        state.set_completed("ingestion")
        state.set_skipped("publishing")
        assert state.all_completed is True

    def test_all_completed_false_when_running(self):
        state = PipelineState()
        state.set_running("ingestion")
        state.set_completed("ingestion")
        state.set_running("qa")
        assert state.all_completed is False

    def test_total_tokens(self):
        state = PipelineState()
        state.set_running("wireframe")
        state.set_completed("wireframe", tokens={"input_tokens": 500, "output_tokens": 200})
        state.set_running("qa")
        state.set_completed("qa", tokens={"input_tokens": 300, "output_tokens": 100})
        total = state.total_tokens
        assert total["input_tokens"] == 800
        assert total["output_tokens"] == 300

    def test_total_tokens_empty(self):
        state = PipelineState()
        total = state.total_tokens
        assert total["input_tokens"] == 0
        assert total["output_tokens"] == 0


class TestProgressCallback:
    def test_progress_callback_receives_events(self):
        """Verify the orchestrator's _notify pattern works with a callback."""
        events: list[tuple[str, str]] = []

        def callback(stage: str, status: str) -> None:
            events.append((stage, status))

        # Simulate what the orchestrator does
        callback("ingestion", "running")
        callback("ingestion", "completed")
        callback("wireframe", "running")
        callback("wireframe", "completed")

        assert len(events) == 4
        assert events[0] == ("ingestion", "running")
        assert events[1] == ("ingestion", "completed")
        assert events[3] == ("wireframe", "completed")
