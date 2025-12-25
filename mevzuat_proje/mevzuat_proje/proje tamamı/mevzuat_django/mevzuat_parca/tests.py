# Zaman hesapları için (due_date -1 gün gibi)
from datetime import timedelta

# Django test altyapısı
from django.test import TestCase

# URL name’leriyle endpoint üretmek için
from django.urls import reverse

# Tarih/saat işlemleri (timezone.localdate() vs)
from django.utils import timezone

# DRF test client (API istekleri için: GET/PATCH/POST)
from rest_framework.test import APIClient

# Testte kullanılacak modeller
from .models import Sirket, Duzenleme, SirketObligation

# Skor hesaplayan fonksiyonu direkt test edeceğiz
from .views import hesapla_sirket_skoru


# Test sınıfı: Django her testte ayrı bir test DB kurar (izole)
class RegTechBasicTests(TestCase):

    # Her testten önce çalışır (hazırlık)
    def setUp(self):
        # DRF APIClient: JSON format, patch vb kolay
        self.api = APIClient()

    # ---------------------------------------
    # 1) Düzenleme kaydedilince otomatik tag/sector/impact doluyor mu?
    # ---------------------------------------
    def test_duzenleme_save_auto_tags_sectors_impact(self):
        # Düzenleme kaydı oluşturuyoruz
        d = Duzenleme.objects.create(
            source="gib",                            # kaynağı
            title="Yeni KDV Tebliği",                # başlık
            publish_date=timezone.localdate(),       # bugün
            raw_text="KDV zorunludur. Yazılım şirketleri için yeni beyan şartı vardır.",
        )

        # nlp_rules.py gibi otomatik doldurma yapan kod çalıştı mı kontrol:
        self.assertIn("KDV", d.tags)                 # tags içinde "KDV" var mı?
        self.assertIn("vergi", d.tags)               # tags içinde "vergi" var mı?
        self.assertIn("yazilim", d.sectors)          # sectors içinde "yazilim" var mı?
        self.assertEqual(d.impact_type, "zorunlu")   # etki tipi zorunlu mu?

    # ---------------------------------------
    # 2) Şirkette hiç obligation yoksa skor 100 olmalı mı?
    # ---------------------------------------
    def test_hesapla_sirket_skoru_no_obligation_100(self):
        # Obilgation’sız şirket oluşturuyoruz
        s = Sirket.objects.create(
            name="Demo A.Ş.",
            sector="yazilim",
            employee_count=10,
            location_city="İstanbul",
            is_exporter=False,
        )

        # Skor fonksiyonunu çağır
        result = hesapla_sirket_skoru(s)

        # Skor 100 bekleniyor
        self.assertEqual(result["score"], 100)

        # Obligation sayısı 0 olmalı
        self.assertEqual(result["stats"]["total_obligations"], 0)

        # Todo / Completed boş olmalı
        self.assertEqual(len(result["todo"]), 0)
        self.assertEqual(len(result["completed"]), 0)

    # ---------------------------------------
    # 3) Dashboard API doğru key’leri dönüyor mu?
    # ---------------------------------------
    def test_dashboard_api_returns_expected_keys(self):
        # Şirket oluştur
        s = Sirket.objects.create(
            name="Test Ltd",
            sector="imalat",
            employee_count=50,
            location_city="Bursa",
            is_exporter=True,
        )

        # Düzenleme oluştur
        r = Duzenleme.objects.create(
            source="resmi_gazete",
            title="Zorunlu Bildirim",
            publish_date=timezone.localdate(),
            raw_text="Bu bildirim zorunludur.",
            impact_type="zorunlu",
            tags=["vergi"],
            sectors=["imalat"],
        )

        # Şirkete uygulanabilir bir obligation ekle (gecikmiş + high risk)
        SirketObligation.objects.create(
            sirket=s,
            duzenleme=r,
            is_applicable=True,
            is_compliant=False,
            due_date=timezone.localdate() - timedelta(days=1),  # dün -> overdue
            risk_level="high",
        )

        # URL name ile endpoint üret
        url = reverse("Sirket-dashboard", kwargs={"pk": s.pk})

        # API GET at
        res = self.api.get(url)

        # 200 dönmeli
        self.assertEqual(res.status_code, 200)

        # JSON parse et
        data = res.json()

        # Beklenen temel alanlar var mı?
        self.assertIn("sirket", data)
        self.assertIn("uyum_skoru", data)
        self.assertIn("stats", data)
        self.assertIn("todo", data)
        self.assertIn("completed", data)

        # todo ve completed list tipinde olmalı
        self.assertTrue(isinstance(data["todo"], list))
        self.assertTrue(isinstance(data["completed"], list))

    # ---------------------------------------
    # 4) PATCH ile obligation todo<->completed arasında taşınıyor mu?
    # ---------------------------------------
    def test_obligation_status_api_toggle_moves_between_lists(self):
        # Şirket oluştur
        s = Sirket.objects.create(
            name="Toggle Co",
            sector="perakende",
            employee_count=5,
            location_city="Ankara",
            is_exporter=False,
        )

        # Düzenleme oluştur
        r = Duzenleme.objects.create(
            source="gib",
            title="Yükümlülük X",
            publish_date=timezone.localdate(),
            raw_text="Bu yükümlülük zorunludur.",
            impact_type="zorunlu",
            tags=["vergi"],
            sectors=["perakende"],
        )

        # Obligation oluştur (başta uyumsuz)
        obl = SirketObligation.objects.create(
            sirket=s,
            duzenleme=r,
            is_applicable=True,
            is_compliant=False,
            due_date=timezone.localdate() - timedelta(days=1),
            risk_level="high",
        )

        # Önce dashboard çek -> todo=1, completed=0 beklenir
        dash_url = reverse("Sirket-dashboard", kwargs={"pk": s.pk})
        before = self.api.get(dash_url).json()
        self.assertEqual(len(before["todo"]), 1)
        self.assertEqual(len(before["completed"]), 0)

        # PATCH endpoint URL’i
        patch_url = reverse("obligation-status-api", kwargs={"pk": obl.pk})

        # 1) Tamamlandı yap (true)
        res1 = self.api.patch(patch_url, {"is_compliant": True}, format="json")
        self.assertEqual(res1.status_code, 200)
        json1 = res1.json()

        # PATCH cevabı dashboard dönüyor -> key’ler var mı?
        self.assertIn("uyum_skoru", json1)
        self.assertIn("todo", json1)
        self.assertIn("completed", json1)

        # Tamamlandı olunca todo boş, completed 1 olmalı
        self.assertEqual(len(json1["todo"]), 0)
        self.assertEqual(len(json1["completed"]), 1)

        # completed içindeki obligation_id doğru mu?
        self.assertEqual(json1["completed"][0]["obligation_id"], obl.pk)

        # 2) Geri al (false)
        res2 = self.api.patch(patch_url, {"is_compliant": False}, format="json")
        self.assertEqual(res2.status_code, 200)
        json2 = res2.json()

        # Geri alınınca todo 1, completed 0 olmalı
        self.assertEqual(len(json2["todo"]), 1)
        self.assertEqual(len(json2["completed"]), 0)
        self.assertEqual(json2["todo"][0]["obligation_id"], obl.pk)

    # ---------------------------------------
    # 5) Riskli filtre doğru çalışıyor mu? (?risky=true&threshold=80)
    # ---------------------------------------
    def test_companies_list_risky_filter_returns_only_low_scores(self):
        # Düşük skor üretilecek şirket
        low = Sirket.objects.create(
            name="Riskli Şirket",
            sector="lojistik",
            employee_count=20,
            location_city="İzmir",
            is_exporter=False,
        )

        # Yükümlülük verilmeyecek şirket (yüksek skor beklenir)
        high = Sirket.objects.create(
            name="Sağlam Şirket",
            sector="lojistik",
            employee_count=20,
            location_city="İzmir",
            is_exporter=False,
        )

        # Düzenleme oluştur
        r = Duzenleme.objects.create(
            source="resmi_gazete",
            title="Ceza Riski",
            publish_date=timezone.localdate(),
            raw_text="Bu yükümlülük zorunludur. İdari para cezası vardır.",
            impact_type="zorunlu",
            tags=["vergi"],
            sectors=["lojistik"],
        )

        # Sadece low şirketine obligation ekle -> skor düşsün
        SirketObligation.objects.create(
            sirket=low,
            duzenleme=r,
            is_applicable=True,
            is_compliant=False,
            due_date=timezone.localdate() - timedelta(days=1),  # overdue
            risk_level="high",
        )

        # ?risky=true -> threshold altını bekliyoruz
        url = reverse("Sirket-list-create") + "?risky=true&threshold=80"
        res = self.api.get(url)
        self.assertEqual(res.status_code, 200)

        # Dönen şirket id’lerini al
        data = res.json()
        ids = [item["id"] for item in data]

        # low listede olmalı, high olmamalı
        self.assertIn(low.id, ids)
        self.assertNotIn(high.id, ids)

    # ---------------------------------------
    # 6) SPA detail template içinde data-company-id var mı?
    # (React’e id aktarımı için)
    # ---------------------------------------
    def test_companies_spa_detail_page_has_data_company_id(self):
        # Şirket oluştur
        s = Sirket.objects.create(
            name="SPA Co",
            sector="yazilim",
            employee_count=3,
            location_city="İstanbul",
            is_exporter=False,
        )

        # SPA detail sayfası URL’i (HTML)
        url = reverse("companies_spa_detail", kwargs={"pk": s.pk})
        res = self.client.get(url)  # Django'nun built-in test client’ı

        # 200 dönmeli
        self.assertEqual(res.status_code, 200)

        # HTML içinde data-company-id attribute’u var mı?
        self.assertContains(res, 'data-company-id')

        # ID doğru mu? (sayfada şirket id’si yazıyor mu?)
        self.assertContains(res, str(s.pk))

    # ---------------------------------------
    # 7) Klasik dashboard JSON ile SPA dashboard JSON aynı mı?
    # ---------------------------------------
    def test_dashboard_and_spa_dashboard_payloads_match(self):
        # Test DB boş olabileceği için kendi şirketimizi yaratıyoruz
        kwargs = dict(
            name="Test Yazılım A.Ş.",
            sector="yazilim",
            employee_count=20,
            location_city="İstanbul",
            is_exporter=True,
        )

        # Bazı sürümlerde Sirket modelinde 'unvan' alanı olabilir -> varsa doldur
        field_names = {f.name for f in Sirket._meta.fields}
        if "unvan" in field_names:
            kwargs["unvan"] = "Test Yazılım A.Ş."

        # Şirket oluştur
        sirket = Sirket.objects.create(**kwargs)

        # 1) Eski endpoint: /api/companies/<pk>/dashboard/
        url1 = reverse("Sirket-dashboard", args=[sirket.id])

        # 2) SPA endpoint: /api/companies-spa/<pk>/dashboard/
        url2 = reverse("sirket-dashboard-api", args=[sirket.id])

        # GET istekleri
        r1 = self.client.get(url1)
        r2 = self.client.get(url2)

        # İkisi de 200 dönmeli (aksi halde mesaj bas)
        self.assertEqual(r1.status_code, 200, f"dashboard 200 değil: {r1.status_code} url={url1}")
        self.assertEqual(r2.status_code, 200, f"spa dashboard 200 değil: {r2.status_code} url={url2}")

        # JSON payload’lar birebir aynı olmalı
        self.assertEqual(r1.json(), r2.json())
