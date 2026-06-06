"""
seed_official_agents — idempotent inserter for the 5 day-one Exchange agents.

For each AGENT entry in seeds.official_agents:
  1. upsert a `bot_projects` document (creator = owner admin) with the Python
     files and a hand-tuned node graph
  2. upsert a `exchange_listings` document marked `is_official=True` and
     `status='published'` pointing at the bot_project as `source_project_id`

Run:
  python -m backend.scripts.seed_official_agents
  python -m backend.scripts.seed_official_agents --dry-run

Owner is selected by email — falls back to first user with is_owner=True
or is_admin=True. Override with --owner-email foo@bar.com.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from motor.motor_asyncio import AsyncIOMotorClient

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

from seeds.official_agents import AGENTS  # noqa: E402


_DASHBOARDS = {
    "lead-responder": '''import {{ useState }} from "react";

export default function App() {{
  const [running, setRunning] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const run = async () => {{
    setRunning(true); setError(null);
    try {{
      const r = await fetch("/run", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          gmail_query: "is:unread newer_than:7d",
          max_emails: 10,
          business_context: "B2B SaaS",
          reply_tone: "friendly and professional",
        }}),
      }});
      const j = await r.json();
      if (j.error) setError(j.error);
      else setData(j);
    }} catch (e) {{ setError(String(e)); }}
    setRunning(false);
  }};

  const stats = data ? [
    {{ label: "Processed", value: data.emails_processed }},
    {{ label: "Hot", value: data.leads_qualified?.hot || 0, color: "#ef4444" }},
    {{ label: "Warm", value: data.leads_qualified?.warm || 0, color: "#f59e0b" }},
    {{ label: "Replies", value: data.replies_sent || 0, color: "#22d3ee" }},
  ] : [];

  return (
    <div style={{{{ background: "#0c0c10", minHeight: "100vh", color: "#e5e5e5", fontFamily: "Inter, system-ui", padding: 24 }}}}>
      <div style={{{{ maxWidth: 900, margin: "0 auto" }}}}>
        <h1 style={{{{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}}}>Lead Responder</h1>
        <p style={{{{ color: "#888", fontSize: 13, marginBottom: 24 }}}}>Gmail inbox → qualify with AI → auto-reply.</p>
        <button data-testid="run-btn" onClick={{run}} disabled={{running}}
          style={{{{ background: "#22d3ee", color: "#000", border: 0, padding: "8px 20px", borderRadius: 4, fontWeight: 700, fontSize: 12, letterSpacing: "0.1em", textTransform: "uppercase", cursor: running ? "wait" : "pointer", opacity: running ? 0.5 : 1 }}}}>
          {{running ? "Scanning…" : "Run Now"}}
        </button>
        {{error && <div style={{{{ marginTop: 16, padding: 12, background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 4, fontSize: 13 }}}}>{{error}}</div>}}
        {{stats.length > 0 && (
          <div style={{{{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginTop: 24 }}}}>
            {{stats.map((s) => (
              <div key={{s.label}} style={{{{ padding: 16, background: "rgba(255,255,255,0.02)", border: "1px solid #1e1e22", borderRadius: 4 }}}}>
                <div style={{{{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.2em", color: "#888" }}}}>{{s.label}}</div>
                <div style={{{{ fontSize: 24, fontWeight: 700, color: s.color || "#e5e5e5", marginTop: 4 }}}}>{{s.value}}</div>
              </div>
            ))}}
          </div>
        )}}
        {{data?.details?.length > 0 && (
          <div style={{{{ marginTop: 24, background: "rgba(255,255,255,0.02)", border: "1px solid #1e1e22", borderRadius: 4 }}}}>
            <div style={{{{ padding: 12, borderBottom: "1px solid #1e1e22", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.2em", color: "#888" }}}}>Recent Leads</div>
            {{data.details.slice(0, 10).map((d, i) => (
              <div key={{i}} style={{{{ padding: 12, borderBottom: i < data.details.length - 1 ? "1px solid #1e1e22" : 0, display: "flex", alignItems: "center", gap: 12 }}}}>
                <span style={{{{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 4, background: d.qualification === "hot" ? "rgba(239,68,68,0.15)" : d.qualification === "warm" ? "rgba(245,158,11,0.15)" : "rgba(120,120,120,0.15)", color: d.qualification === "hot" ? "#ef4444" : d.qualification === "warm" ? "#f59e0b" : "#888", textTransform: "uppercase" }}}}>
                  {{d.qualification}}
                </span>
                <div style={{{{ flex: 1, minWidth: 0 }}}}>
                  <div style={{{{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}}}>{{d.subject || "(no subject)"}}</div>
                  <div style={{{{ fontSize: 11, color: "#666", marginTop: 2 }}}}>{{d.from}}</div>
                </div>
                {{d.reply_sent && <span style={{{{ fontSize: 10, color: "#22d3ee", textTransform: "uppercase", letterSpacing: "0.1em" }}}}>Replied</span>}}
              </div>
            ))}}
          </div>
        )}}
      </div>
    </div>
  );
}}
''',

    # Compact dashboards for the rest — same layout family, different fields.
    "social-media-repurposer": '''import {{ useState }} from "react";
export default function App() {{
  const [content, setContent] = useState("");
  const [voice, setVoice] = useState("casual and clear");
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState(null);
  const [err, setErr] = useState(null);
  const run = async () => {{
    setBusy(true); setErr(null);
    try {{ const r = await fetch("/run", {{ method: "POST", headers: {{ "Content-Type":"application/json" }}, body: JSON.stringify({{ content, brand_voice: voice, include_hashtags: true, thread_length: 6 }}) }}); const j = await r.json(); if (j.error) setErr(j.error); else setOut(j); }} catch(e){{ setErr(String(e)); }}
    setBusy(false);
  }};
  const blk = {{ background:"rgba(255,255,255,0.02)", border:"1px solid #1e1e22", borderRadius:4, padding:14 }};
  return (
    <div style={{{{ background:"#0c0c10", minHeight:"100vh", color:"#e5e5e5", fontFamily:"Inter, system-ui", padding:24 }}}}>
      <div style={{{{ maxWidth:1100, margin:"0 auto" }}}}>
        <h1 style={{{{ fontSize:22, fontWeight:700 }}}}>Social Media Repurposer</h1>
        <p style={{{{ color:"#888", fontSize:13, marginBottom:20 }}}}>One input. Three platform-ready posts.</p>
        <textarea data-testid="content-textarea" value={{content}} onChange={{e=>setContent(e.target.value)}} placeholder="Paste your blog post, transcript, or newsletter…" rows={{8}} style={{{{ width:"100%", background:"rgba(255,255,255,0.02)", border:"1px solid #1e1e22", borderRadius:4, padding:12, color:"#e5e5e5", fontSize:13, fontFamily:"inherit", marginBottom:12 }}}}/>
        <input data-testid="voice-input" value={{voice}} onChange={{e=>setVoice(e.target.value)}} placeholder="Brand voice (e.g. witty, technical)" style={{{{ width:"100%", background:"rgba(255,255,255,0.02)", border:"1px solid #1e1e22", borderRadius:4, padding:10, color:"#e5e5e5", fontSize:13, marginBottom:12 }}}}/>
        <button data-testid="run-btn" onClick={{run}} disabled={{busy||!content}} style={{{{ background:"#22d3ee", color:"#000", border:0, padding:"8px 20px", borderRadius:4, fontWeight:700, fontSize:12, letterSpacing:"0.1em", textTransform:"uppercase" }}}}>{{busy?"Generating…":"Generate"}}</button>
        {{err && <div style={{{{ marginTop:14, padding:12, background:"rgba(239,68,68,0.1)", borderRadius:4, fontSize:13 }}}}>{{err}}</div>}}
        {{out && (
          <div style={{{{ display:"grid", gridTemplateColumns:"repeat(3, 1fr)", gap:12, marginTop:20 }}}}>
            <div style={{blk}}><div style={{{{ fontSize:10, textTransform:"uppercase", letterSpacing:"0.2em", color:"#22d3ee", marginBottom:8 }}}}>Twitter</div>{{(out.twitter_thread||[]).map((t,i)=><div key={{i}} style={{{{ fontSize:12, marginBottom:8, paddingBottom:8, borderBottom:"1px solid #1e1e22" }}}}>{{t}}</div>)}}</div>
            <div style={{blk}}><div style={{{{ fontSize:10, textTransform:"uppercase", letterSpacing:"0.2em", color:"#3b82f6", marginBottom:8 }}}}>LinkedIn</div><div style={{{{ fontSize:12, whiteSpace:"pre-wrap" }}}}>{{out.linkedin_post}}</div></div>
            <div style={{blk}}><div style={{{{ fontSize:10, textTransform:"uppercase", letterSpacing:"0.2em", color:"#a855f7", marginBottom:8 }}}}>Instagram</div><div style={{{{ fontSize:12, whiteSpace:"pre-wrap" }}}}>{{out.instagram_caption}}</div></div>
          </div>
        )}}
      </div>
    </div>
  );
}}
''',

    "invoice-chaser": '''import {{ useState }} from "react";
export default function App() {{
  const [busy, setBusy] = useState(false);
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const run = async () => {{
    setBusy(true); setErr(null);
    try {{ const r = await fetch("/run", {{ method:"POST", headers:{{ "Content-Type":"application/json" }}, body: JSON.stringify({{ days_overdue_min: 3, auto_send: false, tone:"polite but firm", business_name:"TaskForce AI", sender_name:"Accounts" }}) }}); const j = await r.json(); if(j.error) setErr(j.error); else setData(j); }} catch(e){{ setErr(String(e)); }}
    setBusy(false);
  }};
  const sev = (s)=> s==="final_notice"?"#ef4444":s==="firm"?"#f59e0b":"#888";
  return (
    <div style={{{{ background:"#0c0c10", minHeight:"100vh", color:"#e5e5e5", fontFamily:"Inter, system-ui", padding:24 }}}}>
      <div style={{{{ maxWidth:1000, margin:"0 auto" }}}}>
        <h1 style={{{{ fontSize:22, fontWeight:700 }}}}>Invoice Chaser</h1>
        <p style={{{{ color:"#888", fontSize:13, marginBottom:20 }}}}>Find overdue invoices, draft tone-appropriate reminders.</p>
        <button data-testid="run-btn" onClick={{run}} disabled={{busy}} style={{{{ background:"#10b981", color:"#000", border:0, padding:"8px 20px", borderRadius:4, fontWeight:700, fontSize:12, letterSpacing:"0.1em", textTransform:"uppercase" }}}}>{{busy?"Scanning…":"Run Scan"}}</button>
        {{err && <div style={{{{ marginTop:14, padding:12, background:"rgba(239,68,68,0.1)", borderRadius:4, fontSize:13 }}}}>{{err}}</div>}}
        {{data && (
          <div style={{{{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:12, marginTop:20 }}}}>
            <div style={{{{ padding:14, background:"rgba(255,255,255,0.02)", border:"1px solid #1e1e22", borderRadius:4 }}}}><div style={{{{ fontSize:10, letterSpacing:"0.2em", color:"#888", textTransform:"uppercase" }}}}>Total</div><div style={{{{ fontSize:24, fontWeight:700, marginTop:4 }}}}>{{data.invoices_found}}</div></div>
            <div style={{{{ padding:14, background:"rgba(255,255,255,0.02)", border:"1px solid #1e1e22", borderRadius:4 }}}}><div style={{{{ fontSize:10, letterSpacing:"0.2em", color:"#888", textTransform:"uppercase" }}}}>Overdue</div><div style={{{{ fontSize:24, fontWeight:700, color:"#f59e0b", marginTop:4 }}}}>{{data.overdue}}</div></div>
            <div style={{{{ padding:14, background:"rgba(255,255,255,0.02)", border:"1px solid #1e1e22", borderRadius:4 }}}}><div style={{{{ fontSize:10, letterSpacing:"0.2em", color:"#888", textTransform:"uppercase" }}}}>Drafts</div><div style={{{{ fontSize:24, fontWeight:700, color:"#22d3ee", marginTop:4 }}}}>{{data.drafts_generated}}</div></div>
          </div>
        )}}
        {{data?.details?.length > 0 && (
          <div style={{{{ marginTop:20, background:"rgba(255,255,255,0.02)", border:"1px solid #1e1e22", borderRadius:4 }}}}>
            {{data.details.map((d,i)=>(
              <div key={{i}} style={{{{ padding:12, borderBottom: i<data.details.length-1?"1px solid #1e1e22":0 }}}}>
                <div style={{{{ display:"flex", justifyContent:"space-between", alignItems:"center" }}}}>
                  <div style={{{{ fontSize:13, fontWeight:500 }}}}>{{d.customer}} — {{d.amount}}</div>
                  <span style={{{{ fontSize:10, fontWeight:700, padding:"2px 8px", borderRadius:4, color:sev(d.severity), background:`${{sev(d.severity)}}22`, textTransform:"uppercase" }}}}>{{d.severity}}</span>
                </div>
                <div style={{{{ fontSize:11, color:"#888", marginTop:2 }}}}>{{d.days_overdue}} days overdue · {{d.email}}</div>
                <div style={{{{ fontSize:12, color:"#999", marginTop:6, padding:8, background:"rgba(255,255,255,0.02)", borderRadius:4 }}}}>{{d.draft_subject}}</div>
              </div>
            ))}}
          </div>
        )}}
      </div>
    </div>
  );
}}
''',

    "customer-support-classifier": '''import {{ useState }} from "react";
export default function App() {{
  const [busy, setBusy] = useState(false);
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const run = async () => {{
    setBusy(true); setErr(null);
    try {{ const r = await fetch("/run", {{ method:"POST", headers:{{ "Content-Type":"application/json" }}, body: JSON.stringify({{ gmail_query:"is:unread label:support", max_messages:20, company_context:"We build AI agent tools." }}) }}); const j = await r.json(); if(j.error) setErr(j.error); else setData(j); }} catch(e){{ setErr(String(e)); }}
    setBusy(false);
  }};
  const ucol = (u)=> u==="critical"?"#ef4444":u==="high"?"#f97316":u==="medium"?"#f59e0b":"#22c55e";
  return (
    <div style={{{{ background:"#0c0c10", minHeight:"100vh", color:"#e5e5e5", fontFamily:"Inter, system-ui", padding:24 }}}}>
      <div style={{{{ maxWidth:1000, margin:"0 auto" }}}}>
        <h1 style={{{{ fontSize:22, fontWeight:700 }}}}>Customer Support Classifier</h1>
        <p style={{{{ color:"#888", fontSize:13, marginBottom:20 }}}}>Triage support email by urgency + category.</p>
        <button data-testid="run-btn" onClick={{run}} disabled={{busy}} style={{{{ background:"#f59e0b", color:"#000", border:0, padding:"8px 20px", borderRadius:4, fontWeight:700, fontSize:12, letterSpacing:"0.1em", textTransform:"uppercase" }}}}>{{busy?"Scanning…":"Run Scan"}}</button>
        {{err && <div style={{{{ marginTop:14, padding:12, background:"rgba(239,68,68,0.1)", borderRadius:4, fontSize:13 }}}}>{{err}}</div>}}
        {{data && (
          <>
            <div style={{{{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:8, marginTop:20 }}}}>
              {{Object.entries(data.classification||{{}}).map(([k,v])=>(
                <div key={{k}} style={{{{ padding:12, background:"rgba(255,255,255,0.02)", border:"1px solid #1e1e22", borderRadius:4 }}}}>
                  <div style={{{{ fontSize:10, letterSpacing:"0.2em", color:ucol(k), textTransform:"uppercase" }}}}>{{k}}</div>
                  <div style={{{{ fontSize:22, fontWeight:700, marginTop:4 }}}}>{{v}}</div>
                </div>
              ))}}
            </div>
            <div style={{{{ marginTop:20, background:"rgba(255,255,255,0.02)", border:"1px solid #1e1e22", borderRadius:4 }}}}>
              {{(data.details||[]).map((d,i)=>(
                <div key={{i}} style={{{{ padding:12, borderBottom: i<(data.details||[]).length-1?"1px solid #1e1e22":0 }}}}>
                  <div style={{{{ display:"flex", gap:8, alignItems:"center" }}}}>
                    <span style={{{{ fontSize:9, fontWeight:700, padding:"2px 7px", borderRadius:4, background:`${{ucol(d.urgency)}}22`, color:ucol(d.urgency), textTransform:"uppercase", letterSpacing:"0.1em" }}}}>{{d.urgency}}</span>
                    <span style={{{{ fontSize:10, padding:"2px 7px", borderRadius:4, background:"rgba(255,255,255,0.04)", color:"#aaa" }}}}>{{d.category}}</span>
                    <span style={{{{ fontSize:13, fontWeight:500, flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}}}>{{d.subject}}</span>
                  </div>
                  <div style={{{{ fontSize:12, color:"#999", marginTop:6 }}}}>{{(d.draft_response||"").slice(0, 200)}}</div>
                  <div style={{{{ fontSize:10, color:"#666", marginTop:6, textTransform:"uppercase", letterSpacing:"0.1em" }}}}>→ {{d.suggested_action}}</div>
                </div>
              ))}}
            </div>
          </>
        )}}
      </div>
    </div>
  );
}}
''',

    "meeting-notes-action-items": '''import {{ useState }} from "react";
export default function App() {{
  const [transcript, setTranscript] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const run = async () => {{
    setBusy(true); setErr(null);
    try {{ const r = await fetch("/run", {{ method:"POST", headers:{{ "Content-Type":"application/json" }}, body: JSON.stringify({{ transcript, meeting_title: title || "Untitled", participants: [] }}) }}); const j = await r.json(); if(j.error) setErr(j.error); else setData(j); }} catch(e){{ setErr(String(e)); }}
    setBusy(false);
  }};
  const blk = {{ background:"rgba(255,255,255,0.02)", border:"1px solid #1e1e22", borderRadius:4, padding:14 }};
  return (
    <div style={{{{ background:"#0c0c10", minHeight:"100vh", color:"#e5e5e5", fontFamily:"Inter, system-ui", padding:24 }}}}>
      <div style={{{{ maxWidth:1000, margin:"0 auto" }}}}>
        <h1 style={{{{ fontSize:22, fontWeight:700 }}}}>Meeting Notes → Action Items</h1>
        <p style={{{{ color:"#888", fontSize:13, marginBottom:20 }}}}>Paste a transcript, get structured action items.</p>
        <input data-testid="title-input" value={{title}} onChange={{e=>setTitle(e.target.value)}} placeholder="Meeting title (optional)" style={{{{ width:"100%", background:"rgba(255,255,255,0.02)", border:"1px solid #1e1e22", borderRadius:4, padding:10, color:"#e5e5e5", fontSize:13, marginBottom:10 }}}}/>
        <textarea data-testid="transcript-textarea" value={{transcript}} onChange={{e=>setTranscript(e.target.value)}} rows={{10}} placeholder="Paste your meeting transcript…" style={{{{ width:"100%", background:"rgba(255,255,255,0.02)", border:"1px solid #1e1e22", borderRadius:4, padding:12, color:"#e5e5e5", fontSize:13, marginBottom:12, fontFamily:"inherit" }}}}/>
        <button data-testid="run-btn" onClick={{run}} disabled={{busy||!transcript}} style={{{{ background:"#3b82f6", color:"#fff", border:0, padding:"8px 20px", borderRadius:4, fontWeight:700, fontSize:12, letterSpacing:"0.1em", textTransform:"uppercase" }}}}>{{busy?"Processing…":"Process"}}</button>
        {{err && <div style={{{{ marginTop:14, padding:12, background:"rgba(239,68,68,0.1)", borderRadius:4, fontSize:13 }}}}>{{err}}</div>}}
        {{data && (
          <div style={{{{ display:"grid", gap:12, marginTop:20 }}}}>
            <div style={{blk}}><div style={{{{ fontSize:10, textTransform:"uppercase", letterSpacing:"0.2em", color:"#22d3ee", marginBottom:6 }}}}>Summary</div><div style={{{{ fontSize:13 }}}}>{{data.summary}}</div></div>
            {{data.key_decisions?.length > 0 && (<div style={{blk}}><div style={{{{ fontSize:10, textTransform:"uppercase", letterSpacing:"0.2em", color:"#3b82f6", marginBottom:8 }}}}>Decisions</div><ul style={{{{ margin:0, padding:0, listStyle:"none" }}}}>{{data.key_decisions.map((d,i)=><li key={{i}} style={{{{ fontSize:12, padding:"4px 0", borderTop: i?"1px solid #1e1e22":0 }}}}>• {{d}}</li>)}}</ul></div>)}}
            {{data.action_items?.length > 0 && (<div style={{blk}}><div style={{{{ fontSize:10, textTransform:"uppercase", letterSpacing:"0.2em", color:"#f59e0b", marginBottom:8 }}}}>Action Items</div>{{data.action_items.map((a,i)=>(<div key={{i}} style={{{{ padding:8, marginBottom:6, background:"rgba(255,255,255,0.02)", borderRadius:4 }}}}><div style={{{{ fontSize:13 }}}}>{{a.task}}</div><div style={{{{ fontSize:11, color:"#888", marginTop:4 }}}}>{{a.owner || "Unassigned"}} · {{a.deadline || "No deadline"}} · <span style={{{{ color: a.priority==="high"?"#ef4444":a.priority==="medium"?"#f59e0b":"#22c55e" }}}}>{{a.priority || "low"}}</span></div></div>))}}</div>)}}
          </div>
        )}}
      </div>
    </div>
  );
}}
''',
}


def _nodes_for(agent: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Hand-tuned node graphs per agent (used as the visual workflow."""
    slug = agent["slug"]
    color = agent["avatar_color"]
    if slug == "lead-responder":
        return {
            "nodes": [
                {"id": "n1", "type": "trigger", "label": "Scan Inbox", "position": {"x": 100, "y": 120}, "data": {"color": color}},
                {"id": "n2", "type": "action",  "label": "Gmail Fetch", "position": {"x": 400, "y": 120}},
                {"id": "n3", "type": "llm",     "label": "Classify Hot/Warm/Cold", "position": {"x": 700, "y": 120}},
                {"id": "n4", "type": "condition","label": "Is Hot or Warm?", "position": {"x": 1000, "y": 120}},
                {"id": "n5", "type": "llm",     "label": "Draft Reply", "position": {"x": 1300, "y": 40}},
                {"id": "n6", "type": "action",  "label": "Send Gmail",  "position": {"x": 1600, "y": 40}},
                {"id": "n7", "type": "database","label": "Log Skipped", "position": {"x": 1300, "y": 200}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"},
                {"id": "e2", "source": "n2", "target": "n3"},
                {"id": "e3", "source": "n3", "target": "n4"},
                {"id": "e4", "source": "n4", "target": "n5"},
                {"id": "e5", "source": "n5", "target": "n6"},
                {"id": "e6", "source": "n4", "target": "n7"},
            ],
        }
    if slug == "social-media-repurposer":
        return {
            "nodes": [
                {"id": "n1", "type": "trigger",  "label": "Input Content", "position": {"x": 100, "y": 120}},
                {"id": "n2", "type": "transform","label": "Normalize",     "position": {"x": 400, "y": 120}},
                {"id": "n3", "type": "llm",      "label": "Twitter Thread","position": {"x": 700, "y": 40}},
                {"id": "n4", "type": "llm",      "label": "LinkedIn Post", "position": {"x": 700, "y": 180}},
                {"id": "n5", "type": "llm",      "label": "Instagram Cap.","position": {"x": 700, "y": 320}},
                {"id": "n6", "type": "transform","label": "Bundle Output", "position": {"x": 1000, "y": 180}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"},
                {"id": "e2", "source": "n2", "target": "n3"},
                {"id": "e3", "source": "n2", "target": "n4"},
                {"id": "e4", "source": "n2", "target": "n5"},
                {"id": "e5", "source": "n3", "target": "n6"},
                {"id": "e6", "source": "n4", "target": "n6"},
                {"id": "e7", "source": "n5", "target": "n6"},
            ],
        }
    if slug == "invoice-chaser":
        return {
            "nodes": [
                {"id": "n1", "type": "trigger",   "label": "Scan Trigger",      "position": {"x": 100, "y": 120}},
                {"id": "n2", "type": "action",    "label": "List Stripe Inv.",  "position": {"x": 400, "y": 120}},
                {"id": "n3", "type": "transform", "label": "Filter Overdue",    "position": {"x": 700, "y": 120}},
                {"id": "n4", "type": "transform", "label": "Severity Bucket",   "position": {"x": 1000, "y": 120}},
                {"id": "n5", "type": "llm",       "label": "Draft Reminder",    "position": {"x": 1300, "y": 120}},
                {"id": "n6", "type": "condition", "label": "Auto-send?",        "position": {"x": 1600, "y": 120}},
                {"id": "n7", "type": "action",    "label": "Send Email",        "position": {"x": 1900, "y": 60}},
                {"id": "n8", "type": "database",  "label": "Queue Draft",       "position": {"x": 1900, "y": 200}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"}, {"id": "e2", "source": "n2", "target": "n3"},
                {"id": "e3", "source": "n3", "target": "n4"}, {"id": "e4", "source": "n4", "target": "n5"},
                {"id": "e5", "source": "n5", "target": "n6"}, {"id": "e6", "source": "n6", "target": "n7"},
                {"id": "e7", "source": "n6", "target": "n8"},
            ],
        }
    if slug == "customer-support-classifier":
        return {
            "nodes": [
                {"id": "n1", "type": "trigger",   "label": "Scan Support Inbox","position": {"x": 100, "y": 120}},
                {"id": "n2", "type": "action",    "label": "Gmail Fetch",       "position": {"x": 400, "y": 120}},
                {"id": "n3", "type": "llm",       "label": "Classify Urgency",  "position": {"x": 700, "y": 60}},
                {"id": "n4", "type": "llm",       "label": "Classify Category", "position": {"x": 700, "y": 200}},
                {"id": "n5", "type": "llm",       "label": "Draft Response",    "position": {"x": 1000, "y": 120}},
                {"id": "n6", "type": "transform", "label": "Suggest Action",    "position": {"x": 1300, "y": 120}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"}, {"id": "e2", "source": "n2", "target": "n3"},
                {"id": "e3", "source": "n2", "target": "n4"}, {"id": "e4", "source": "n3", "target": "n5"},
                {"id": "e5", "source": "n4", "target": "n5"}, {"id": "e6", "source": "n5", "target": "n6"},
            ],
        }
    if slug == "meeting-notes-action-items":
        return {
            "nodes": [
                {"id": "n1", "type": "trigger",   "label": "Input Transcript", "position": {"x": 100, "y": 120}},
                {"id": "n2", "type": "transform", "label": "Chunk",            "position": {"x": 400, "y": 120}},
                {"id": "n3", "type": "llm",       "label": "Extract JSON",     "position": {"x": 700, "y": 120}},
                {"id": "n4", "type": "transform", "label": "Format Markdown",  "position": {"x": 1000, "y": 120}},
                {"id": "n5", "type": "action",    "label": "Slack (optional)", "position": {"x": 1300, "y": 120}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"}, {"id": "e2", "source": "n2", "target": "n3"},
                {"id": "e3", "source": "n3", "target": "n4"}, {"id": "e4", "source": "n4", "target": "n5"},
            ],
        }
    return {"nodes": [], "edges": []}


async def _resolve_owner(db, owner_email: str | None) -> dict:
    """Pick the user we'll attribute these agents to.

    NOTE: This is a CLI seeder, not an API route — the returned `dict` is
    used only for `_id` / `email` lookups inside this script. ObjectId
    serialization warnings from the linter (EB001) are false positives here.
    """
    if owner_email:
        u = await db.users.find_one({"email": owner_email})
        if u:
            return u  # noqa: EB001 - CLI script, not serialized
        raise SystemExit(f"--owner-email {owner_email!r} not found in users.")
    # Try common owner emails.
    for em in ("admin@nova.ai", "benjamin@taskforce.ai"):
        u = await db.users.find_one({"email": em})
        if u:
            return u  # noqa: EB001 - CLI script, not serialized
    u = await db.users.find_one({"$or": [{"is_owner": True}, {"is_admin": True}]})
    if not u:
        raise SystemExit("No owner/admin user found — pass --owner-email.")
    return u  # noqa: EB001 - CLI script, not serialized


async def main(dry_run: bool, owner_email: str | None) -> None:
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        raise SystemExit("MONGO_URL / DB_NAME missing.")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    owner = await _resolve_owner(db, owner_email)
    owner_id = str(owner.get("id") or owner.get("_id") or owner.get("email"))
    owner_email_display = owner.get("email")
    print(f"Seeding as owner: {owner_email_display}  (id={owner_id})\n")
    now = datetime.now(tz=timezone.utc).isoformat()

    for agent in AGENTS:
        slug = agent["slug"]
        existing_listing = await db.exchange_listings.find_one({
            "is_official": True, "slug": slug,
        })

        # Build the bot_project document.
        files = list(agent["files"])
        # Append the App.jsx UI as a separate file in the project.
        if slug in _DASHBOARDS:
            files.append({
                "path": "App.jsx",
                "content": _DASHBOARDS[slug],
                "language": "javascript",
            })

        graph = _nodes_for(agent)
        bot_project_id = (existing_listing or {}).get("source_project_id") or uuid.uuid4().hex
        bot_project_doc = {
            "id": bot_project_id,
            "user_id": owner_id,
            "creator_email": owner_email_display,
            "language": "python",
            "name": agent["name"],
            "description": agent["description"],
            "prompt": f"[Official seed agent] {agent['name']}",
            "files": files,
            "nodes": graph["nodes"],
            "edges": graph["edges"],
            "has_ui": True,
            "app_slug": f"{slug}-official",
            "frontend": {"app_jsx": _DASHBOARDS.get(slug, ""), "manifest": {"name": agent["name"]}},
            "source": "official-seed",
            "updated_at": now,
        }
        if not existing_listing:
            bot_project_doc["created_at"] = now

        # Build the listing document.
        listing_id = (existing_listing or {}).get("id") or uuid.uuid4().hex
        listing_doc = {
            "id": listing_id,
            "slug": slug,
            "user_id": owner_id,
            "creator_email": owner_email_display,
            "creator_name": "TaskForce Official",
            "name": agent["name"],
            "description": agent["description"],
            "category": agent["category"],
            "tags": agent["tags"],
            "price_credits": agent["price_credits"],
            "rent_price": 0,
            "buy_price": 0,
            "avatar_icon": agent["avatar_icon"],
            "avatar_color": agent["avatar_color"],
            "trigger_type": agent["trigger_type"],
            "engine": agent["engine"],
            "required_integrations": agent["required_integrations"],
            "source_project_id": bot_project_id,
            "status": "published",
            "is_official": True,
            "nodes_snapshot": graph["nodes"],
            "edges_snapshot": graph["edges"],
            "updated_at": now,
        }
        if not existing_listing:
            listing_doc["created_at"] = now
            listing_doc["deploy_count"] = 0
            listing_doc["purchase_count"] = 0
            listing_doc["revenue_credits"] = 0

        if dry_run:
            print(f"[dry-run]  would upsert  {slug:<32}  price={agent['price_credits']}cr  files={len(files)}  nodes={len(graph['nodes'])}")
            continue

        # Upsert bot_project.
        await db.bot_projects.update_one(
            {"id": bot_project_id}, {"$set": bot_project_doc}, upsert=True,
        )
        # Upsert listing.
        await db.exchange_listings.update_one(
            {"is_official": True, "slug": slug}, {"$set": listing_doc}, upsert=True,
        )
        print(f"  ✓ {slug:<32}  price={agent['price_credits']}cr  ({'updated' if existing_listing else 'created'})")

    if dry_run:
        print("\nDry-run only. Re-run without --dry-run to apply.")
    else:
        # Final counts.
        n_official = await db.exchange_listings.count_documents({"is_official": True})
        print(f"\n✓ Seed complete. {n_official} official listings total in the exchange.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--owner-email", help="explicit owner email; default tries admin@nova.ai then benjamin@taskforce.ai")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run, args.owner_email))
