"""Unit tests for the n8n → Task Force native schema translator."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.n8n_translator import translate_workflow, classify_node


def test_classify_known_types():
    assert classify_node("n8n-nodes-base.webhook") == "webhook"
    assert classify_node("n8n-nodes-base.httpRequest") == "http_request"
    assert classify_node("n8n-nodes-base.if") == "condition"
    assert classify_node("n8n-nodes-base.set") == "transform"
    assert classify_node("@n8n/n8n-nodes-langchain.lmChatOpenAi") == "llm"
    assert classify_node("n8n-nodes-base.postgres") == "database"
    assert classify_node("n8n-nodes-base.gmail") == "action"
    assert classify_node("n8n-nodes-base.scheduleTrigger") == "trigger"
    print("[ok] classify_known_types")


def test_classify_unknown_heuristic():
    # Anything unrecognized falls to action by default
    assert classify_node("custom.foobar") == "action"
    # But generic keywords still match
    assert classify_node("custom.openaiThing") == "llm"
    print("[ok] classify_unknown_heuristic")


def test_translate_simple_workflow():
    n8n = {
        "name": "Simple Test",
        "nodes": [
            {"name": "Webhook", "type": "n8n-nodes-base.webhook", "parameters": {"path": "/in"}, "position": [0, 0]},
            {"name": "Transform", "type": "n8n-nodes-base.set", "parameters": {}, "position": [220, 0]},
            {"name": "Send", "type": "n8n-nodes-base.httpRequest", "parameters": {"url": "https://api.example.com", "method": "POST"}, "position": [440, 0]},
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Transform"}]]},
            "Transform": {"main": [[{"node": "Send"}]]},
        },
    }
    out = translate_workflow(n8n, source_path="test/simple.json")
    assert out["name"] == "Simple Test"
    assert out["node_count"] == 3
    assert out["edge_count"] == 2
    assert out["nodes"][0]["type"] == "webhook"
    assert out["nodes"][1]["type"] == "transform"
    assert out["nodes"][2]["type"] == "http_request"
    assert out["nodes"][2]["data"]["url"] == "https://api.example.com"
    # Verify edges reference our internal node IDs
    src = out["nodes"][0]["id"]
    tgt = out["nodes"][1]["id"]
    assert any(e["from"] == src and e["to"] == tgt for e in out["edges"])
    print("[ok] translate_simple_workflow")


def test_translate_empty():
    out = translate_workflow({"name": "Empty", "nodes": [], "connections": {}})
    assert out["node_count"] == 0
    assert out["edge_count"] == 0
    print("[ok] translate_empty")


def test_translate_real_template():
    """Translate one of the real ingested templates as smoke test."""
    p = Path("/tmp/awesome-n8n-templates")
    if not p.exists():
        print("[skip] no local clone available")
        return
    sample = next(p.rglob("*.json"), None)
    if not sample:
        print("[skip] no sample found")
        return
    import json
    with open(sample) as f:
        n8n = json.load(f)
    if not isinstance(n8n, dict) or "nodes" not in n8n:
        print("[skip] non-workflow file")
        return
    out = translate_workflow(n8n, source_path=str(sample.name))
    assert "nodes" in out and isinstance(out["nodes"], list)
    assert "edges" in out and isinstance(out["edges"], list)
    print(f"[ok] translate_real_template: {out['name']} → {out['node_count']} nodes")


if __name__ == "__main__":
    test_classify_known_types()
    test_classify_unknown_heuristic()
    test_translate_simple_workflow()
    test_translate_empty()
    test_translate_real_template()
    print("\n[ALL TRANSLATOR TESTS PASSED]")
