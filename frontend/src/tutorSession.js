// Reads the voice tutor's session (recognition/tutor_runner.py GET /session).
//
// The tutor listens on the same address and token as the glasses relay, so it
// uses the relay settings already saved in this browser. While live_runner
// runs instead of the tutor, /session is missing and status is "unavailable".
//
// Session shape:
// { revision, project: null | { id, title, parts: [..], steps: [{ say }] },
//   step_index, step_count, finished, pending_plan: null | { title, parts, missing },
//   components: [..] }

import { useEffect, useState } from "react";

const POLL_MS = 1000;

// status: "off" (no relay set) | "connecting" | "live" | "unavailable"
export function useTutorSession(relay) {
  const [state, setState] = useState({ status: relay ? "connecting" : "off", session: null });

  useEffect(() => {
    if (!relay) {
      setState({ status: "off", session: null });
      return undefined;
    }
    let stopped = false;
    let timer = null;
    let controller = null;
    const url = `${relay.url}/session?token=${encodeURIComponent(relay.token)}`;

    const poll = async () => {
      controller = new AbortController();
      const abortTimer = setTimeout(() => controller.abort(), 4000);
      try {
        const response = await fetch(url, { cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error(String(response.status));
        const text = await response.text();
        const session = JSON.parse(text);
        if (!stopped) {
          // Only re-render when something changed (a tutor restart resets the revision, so compare content).
          setState((prev) => (prev.status === "live" && prev.raw === text ? prev : { status: "live", session, raw: text }));
        }
      } catch {
        // Keep the last session on screen so a brief network blip doesn't empty the drawer.
        if (!stopped) setState((prev) => ({ status: "unavailable", session: prev.session }));
      } finally {
        clearTimeout(abortTimer);
        if (!stopped) timer = setTimeout(poll, POLL_MS);
      }
    };

    setState({ status: "connecting", session: null });
    poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
      controller?.abort();
    };
  }, [relay?.url, relay?.token]); // eslint-disable-line react-hooks/exhaustive-deps

  return state;
}
