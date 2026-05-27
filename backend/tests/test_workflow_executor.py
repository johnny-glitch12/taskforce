"""Integration tests for native workflow executor."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routes.workflow_executor import execute_workflow_dag, topological_sort


def test_topological_sort_simple():
    nodes = [
        {"id": "a", "type": "trigger"},
        {"id": "b", "type": "transform"},
        {"id": "c", "type": "webhook"},
    ]
    edges = [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}]
    order = topological_sort(nodes, edges)
    ids = [n["id"] for n in order]
    assert ids == ["a", "b", "c"], f"Expected a,b,c got {ids}"
    print("[ok] topological_sort_simple")


def test_topological_sort_cycle():
    from fastapi import HTTPException
    nodes = [{"id": "a", "type": "trigger"}, {"id": "b", "type": "transform"}]
    edges = [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}]
    try:
        topological_sort(nodes, edges)
        raise AssertionError("Should have raised on cycle")
    except HTTPException as e:
        assert e.status_code == 400
        print("[ok] topological_sort_cycle_detected")


async def test_execute_transform_pipeline():
    wf = {
        "nodes": [
            {"id": "t1", "type": "trigger", "data": {"payload": {"x": 5}}},
            {"id": "tr1", "type": "transform", "data": {"code": "RESULT = {'doubled': INPUT['x'] * 2}"}},
        ],
        "edges": [{"from": "t1", "to": "tr1"}],
    }
    result = await execute_workflow_dag(wf)
    assert result["success"] is True, f"Expected success, got {result}"
    assert result["final_output"] == {"doubled": 10}, f"Got {result['final_output']}"
    print("[ok] execute_transform_pipeline:", result["final_output"])


async def test_execute_condition_branch():
    wf = {
        "nodes": [
            {"id": "t1", "type": "trigger", "data": {"payload": {"score": 80}}},
            {"id": "c1", "type": "condition", "data": {"condition": "INPUT.get('score', 0) > 50"}},
        ],
        "edges": [{"from": "t1", "to": "c1"}],
    }
    result = await execute_workflow_dag(wf)
    assert result["success"] is True
    cond_result = next(r for r in result["node_results"] if r["type"] == "condition")
    assert cond_result["branch"] == "true", f"Expected true branch, got {cond_result}"
    print("[ok] execute_condition_branch:", cond_result["branch"])


async def test_execute_http_ssrf_block():
    """Verify SSRF protection blocks private IP HTTP requests."""
    wf = {
        "nodes": [
            {"id": "t1", "type": "trigger"},
            {"id": "h1", "type": "http_request", "data": {"url": "http://localhost:22", "method": "GET"}},
        ],
        "edges": [{"from": "t1", "to": "h1"}],
    }
    result = await execute_workflow_dag(wf)
    # Should fail at the http node due to SSRF
    http_res = next(r for r in result["node_results"] if r["type"] == "http_request")
    assert http_res["status"] == "error", f"SSRF should be blocked, got {http_res}"
    assert "blocked" in http_res["log"].lower() or "ssrf" in http_res["log"].lower()
    print("[ok] execute_http_ssrf_block:", http_res["log"])


async def test_empty_workflow():
    result = await execute_workflow_dag({"nodes": [], "edges": []})
    assert result["success"] is False
    print("[ok] execute_empty_workflow_rejected")


async def main():
    test_topological_sort_simple()
    test_topological_sort_cycle()
    await test_execute_transform_pipeline()
    await test_execute_condition_branch()
    await test_execute_http_ssrf_block()
    await test_empty_workflow()
    print("\n[ALL TESTS PASSED]")


if __name__ == "__main__":
    asyncio.run(main())
