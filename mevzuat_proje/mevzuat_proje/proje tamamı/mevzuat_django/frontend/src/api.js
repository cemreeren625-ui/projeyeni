export const API_BASE = "http://127.0.0.1:8000";

export async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
// src/lib/api.js
// Ortak JSON fetch helper'ı: JSON gelmezse (HTML gelirse) hatayı net gösterir.
export async function fetchJson(url, options = {}) {
  const headers = {
    Accept: "application/json",
    ...(options.headers || {}),
  };

  const r = await fetch(url, { ...options, headers });

  // Her durumda text alıyoruz ki HTML gelirse ilk kısmını hatada gösterebilelim
  const text = await r.text();
  const ct = (r.headers.get("content-type") || "").toLowerCase();

  if (!r.ok) {
    throw new Error(`HTTP ${r.status} ${r.statusText}. Body: ${text.slice(0, 200)}`);
  }

  // JSON değilse (HTML döndüyse) burada yakala
  if (!ct.includes("application/json")) {
    throw new Error(
      `JSON gelmedi (content-type=${ct || "yok"}). İlk 120 char: ${text.slice(0, 120)}`
    );
  }

  return JSON.parse(text);
}
