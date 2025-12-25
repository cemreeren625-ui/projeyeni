// Vite config tanımlamak için yardımcı fonksiyon
import { defineConfig } from "vite";

// React + SWC (çok hızlı derleme) plugin’i
import react from "@vitejs/plugin-react-swc";

// Vite yapılandırması
export default defineConfig({
  // Vite'a React desteğini ekliyoruz
  plugins: [react()],

  // "npm run dev" ile açılan Vite geliştirme sunucusu ayarları
  server: {
    // Proxy ayarları: Frontend’den "/api/..." çağırınca
    // bunu arka planda Django’ya yönlendirir
    proxy: {
      "/api": {
        // Backend adresi (Django dev server)
        target: "http://127.0.0.1:8000",

        // Origin header'ını target'a göre değiştirir
        // (bazı backend'ler için gerekli olur)
        changeOrigin: true,

        // HTTPS sertifika kontrolü kapalı
        // (biz HTTP kullandığımız için genelde sorun olmaz ama güvenli)
        secure: false,
      },
    },
  },
});
