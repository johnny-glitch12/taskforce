"""
n8n → Task Force AI Native Schema Translator

Translates n8n workflow JSON into our React Flow native schema.
Maps n8n node types to our 8 canonical types: trigger, llm, condition,
action, http_request, webhook, database, transform.
"""
import hashlib
from typing import Dict, Any, List

# ── n8n type → Task Force canonical type ──
TYPE_MAP = {
    # Triggers
    "n8n-nodes-base.manualTrigger": "trigger",
    "n8n-nodes-base.cron": "trigger",
    "n8n-nodes-base.scheduleTrigger": "trigger",
    "n8n-nodes-base.emailReadImap": "trigger",
    "n8n-nodes-base.emailTrigger": "trigger",
    "n8n-nodes-base.start": "trigger",
    # Webhook
    "n8n-nodes-base.webhook": "webhook",
    "n8n-nodes-base.respondToWebhook": "webhook",
    # HTTP
    "n8n-nodes-base.httpRequest": "http_request",
    "n8n-nodes-base.httpRequestTool": "http_request",
    # Conditions
    "n8n-nodes-base.if": "condition",
    "n8n-nodes-base.switch": "condition",
    "n8n-nodes-base.filter": "condition",
    "n8n-nodes-base.merge": "condition",
    # Transforms
    "n8n-nodes-base.set": "transform",
    "n8n-nodes-base.function": "transform",
    "n8n-nodes-base.functionItem": "transform",
    "n8n-nodes-base.code": "transform",
    "n8n-nodes-base.itemLists": "transform",
    "n8n-nodes-base.aggregate": "transform",
    "n8n-nodes-base.splitInBatches": "transform",
    "n8n-nodes-base.dateTime": "transform",
    # LLM
    "n8n-nodes-base.openAi": "llm",
    "@n8n/n8n-nodes-langchain.openAi": "llm",
    "@n8n/n8n-nodes-langchain.chatOpenAi": "llm",
    "@n8n/n8n-nodes-langchain.lmChatOpenAi": "llm",
    "@n8n/n8n-nodes-langchain.lmChatGoogleGemini": "llm",
    "@n8n/n8n-nodes-langchain.lmChatAnthropic": "llm",
    "@n8n/n8n-nodes-langchain.agent": "llm",
    "@n8n/n8n-nodes-langchain.chainLlm": "llm",
    "n8n-nodes-base.googleGemini": "llm",
    # Database
    "n8n-nodes-base.postgres": "database",
    "n8n-nodes-base.mysql": "database",
    "n8n-nodes-base.mongoDb": "database",
    "n8n-nodes-base.redis": "database",
    "n8n-nodes-base.supabase": "database",
    "n8n-nodes-base.googleSheets": "database",
    "n8n-nodes-base.airtable": "database",
    "n8n-nodes-base.notion": "database",
}

# Action handlers (any messaging/email/api integration not above)
ACTION_PREFIXES = (
    "n8n-nodes-base.gmail", "n8n-nodes-base.slack", "n8n-nodes-base.discord",
    "n8n-nodes-base.telegram", "n8n-nodes-base.sendGrid", "n8n-nodes-base.mailgun",
    "n8n-nodes-base.twilio", "n8n-nodes-base.hubspot", "n8n-nodes-base.salesforce",
    "n8n-nodes-base.stripe", "n8n-nodes-base.googleDrive", "n8n-nodes-base.dropbox",
    "n8n-nodes-base.s3", "n8n-nodes-base.github", "n8n-nodes-base.gitlab",
    "n8n-nodes-base.jira", "n8n-nodes-base.linear", "n8n-nodes-base.asana",
    "n8n-nodes-base.trello", "n8n-nodes-base.shopify", "n8n-nodes-base.woocommerce",
)

LABEL_MAP = {
    "trigger": "Trigger",
    "llm": "LLM",
    "condition": "Condition",
    "action": "Action",
    "http_request": "HTTP Request",
    "webhook": "Webhook",
    "database": "Database",
    "transform": "Transform",
}

ICON_MAP = {
    "trigger": "Mail",
    "llm": "Brain",
    "condition": "Filter",
    "action": "FileText",
    "http_request": "Globe",
    "webhook": "Zap",
    "database": "Database",
    "transform": "Code",
}


def classify_node(n8n_type: str) -> str:
    """Map an n8n node type string to our canonical type."""
    if not n8n_type:
        return "action"
    if n8n_type in TYPE_MAP:
        return TYPE_MAP[n8n_type]
    if any(n8n_type.startswith(p) for p in ACTION_PREFIXES):
        return "action"
    # Heuristic fallbacks
    lower = n8n_type.lower()
    if "trigger" in lower or "webhook" in lower:
        return "webhook" if "webhook" in lower else "trigger"
    if "http" in lower or "request" in lower:
        return "http_request"
    if "llm" in lower or "openai" in lower or "gemini" in lower or "anthropic" in lower or "agent" in lower:
        return "llm"
    if "database" in lower or "postgres" in lower or "mysql" in lower or "mongo" in lower or "sheet" in lower:
        return "database"
    return "action"


def _short_name(n8n_type: str) -> str:
    """Extract a friendly node name from a fully-qualified n8n type."""
    if not n8n_type:
        return "Node"
    last = n8n_type.split(".")[-1]
    # camelCase → spaced
    out = ""
    for c in last:
        if c.isupper() and out:
            out += " "
        out += c
    return out.title()


def _extract_node_params(node: Dict[str, Any], canonical: str) -> Dict[str, Any]:
    """Extract relevant parameters from n8n node into our `data` shape."""
    params = node.get("parameters", {}) or {}
    out: Dict[str, Any] = {}

    if canonical == "http_request":
        out["method"] = params.get("method", "GET")
        out["url"] = params.get("url", "https://api.example.com")
        if "authentication" in params:
            out["auth"] = params["authentication"]
    elif canonical == "condition":
        # Try to extract condition expressions
        conds = params.get("conditions", {})
        if isinstance(conds, dict):
            out["condition"] = "complex_branch"
        elif isinstance(conds, list) and conds:
            out["condition"] = str(conds[0])[:200]
        else:
            out["condition"] = "true"
    elif canonical == "transform":
        if "jsCode" in params:
            out["code"] = "# Translated from n8n JS to safe placeholder\nRESULT = INPUT"
            out["original_js"] = str(params["jsCode"])[:1000]
        elif "values" in params:
            out["values"] = params["values"]
        out["code"] = out.get("code", "RESULT = INPUT")
    elif canonical == "llm":
        out["model"] = "gemini-2.5-flash"
        prompt = params.get("prompt") or params.get("text") or params.get("message")
        if prompt:
            out["prompt"] = str(prompt)[:500]
        else:
            out["prompt"] = "Analyze input and produce structured output."
        out["temperature"] = params.get("temperature", 0.3)
    elif canonical == "webhook":
        out["path"] = params.get("path", "/webhook")
        out["method"] = params.get("httpMethod", "POST")
        # Outbound webhook
        if params.get("url"):
            out["url"] = params["url"]
    elif canonical == "database":
        out["operation"] = params.get("operation", "read")
        out["table"] = params.get("table") or params.get("sheetName") or "data"
    elif canonical == "action":
        out["service"] = node.get("type", "external").split(".")[-1]
    elif canonical == "trigger":
        out["source"] = node.get("type", "manual").split(".")[-1]

    return out


def translate_workflow(n8n_json: Dict[str, Any], source_path: str = "") -> Dict[str, Any]:
    """
    Translate an n8n workflow JSON to Task Force native schema.

    Returns a dict ready to insert into MongoDB `n8n_templates` collection.
    """
    name = n8n_json.get("name", "Untitled Workflow")
    n8n_nodes = n8n_json.get("nodes", []) or []
    n8n_connections = n8n_json.get("connections", {}) or {}

    # Build name → id map for connection rewriting
    name_to_id: Dict[str, str] = {}
    nodes_out: List[Dict[str, Any]] = []

    for idx, node in enumerate(n8n_nodes):
        n8n_name = node.get("name", f"Node {idx}")
        n8n_type = node.get("type", "")
        canonical = classify_node(n8n_type)
        node_id = f"n_{idx}_{hashlib.md5(n8n_name.encode()).hexdigest()[:6]}"
        name_to_id[n8n_name] = node_id

        # Original n8n position [x, y] → scaled to our canvas
        pos = node.get("position", [60 + idx * 220, 100])
        x = float(pos[0]) if len(pos) > 0 else 60 + idx * 220
        y = float(pos[1]) if len(pos) > 1 else 100

        nodes_out.append({
            "id": node_id,
            "type": canonical,
            "label": LABEL_MAP[canonical],
            "sub": _short_name(n8n_type),
            "icon": ICON_MAP[canonical],
            "x": x,
            "y": y,
            "data": _extract_node_params(node, canonical),
            "_n8n_type": n8n_type,
        })

    # Rewrite connections — n8n stores as: { sourceName: { main: [[{node: targetName, ...}]] } }
    edges_out: List[Dict[str, Any]] = []
    seen_edges = set()
    for src_name, conns in n8n_connections.items():
        if not isinstance(conns, dict):
            continue
        main_conns = conns.get("main", [])
        for output_idx, targets in enumerate(main_conns):
            if not isinstance(targets, list):
                continue
            for t in targets:
                if not isinstance(t, dict):
                    continue
                tgt_name = t.get("node")
                src_id = name_to_id.get(src_name)
                tgt_id = name_to_id.get(tgt_name)
                if src_id and tgt_id:
                    key = f"{src_id}->{tgt_id}"
                    if key not in seen_edges:
                        seen_edges.add(key)
                        edges_out.append({"from": src_id, "to": tgt_id})

    # Re-layout: if no positions or all at origin, auto-layout left-to-right
    if all(n["x"] == 0 and n["y"] == 0 for n in nodes_out) or not nodes_out:
        for i, n in enumerate(nodes_out):
            n["x"] = 60 + i * 240
            n["y"] = 120

    # Normalize positions so left-most is at 60
    if nodes_out:
        min_x = min(n["x"] for n in nodes_out)
        min_y = min(n["y"] for n in nodes_out)
        for n in nodes_out:
            n["x"] = max(0, n["x"] - min_x + 60)
            n["y"] = max(0, n["y"] - min_y + 80)

    # Trust score heuristic
    nc = len(nodes_out)
    if nc == 0:
        complexity = "low"
    elif nc < 5:
        complexity = "low"
    elif nc < 12:
        complexity = "med"
    else:
        complexity = "high"

    trust_score = min(95, 60 + nc * 2 + (10 if len(edges_out) > 0 else 0))

    # Source hash for idempotency
    src_hash = hashlib.md5(
        (name + str(nc) + str(len(edges_out)) + source_path).encode()
    ).hexdigest()

    description = n8n_json.get("description") or _generate_description(name, nodes_out)

    return {
        "source_hash": src_hash,
        "name": name,
        "description": description,
        "source": "n8n-template",
        "source_path": source_path,
        "node_count": nc,
        "edge_count": len(edges_out),
        "complexity": complexity,
        "trust_score": trust_score,
        "nodes": nodes_out,
        "edges": edges_out,
    }


def _generate_description(name: str, nodes: List[Dict[str, Any]]) -> str:
    """Generate a one-line description from the workflow shape."""
    if not nodes:
        return f"{name}: empty workflow."
    types = [n["label"] for n in nodes[:5]]
    return f"{name}: {' → '.join(types)}{' → ...' if len(nodes) > 5 else ''}"
