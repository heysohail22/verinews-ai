"use client";

import { useMemo, useSyncExternalStore } from "react";

const listeners = new Set<() => void>();
const memory = new Map<string, string>();
function subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; }
export function saveWorkspace(key: string, value: unknown) {
  const text = JSON.stringify(value);
  memory.set(key, text);
  try { sessionStorage.setItem(key, text); } catch { /* Keep navigation working when storage is full. */ }
  listeners.forEach(listener => listener());
}
function snapshot(key: string) {
  if (memory.has(key)) return memory.get(key)!;
  try { return sessionStorage.getItem(key); } catch { return null; }
}
export function useWorkspace<T>(key: string): T | null {
  const raw = useSyncExternalStore(subscribe, () => snapshot(key), () => null);
  return useMemo(() => { try { return raw ? JSON.parse(raw) as T : null; } catch { return null; } }, [raw]);
}
