export interface PipelineEvent {
  type: string;
  application_id: string;
  [key: string]: any;
}

export function openStream(
  path: string,
  onMessage: (e: PipelineEvent) => void,
): WebSocket {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${window.location.host}${path}`);
  ws.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data));
    } catch {
      /* ignore malformed frames */
    }
  };
  return ws;
}
