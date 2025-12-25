// React'tan gerekli hook'ları import ediyoruz:
// - useState: state tutmak için
// - useEffect: sayfa açılınca/param değişince işlem yapmak için
// - useMemo: hesaplanan değeri (score) gereksiz yere her render'da hesaplamamak için
import { useEffect, useMemo, useState } from "react";

// react-router-dom'dan:
// - useParams: URL'deki :id parametresini almak için
// - useNavigate: sayfalar arası yönlendirme yapmak için
import { useNavigate, useParams } from "react-router-dom";

// Bizim ortak JSON fetch helper'ımız (JSON gelmezse net hata üretir)
import { fetchJson } from "../lib/api";

// Bu component /companies/:id sayfasının detay ekranı
export default function CompanyDetail() {
  // URL'den şirket id'sini alır (Route: /companies/:id)
  const { id } = useParams();

  // Navigasyon fonksiyonu (listeye dön vb.)
  const nav = useNavigate();

  // Dashboard verisi (backend'den gelecek JSON)
  const [dash, setDash] = useState(null);

  // Hata mesajı (UI'da kırmızı basacağız)
  const [err, setErr] = useState("");

  // Yükleme durumu
  const [loading, setLoading] = useState(true);

  // Hangi obligation üzerinde işlem yapılıyor? (butonu disable etmek için)
  const [busyId, setBusyId] = useState(null);

  // Skoru tek yerde normalize ediyoruz:
  // bazen backend uyum_skoru döner, bazen compliance_score döner
  // dash yoksa "-" göster
  const score = useMemo(() => {
    if (!dash) return "-";
    return dash.uyum_skoru ?? dash.compliance_score ?? "-";
  }, [dash]);

  // Dashboard yükleme fonksiyonu
  // signal parametresi AbortController'dan gelir: sayfadan çıkınca fetch iptal olsun diye
  async function load(signal) {
    try {
      // yükleniyor state'ini aç
      setLoading(true);

      // eski hatayı temizle
      setErr("");

      // Dashboard JSON endpoint'inden veriyi çekiyoruz
      // Vite proxy varsa /api/... direkt backend'e gider
      const json = await fetchJson(`/api/companies-spa/${id}/dashboard/`, {
        signal, // abort desteği
      });

      // gelen JSON'u state'e bas
      setDash(json);
    } catch (e) {
      // AbortError ise kullanıcı sayfadan çıktı demektir -> hata basmayız
      if (e?.name !== "AbortError") setErr(e?.message || String(e));
    } finally {
      // yükleme bitti
      setLoading(false);
    }
  }

  // id değişince (başka şirkete gidince) otomatik yeniden dashboard çek
  useEffect(() => {
    // fetch iptali için controller
    const ac = new AbortController();

    // dashboard yükle
    load(ac.signal);

    // component unmount olunca veya id değişince fetch'i iptal et
    return () => ac.abort();

    // eslint disable: load function dependency uyarısı vermesin diye
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Obligation'ı tamamla/geri al (PATCH)
  async function patchObligation(obligationId, isCompliant) {
    try {
      // hangi item işleniyor -> o butonu "İşleniyor..." yapacağız
      setBusyId(obligationId);

      // önceki hatayı temizle
      setErr("");

      // PATCH endpoint'ine is_compliant true/false gönderiyoruz
      const r = await fetch(`/api/obligations/${obligationId}/status/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json", // body JSON gönderiyoruz
          Accept: "application/json",         // JSON bekliyoruz
        },
        body: JSON.stringify({ is_compliant: isCompliant }),
      });

      // response body'yi text olarak alıyoruz
      // (JSON olmayabilir, hata mesajı olabilir)
      const text = await r.text();

      // HTTP 200 değilse hata fırlat
      if (!r.ok) {
        throw new Error(
          `PATCH fail. Status=${r.status}. Body: ${text.slice(0, 200)}`
        );
      }

      // PATCH response JSON mu diye deniyoruz
      let json = null;
      try {
        json = JSON.parse(text);
      } catch {
        json = null;
      }

      // Eğer backend PATCH cevabında direkt dashboard döndürüyorsa
      // yeniden GET yapmadan UI güncellenir
      if (json && (json.todo || json.completed || json.stats || json.sirket)) {
        setDash(json);
      } else {
        // Yoksa fallback: dashboard'u tekrar çek
        await load();
      }
    } catch (e) {
      // hata mesajını state'e yaz
      setErr(e?.message || String(e));
    } finally {
      // işlem bitti -> busy durumunu kapat
      setBusyId(null);
    }
  }

  // Todo listesi yoksa boş array kullan (UI patlamasın)
  const todo = dash?.todo ?? [];

  // Completed listesi yoksa boş array kullan
  const completed = dash?.completed ?? [];

  // UI render
  return (
    <div style={{ padding: 24 }}>
      {/* Liste sayfasına geri dön */}
      <button type="button" onClick={() => nav("/companies")}>
        ← Listeye dön
      </button>

      {/* Sayfa başlığı */}
      <h1 style={{ marginTop: 12 }}>Şirket Detay</h1>

      {/* Hata varsa kırmızı bas */}
      {err && <p style={{ color: "red" }}>Hata: {err}</p>}

      {/* Yükleniyorsa bilgi bas */}
      {loading && <p>Yükleniyor...</p>}

      {/* Yükleme bittiyse ve dash geldiyse detayları göster */}
      {!loading && dash && (
        <>
          {/* Şirket adı ve id */}
          <h2 style={{ marginTop: 12 }}>
            {dash.sirket?.name} (ID: {dash.sirket?.id})
          </h2>

          {/* Skor */}
          <p>
            Skor: <b>{score}</b>
          </p>

          {/* İstatistik */}
          <h3>İstatistik</h3>
          <ul>
            <li>Total: {dash.stats?.total_obligations ?? "-"}</li>
            <li>Açık: {dash.stats?.open_obligations ?? "-"}</li>
            <li>Gecikmiş: {dash.stats?.overdue_obligations ?? "-"}</li>
          </ul>

          {/* TODO listesi */}
          <h3>Yapılacaklar (TODO)</h3>
          {todo.length === 0 ? (
            <p>Todo yok 🎉</p>
          ) : (
            <ul>
              {todo.map((t) => (
                <li key={t.obligation_id} style={{ marginBottom: 10 }}>
                  {/* Yükümlülük başlığı */}
                  <div>
                    <b>{t.regulation_title}</b>
                  </div>

                  {/* Detay satırı */}
                  <div style={{ opacity: 0.8 }}>
                    due: {t.due_date} — risk: {t.risk_level} — etki: {t.impact_type}
                  </div>

                  {/* Tamamlandı butonu: busyId bu obligation ise disable + "İşleniyor..." */}
                  <button
                    type="button"
                    disabled={busyId === t.obligation_id}
                    onClick={() => patchObligation(t.obligation_id, true)}
                  >
                    {busyId === t.obligation_id ? "İşleniyor..." : "Tamamlandı"}
                  </button>
                </li>
              ))}
            </ul>
          )}

          {/* Completed listesi */}
          <h3>Tamamlananlar</h3>
          {completed.length === 0 ? (
            <p>Henüz tamamlanan yok</p>
          ) : (
            <ul>
              {completed.map((t) => (
                <li key={t.obligation_id} style={{ marginBottom: 10 }}>
                  {/* Tamamlanan yükümlülük başlığı */}
                  <div>
                    <b>{t.regulation_title}</b>
                  </div>

                  {/* Detay satırı */}
                  <div style={{ opacity: 0.8 }}>
                    due: {t.due_date} — risk: {t.risk_level} — etki: {t.impact_type}
                  </div>

                  {/* Geri al butonu: is_compliant false gönderir */}
                  <button
                    type="button"
                    disabled={busyId === t.obligation_id}
                    onClick={() => patchObligation(t.obligation_id, false)}
                  >
                    {busyId === t.obligation_id ? "İşleniyor..." : "Geri al"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
