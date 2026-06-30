import { wsUrl } from "./auth";

export interface PipelineEvent {
  type: string;
  application_id: string;
  [key: string]: any;
}

export function openStream(
  path: string,
  onMessage: (e: PipelineEvent) => void,
): WebSocket {
  const ws = new WebSocket(wsUrl(path));
  ws.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data));
    } catch {
      /* ignore malformed frames */
    }
  };
  return ws;
}
