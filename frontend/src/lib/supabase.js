import { createClient } from "@supabase/supabase-js";

// Supabase config is OPTIONAL — used for audit logging on a few code paths.
// If the build doesn't have these env vars baked in (common on first Railway
// deploys where REACT_APP_SUPABASE_URL hasn't been set as a build arg yet),
// fall back to a no-op stub so the React tree still mounts. The handful of
// features that actually use supabase (audit log views) will gracefully
// return empty results instead of crashing the whole app.
const supabaseUrl = process.env.REACT_APP_SUPABASE_URL;
const supabaseAnonKey = process.env.REACT_APP_SUPABASE_ANON_KEY;

function _noopClient() {
  if (typeof window !== "undefined" && !window.__supabase_warned__) {
    console.warn(
      "[supabase] REACT_APP_SUPABASE_URL / REACT_APP_SUPABASE_ANON_KEY not set at build time. " +
      "Audit-log views will be empty. Set these as Railway build variables and redeploy to enable."
    );
    window.__supabase_warned__ = true;
  }
  const _stub = {
    from: () => _stub,
    select: () => Promise.resolve({ data: [], error: null }),
    insert: () => Promise.resolve({ data: null, error: null }),
    update: () => Promise.resolve({ data: null, error: null }),
    upsert: () => Promise.resolve({ data: null, error: null }),
    delete: () => Promise.resolve({ data: null, error: null }),
    eq: () => _stub,
    neq: () => _stub,
    in: () => _stub,
    order: () => _stub,
    limit: () => _stub,
    single: () => Promise.resolve({ data: null, error: null }),
    auth: {
      getSession: () => Promise.resolve({ data: { session: null }, error: null }),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } }),
    },
    channel: () => ({ on: () => _stub, subscribe: () => _stub, unsubscribe: () => {} }),
    removeChannel: () => {},
  };
  return _stub;
}

export const supabase = (supabaseUrl && supabaseAnonKey)
  ? createClient(supabaseUrl, supabaseAnonKey)
  : _noopClient();
