import { API_PREFIX, WS_BASE_URL } from "./config";
import type { JobProgressEvent } from "@/types";

/**
 * Subscribe to live job progress over WebSocket.
 * Returns a cleanup function that closes the socket.
 */
export function subscribeJobProgress(
  jobId: string,
  onEvent: (event: JobProgressEvent) => void,
): () => void {
  const url = `${WS_BASE_URL}${API_PREFIX}/ws/jobs/${jobId}`;
  const socket = new WebSocket(url);

  socket.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data) as JobProgressEvent;
      if (data.type === "ping") return;
      onEvent(data);
    } catch {
      /* ignore malformed frames */
    }
  };

  return () => {
    try {
      socket.close();
    } catch {
      /* noop */
    }
  };
}
