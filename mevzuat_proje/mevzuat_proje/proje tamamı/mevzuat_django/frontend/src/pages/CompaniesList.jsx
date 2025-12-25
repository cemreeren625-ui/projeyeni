import { useEffect, useMemo, useState } from "react"; // React hook'ları
import { useNavigate } from "react-router-dom"; // sayfa yönlendirme
import { fetchJson } from "../lib/api"; // JSON fetch helper

export default function CompaniesList() {
  // Şirket listesi (API'den gelecek)
  const [data, setData] = useState([]);

  // Hata mesajı (UI'da basacağız)
  const [err, setErr] = useState("");

  // Yükleniyor mu? (spinner/text basacağız)
  const [loading, setLoading] = useState(true);

  // Filtre state'leri (projeye uygun: sektör + riskli checkbox)
  const [sector, setSector] = useState(""); // "" = tüm sektörler
  const [riskyOnly, setRiskyOnly] = useState(false); // skor<threshold
  const [threshold, setThreshold] = useState(80); // default eşik

  // React Router navigate fonksiyonu
  const nav = useNavigate();

  // Query string'i tek yerde üret (sector + risky + threshold)
  const listUrl = useMemo(() => {
    const p = new URLSearchParams();

    // sector seçiliyse ekle
    if (sector) p.set("sector", sector);

    // riskyOnly true ise API tarafı riskli filtreyi uygulasın
    if (riskyOnly) {
      p.set("risky", "true");
      p.set("threshold", String(threshold));
    }

    // DRF şirket listesi endpoint'i (JSON döner)
    const qs = p.toString();
    return qs ? `/api/companies/?${qs}` : `/api/companies/`;
  }, [sector, riskyOnly, threshold]);

  // Sayfa açılınca + filtre değişince listeyi çek
  useEffect(() => {
    const ac = new AbortController(); // sayfadan çıkınca fetch iptal

    (async () => {
      try {
        setLoading(true);
        setErr("");

        // JSON beklediğimiz doğru endpoint: /api/companies/
        const json = await fetchJson(listUrl, { signal: ac.signal });

        // API list döndürür (array)
        setData(Array.isArray(json) ? json : []);
      } catch (e) {
        // abort ise hata yazma
        if (e?.name !== "AbortError") setErr(e?.message || String(e));
      } finally {
        setLoading(false);
      }
    })();

    return () => ac.abort();
  }, [listUrl]);

  return (
    <div style={{ padding: 24 }}>
      <h1>Şirketler (SPA)</h1>

      {/* Filtre alanı */}
      <div style={{ display: "flex", gap: 12, alignItems: "center", margin: "12px 0" }}>
        {/* Sektör dropdown */}
        <label>
          Sektör:&nbsp;
          <select value={sector} onChange={(e) => setSector(e.target.value)}>
            <option value="">Tümü</option>
            <option value="yazilim">yazılım</option>
            <option value="imalat">imalat</option>
            <option value="perakende">perakende</option>
            <option value="lojistik">lojistik</option>
          </select>
        </label>

        {/* Riskli checkbox */}
        <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <input
            type="checkbox"
            checked={riskyOnly}
            onChange={(e) => setRiskyOnly(e.target.checked)}
          />
          Sadece riskli (skor &lt; {threshold})
        </label>

        {/* Threshold input (sadece risky açıkken anlamlı) */}
        <label>
          Eşik:&nbsp;
          <input
            type="number"
            value={threshold}
            min={0}
            max={100}
            onChange={(e) => setThreshold(Number(e.target.value || 80))}
            style={{ width: 80 }}
            disabled={!riskyOnly}
          />
        </label>

        {/* Filtreyi temizle */}
        <button
          type="button"
          onClick={() => {
            setSector("");
            setRiskyOnly(false);
            setThreshold(80);
          }}
        >
          Filtreyi temizle
        </button>
      </div>

      {/* Hata / yükleniyor */}
      {err && <p style={{ color: "red" }}>Hata: {err}</p>}
      {loading && <p>Yükleniyor...</p>}

      {/* Liste */}
      {!loading && !err && (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", padding: 12 }}>Şirket</th>
              <th style={{ textAlign: "left", padding: 12 }}>Skor</th>
              <th style={{ textAlign: "right", padding: 12 }}>İşlemler</th>
            </tr>
          </thead>
          <tbody>
            {data.map((c) => (
              <tr
                key={c.id}
                onClick={() => nav(`/companies/${c.id}`)} // satıra tıkla -> detay route
                style={{ cursor: "pointer", borderTop: "1px solid #ddd" }}
              >
                <td style={{ padding: 12 }}>
                  <div style={{ fontWeight: 700 }}>{c.name}</div>
                  <div style={{ opacity: 0.7 }}>ID: {c.id}</div>
                </td>

                <td style={{ padding: 12 }}>
                  {/* farklı isimlerle gelebilir: compliance_score / uyum_skoru */}
                  {c.compliance_score ?? c.uyum_skoru ?? "-"}
                </td>

                <td style={{ padding: 12, textAlign: "right" }}>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation(); // satır click'ini engelle
                      // proxy sayesinde relative URL ile Django HTML panel açılır
                      window.open(`/api/companies/${c.id}/dashboard-page/`, "_blank");
                    }}
                  >
                    HTML Paneli
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
