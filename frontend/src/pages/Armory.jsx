/**
 * Armory.jsx — the redesigned visual+code bot builder.
 *
 * Three-panel layout:
 *   - SessionSidebar (240px, collapsible)
 *   - ChatPanel (flex-grow)
 *   - AgentPreview (380px, slides in once a build exists)
 *
 * Wires to vibe/* APIs (sessions, chat, generate) and reuses the existing
 * DirectPublishModal + bot-projects test-run endpoint.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/App";
import SessionSidebar from "@/components/armory/SessionSidebar";
import ChatPanel from "@/components/armory/ChatPanel";
import AgentPreview from "@/components/armory/AgentPreview";
import DirectPublishModal from "@/components/DirectPublishModal";
import "./Armory.css";

const API = process.env.REACT_APP_BACKEND_URL;

export default function Armory() {
  const { token } = useAuth() || {};
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const headers = useMemo(() => ({
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  }), [token]);

  // Catalog
  const [models, setModels] = useState([]);
  const [model, setModel] = useState("gemini-2.5-flash");
  const [credits, setCredits] = useState(null);

  // Sessions
  const [sessions, setSessions] = useState([]);
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);

  // Build artifacts
  const [project, setProject] = useState(null);          // bot_project doc
  const [files, setFiles] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);

  // Input + busy
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyMode, setBusyMode] = useState(null); // chat | build
  const [busyAction, setBusyAction] = useState(null); // test | deploy | publish | export

  // UI state
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [showPublish, setShowPublish] = useState(false);
  const [testRunResult, setTestRunResult] = useState(null);

  // Bounty prefill (same hand-off shape as VibeBuildPage)
  const bountyPrefillReadRef = useRef(false);

  // ── Initial loads ─────────────────────────────────────────
  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/vibe/models`, { headers })
      .then((r) => r.json())
      .then((d) => {
        setModels(d.models || []);
        setModel(d.default || "gemini-2.5-flash");
      })
      .catch(() => {});
    refreshSessions();
    refreshCredits();
    const sid = search.get("session");
    if (sid) loadSession(sid);
    // Read bounty prefill once
    if (!bountyPrefillReadRef.current) {
      bountyPrefillReadRef.current = true;
      try {
        const raw = sessionStorage.getItem("tfai_bounty_prefill");
        if (raw) {
          const data = JSON.parse(raw);
          if (data?.bounty_id && data?.title) {
            setInput(
              `Build me an agent for the bounty "${data.title}".\n\n` +
              (data.description ? `Spec:\n${data.description.slice(0, 1200)}\n\n` : "") +
              `Please give the agent a clear main.py, a README, and any integrations the bounty calls out.`,
            );
            toast.info(`Pre-filled from bounty: ${data.title}`);
          }
        }
      } catch { /* ignore */ }
    }
    // eslint-disable-next-line
  }, [token]);

  // ── API helpers ───────────────────────────────────────────
  const refreshSessions = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/vibe/sessions`, { headers });
      const d = await r.json();
      setSessions(d.sessions || []);
    } catch { /* ignore */ }
  }, [headers]);

  const refreshCredits = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/credits/me`, { headers });
      const d = await r.json();
      setCredits(d);
    } catch { /* ignore */ }
  }, [headers]);

  const loadProject = useCallback(async (projectId) => {
    if (!projectId) {
      setProject(null); setFiles([]); setNodes([]); setEdges([]);
      return;
    }
    try {
      const r = await fetch(`${API}/api/armory/bot-projects/${projectId}`, { headers });
      if (!r.ok) {
        // Project was deleted, archived, or doesn't belong to this user.
        if (r.status === 404) {
          toast.error("Build artifact no longer exists. Start a new conversation to rebuild.");
        } else {
          toast.error(`Couldn't load build (${r.status}). Try again.`);
        }
        setProject(null); setFiles([]); setNodes([]); setEdges([]); setPreviewOpen(false);
        return;
      }
      const proj = await r.json();
      setProject(proj);
      setFiles(proj.files || []);
      setNodes(proj.nodes || []);
      setEdges(proj.edges || []);
      setPreviewOpen(true);
    } catch {
      toast.error("Couldn't reach the server while loading the build.");
      setProject(null); setFiles([]); setNodes([]); setEdges([]); setPreviewOpen(false);
    }
  }, [headers]);

  const loadSession = useCallback(async (sid) => {
    try {
      const r = await fetch(`${API}/api/vibe/sessions/${sid}`, { headers });
      if (!r.ok) return;
      const d = await r.json();
      setSession(d);
      setMessages(d.messages || []);
      setModel(d.model || "gemini-2.5-flash");
      navigate(`/armory?session=${sid}`, { replace: true });
      if (d.project_id) await loadProject(d.project_id);
      else { setProject(null); setFiles([]); setNodes([]); setEdges([]); setPreviewOpen(false); }
    } catch { /* ignore */ }
  }, [headers, navigate, loadProject]);

  const newSession = useCallback(() => {
    setSession(null);
    setMessages([]);
    setProject(null); setFiles([]); setNodes([]); setEdges([]);
    setPreviewOpen(false);
    setTestRunResult(null);
    setInput("");
    navigate("/armory", { replace: true });
  }, [navigate]);

  const deleteSession = useCallback(async (sid) => {
    if (!window.confirm("Delete this session? This cannot be undone.")) return;
    try {
      const r = await fetch(`${API}/api/vibe/sessions/${sid}`, { method: "DELETE", headers });
      if (r.ok) {
        toast.success("Session deleted");
        if (sid === session?.id) newSession();
        refreshSessions();
      }
    } catch { toast.error("Delete failed"); }
  }, [headers, session, newSession, refreshSessions]);

  // ── Send chat / build ─────────────────────────────────────
  const send = useCallback(async (mode /* "chat" | "build" */) => {
    if (!input.trim() || busy) return;
    const userText = input.trim();
    setInput("");
    setBusy(true); setBusyMode(mode);

    // Optimistic user message
    const userMsg = { role: "user", content: userText, timestamp: new Date().toISOString() };
    setMessages((m) => [...m, userMsg]);

    try {
      const endpoint = mode === "build" ? "/api/vibe/generate" : "/api/vibe/chat";
      const body = { session_id: session?.id || null, message: userText, model };
      const t0 = performance.now();
      const res = await fetch(`${API}${endpoint}`, {
        method: "POST", headers, body: JSON.stringify(body),
      });
      const data = await res.json();
      const dt = performance.now() - t0;

      if (!res.ok) {
        if (data.error === "INSUFFICIENT_CREDITS") {
          setMessages((m) => [...m, {
            role: "assistant", type: "error",
            content: `You need ${data.cost ?? data.required} credits, but only have ${data.balance ?? 0}.`,
            suggestion: "Top up credits or pick a cheaper model.",
          }]);
        } else if (data.detail?.error === "BYOK_REQUIRED" || data.error === "BYOK_REQUIRED") {
          setMessages((m) => [...m, {
            role: "assistant", type: "error",
            content: `This model needs your ${data.detail?.service || data.service} API key.`,
            suggestion: "Add it in the Vault, or pick a platform model.",
          }]);
        } else {
          const reason = typeof data.detail === "string" ? data.detail : (data.message || `Request failed (${res.status})`);
          setMessages((m) => [...m, { role: "assistant", type: "error", content: reason }]);
        }
        return;
      }

      // Append AI message
      if (mode === "build") {
        // NEW: pipeline returns {status: 'queued', session_id} — poll for stage progress.
        const sid = data.session_id;
        setSession((s) => ({ ...(s || {}), id: sid, model, project_id: s?.project_id || null }));

        // Insert a "building" placeholder we can mutate during polling.
        const placeholderIdx = (() => {
          let idx = -1;
          setMessages((m) => {
            idx = m.length;
            return [...m, { role: "assistant", type: "build_progress", session_id: sid, progress: [], status: "queued" }];
          });
          return idx;
        })();

        // Poll loop — every 1.5s up to 4 min
        const startedAt = Date.now();
        const maxMs = 4 * 60 * 1000;
        let last = null;
        while (Date.now() - startedAt < maxMs) {
          await new Promise((r) => setTimeout(r, 1500));
          let pres;
          try {
            pres = await fetch(`${API}/api/vibe/build-status/${sid}`, { headers });
          } catch {
            continue;
          }
          if (!pres.ok) continue;
          last = await pres.json();
          setMessages((m) => {
            const next = [...m];
            next[placeholderIdx] = {
              role: "assistant",
              type: "build_progress",
              session_id: sid,
              progress: last.progress || [],
              status: last.status,
              paused: last.paused,
              error: last.error,
              total_credits_used: last.total_credits_used,
            };
            return next;
          });
          if (["complete", "paused", "failed"].includes(last.status)) break;
        }

        if (last && last.status === "complete" && last.project) {
          setMessages((m) => {
            const next = [...m];
            next[placeholderIdx] = {
              role: "assistant",
              type: "build",
              name: last.project.name,
              files: last.project.files || [],
              nodes: last.project.nodes || [],
              edges: last.project.edges || [],
              duration_ms: Math.round(performance.now() - t0),
              credits_used: last.total_credits_used,
              model,
              project_id: last.project.id,
              has_ui: last.project.has_ui,
              app_slug: last.project.app_slug,
              progress: last.progress || [],
            };
            return next;
          });
          setFiles(last.project.files || []);
          setNodes(last.project.nodes || []);
          setEdges(last.project.edges || []);
          if (last.project.id) await loadProject(last.project.id);
          else setPreviewOpen(true);
          toast.success(`${last.project.name || "Agent"} generated · −${last.total_credits_used}cr`);
          setSession((s) => ({ ...(s || {}), id: sid, project_id: last.project.id }));
        } else if (last && last.status === "paused") {
          toast.warning(`Build paused — top up credits and click Resume`);
        } else if (last && last.status === "failed") {
          toast.error(`Build failed: ${last.error || "unknown"}`);
        }
      } else {
        setMessages((m) => [...m, {
          role: "assistant",
          content: data.response,
          credits_used: data.credits_used,
          model: data.model,
          timestamp: new Date().toISOString(),
        }]);
      }
      if (!session?.id) {
        setSession((s) => ({ ...(s || {}), id: data.session_id, title: userText.slice(0, 80), model, project_id: data.project_id || s?.project_id || null }));
      } else if (data.project_id) {
        setSession((s) => ({ ...s, project_id: data.project_id }));
      }
      refreshSessions();
      refreshCredits();
    } catch {
      setMessages((m) => [...m, { role: "assistant", type: "error", content: "Network error. Try again." }]);
    } finally {
      setBusy(false); setBusyMode(null);
    }
  }, [input, busy, session, model, headers, loadProject, refreshSessions, refreshCredits]);

  const handleSuggest = (prompt) => setInput(prompt);

  // ── Resume a paused build (after user tops up credits) ─────
  const onResumeBuild = useCallback(async () => {
    const sid = session?.id;
    if (!sid) {
      toast.error("No session to resume.");
      return;
    }
    setBusy(true); setBusyMode("build");
    try {
      const r = await fetch(`${API}/api/vibe/resume-build/${sid}`, { method: "POST", headers });
      const j = await r.json();
      if (!r.ok) {
        if (j.error === "INSUFFICIENT_CREDITS") {
          toast.error("Still not enough credits — top up more and try again.");
        } else {
          toast.error(j.detail || `Resume failed (${r.status})`);
        }
        return;
      }
      toast.info("Resuming build…");

      // Poll same loop as the original build
      const startedAt = Date.now();
      const maxMs = 4 * 60 * 1000;
      let last = null;
      while (Date.now() - startedAt < maxMs) {
        await new Promise((res) => setTimeout(res, 1500));
        const pres = await fetch(`${API}/api/vibe/build-status/${sid}`, { headers });
        if (!pres.ok) continue;
        last = await pres.json();
        // Mutate the most-recent build_progress message
        setMessages((m) => {
          const idx = [...m].reverse().findIndex((x) => x.type === "build_progress" || x.type === "build");
          if (idx < 0) return m;
          const realIdx = m.length - 1 - idx;
          const next = [...m];
          next[realIdx] = {
            ...next[realIdx],
            type: last.status === "complete" ? "build" : "build_progress",
            session_id: sid,
            progress: last.progress || [],
            status: last.status,
            paused: last.paused,
            error: last.error,
            total_credits_used: last.total_credits_used,
            ...(last.status === "complete" && last.project ? {
              name: last.project.name,
              files: last.project.files || [],
              nodes: last.project.nodes || [],
              edges: last.project.edges || [],
              project_id: last.project.id,
              has_ui: last.project.has_ui,
              app_slug: last.project.app_slug,
              credits_used: last.total_credits_used,
              model: model,
            } : {}),
          };
          return next;
        });
        if (["complete", "paused", "failed"].includes(last.status)) break;
      }
      if (last && last.status === "complete" && last.project) {
        setFiles(last.project.files || []);
        setNodes(last.project.nodes || []);
        setEdges(last.project.edges || []);
        if (last.project.id) await loadProject(last.project.id);
        toast.success(`Build complete · −${last.total_credits_used}cr`);
      } else if (last && last.status === "paused") {
        toast.warning("Build paused again — add more credits.");
      }
      refreshCredits();
    } catch {
      toast.error("Resume failed.");
    } finally {
      setBusy(false); setBusyMode(null);
    }
  }, [session, headers, model, loadProject, refreshCredits]);

  // ── Right panel actions ───────────────────────────────────
  const openInWorkflows = useCallback(() => {
    if (!project?.id) {
      toast.error("Generate code first.");
      return;
    }
    navigate(`/armory/workflows/${project.id}`);
  }, [project, navigate]);

  const onTestRun = useCallback(async () => {
    if (!project?.id) return;
    setBusyAction("test"); setTestRunResult(null);
    try {
      const r = await fetch(`${API}/api/armory/bot-projects/${project.id}/test-run`, {
        method: "POST", headers,
      });
      const d = await r.json();
      if (!r.ok) {
        const msg = typeof d.detail === "string" ? d.detail : (d.error || "Test run failed");
        setTestRunResult({ success: false, error: msg });
        toast.error(msg);
        return;
      }
      setTestRunResult(d);
      if (d.success) toast.success(`Test run OK · ${d.duration_ms}ms`);
      else toast.error("Run failed — see preview panel.");
    } catch (e) {
      setTestRunResult({ success: false, error: e.message });
      toast.error("Network error");
    } finally {
      setBusyAction(null);
    }
  }, [project, headers]);

  const onDeploy = useCallback(() => {
    if (!project?.id) return;
    // Per current platform flow: deploy = publish (free) → then user runs from MyDeployments.
    setShowPublish(true);
  }, [project]);

  const onPublish = useCallback(() => {
    if (!project?.id) return;
    setShowPublish(true);
  }, [project]);

  const onExport = useCallback(async () => {
    if (!project?.id) return;
    setBusyAction("export");
    try {
      // Build a JSON blob locally — no extra backend endpoint needed.
      const payload = {
        name: project.name,
        description: project.description,
        language: project.language,
        files: project.files,
        nodes: project.nodes,
        edges: project.edges,
        version: project.version,
        exported_at: new Date().toISOString(),
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(project.name || "agent").toLowerCase().replace(/\s+/g, "-")}.tfagent.json`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast.success("Exported");
    } catch {
      toast.error("Export failed");
    } finally {
      setBusyAction(null);
    }
  }, [project]);

  return (
    <div data-testid="armory-page" className="armory-shell flex h-[calc(100vh-52px)]" style={{ background: "var(--armory-bg)" }}>
      <SessionSidebar
        sessions={sessions}
        currentId={session?.id}
        onSelect={loadSession}
        onNew={newSession}
        onDelete={deleteSession}
        open={sidebarOpen}
        onToggle={() => setSidebarOpen((v) => !v)}
        models={models}
        model={model}
        onModelChange={setModel}
        credits={credits}
      />
      <ChatPanel
        session={session}
        messages={messages}
        model={model}
        models={models}
        input={input}
        setInput={setInput}
        busy={busy}
        busyMode={busyMode}
        onSend={send}
        onSuggest={handleSuggest}
        onViewFiles={() => setPreviewOpen(true)}
        onOpenInWorkflows={openInWorkflows}
        onResume={onResumeBuild}
        hasProject={!!project}
      />
      {previewOpen && project && (
        <AgentPreview
          project={project}
          files={files}
          nodes={nodes}
          edges={edges}
          onClose={() => setPreviewOpen(false)}
          onTestRun={onTestRun}
          onDeploy={onDeploy}
          onPublish={onPublish}
          onExport={onExport}
          testRunResult={testRunResult}
          busyAction={busyAction}
        />
      )}
      {/* Floating "show preview" button when collapsed */}
      {!previewOpen && project && (
        <button
          data-testid="armory-show-preview"
          onClick={() => setPreviewOpen(true)}
          className="fixed right-4 bottom-20 z-30 inline-flex items-center gap-1.5 px-3 py-2 text-[10px] font-mono uppercase tracking-[0.15em] rounded-sm transition-all"
          style={{
            background: "var(--armory-accent)",
            color: "#0a0a0a",
            fontWeight: 600,
            boxShadow: "0 8px 24px rgba(0,229,204,0.25)",
          }}
        >
          Show preview
        </button>
      )}
      {/* Publish modal */}
      {showPublish && (
        <DirectPublishModal
          open={showPublish}
          onClose={() => setShowPublish(false)}
          onPublished={() => { setShowPublish(false); toast.success("Published"); refreshSessions(); }}
        />
      )}
    </div>
  );
}
