"use client";
import { useState, useEffect, useRef } from "react";

interface NotificationEvent {
  type: string;
  bill_id?: string;
  label_el?: string;
  message_el?: string;
  milestone?: number;
}

interface Props {
  billId?: string;
  maxItems?: number;
}

export default function LiveNotifications({ billId, maxItems = 5 }: Props) {
  const [events, setEvents]       = useState<NotificationEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const BASE = process.env.NEXT_PUBLIC_API_URL || "https://api.ekklesia.gr";
    const url = `${BASE}/api/v1/notifications/stream${billId ? `?bill_id=${billId}` : ""}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (e) => {
      try {
        const data: NotificationEvent = JSON.parse(e.data);
        if (data.type === "heartbeat" || data.type === "connected") return;
        setEvents(prev => [data, ...prev].slice(0, maxItems));
      } catch { /* ignore */ }
    };

    return () => { es.close(); setConnected(false); };
  }, [billId, maxItems]);

  if (!connected && events.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-xs">
      <div className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full self-end ${
        connected ? "bg-green-900 text-green-300" : "bg-gray-800 text-gray-400"
      }`}>
        <span className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-green-400 animate-pulse" : "bg-gray-600"}`} />
        {connected ? "Live" : "Offline"}
      </div>
      {events.map((ev, i) => (
        <div key={i} className="bg-gray-900 border border-gray-700 rounded-xl p-3 shadow-lg text-sm">
          <div className="font-bold text-xs text-blue-400 mb-1">{ev.type}</div>
          {ev.label_el && <p className="text-gray-300 text-xs">{ev.label_el}</p>}
          {ev.message_el && <p className="text-gray-300 text-xs">{ev.message_el}</p>}
          {ev.milestone && <p className="text-yellow-400 font-bold text-xs">{ev.milestone} votes!</p>}
        </div>
      ))}
    </div>
  );
}
