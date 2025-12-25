from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from mevzuat_parca.models import Sirket, Duzenleme, SirketObligation
from mevzuat_parca.views import hesapla_sirket_skoru
from django.db import connection
from django.test.utils import CaptureQueriesContext


class RegTechBasicTests(TestCase):
    def setUp(self):
        self.api = APIClient()

    def test_duzenleme_save_auto_tags_sectors_impact(self):
        d = Duzenleme.objects.create(
            source="gib",
            title="Yeni KDV Tebliği",
            publish_date=timezone.localdate(),
            raw_text="KDV zorunludur. Yazılım şirketleri için yeni beyan şartı vardır.",
        )
        # nlp_rules.py -> otomatik doldurma bekliyoruz
        self.assertIn("KDV", d.tags)
        self.assertIn("vergi", d.tags)
        self.assertIn("yazilim", d.sectors)
        self.assertEqual(d.impact_type, "zorunlu")

    def test_hesapla_sirket_skoru_no_obligation_100(self):
        s = Sirket.objects.create(
            name="Demo A.Ş.",
            sector="yazilim",
            employee_count=10,
            location_city="İstanbul",
            is_exporter=False,
        )
        result = hesapla_sirket_skoru(s)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["stats"]["total_obligations"], 0)
        self.assertEqual(len(result["todo"]), 0)
        self.assertEqual(len(result["completed"]), 0)

    def test_dashboard_api_returns_expected_keys(self):
        s = Sirket.objects.create(
            name="Test Ltd",
            sector="imalat",
            employee_count=50,
            location_city="Bursa",
            is_exporter=True,
        )
        r = Duzenleme.objects.create(
            source="resmi_gazete",
            title="Zorunlu Bildirim",
            publish_date=timezone.localdate(),
            raw_text="Bu bildirim zorunludur.",
            impact_type="zorunlu",
            tags=["vergi"],
            sectors=["imalat"],
        )
        SirketObligation.objects.create(
            sirket=s,
            duzenleme=r,
            is_applicable=True,
            is_compliant=False,
            due_date=timezone.localdate() - timedelta(days=1),
            risk_level="high",
        )

        url = reverse("Sirket-dashboard", kwargs={"pk": s.pk})
        res = self.api.get(url)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertIn("sirket", data)
        self.assertIn("uyum_skoru", data)
        self.assertIn("stats", data)
        self.assertIn("todo", data)
        self.assertIn("completed", data)

        self.assertTrue(isinstance(data["todo"], list))
        self.assertTrue(isinstance(data["completed"], list))

    def test_obligation_status_api_toggle_moves_between_lists(self):
        s = Sirket.objects.create(
            name="Toggle Co",
            sector="perakende",
            employee_count=5,
            location_city="Ankara",
            is_exporter=False,
        )
        r = Duzenleme.objects.create(
            source="gib",
            title="Yükümlülük X",
            publish_date=timezone.localdate(),
            raw_text="Bu yükümlülük zorunludur.",
            impact_type="zorunlu",
            tags=["vergi"],
            sectors=["perakende"],
        )
        obl = SirketObligation.objects.create(
            sirket=s,
            duzenleme=r,
            is_applicable=True,
            is_compliant=False,
            due_date=timezone.localdate() - timedelta(days=1),
            risk_level="high",
        )

        dash_url = reverse("Sirket-dashboard", kwargs={"pk": s.pk})
        before = self.api.get(dash_url).json()
        self.assertEqual(len(before["todo"]), 1)
        self.assertEqual(len(before["completed"]), 0)

        patch_url = reverse("obligation-status-api", kwargs={"pk": obl.pk})

        # 1) Tamamlandı yap
        res1 = self.api.patch(patch_url, {"is_compliant": True}, format="json")
        self.assertEqual(res1.status_code, 200)
        json1 = res1.json()

        # PATCH cevabı dashboard döndürüyor -> onu doğrula
        self.assertIn("uyum_skoru", json1)
        self.assertIn("todo", json1)
        self.assertIn("completed", json1)
        self.assertEqual(len(json1["todo"]), 0)
        self.assertEqual(len(json1["completed"]), 1)
        self.assertEqual(json1["completed"][0]["obligation_id"], obl.pk)

        # 2) Geri al
        res2 = self.api.patch(patch_url, {"is_compliant": False}, format="json")
        self.assertEqual(res2.status_code, 200)
        json2 = res2.json()

        self.assertEqual(len(json2["todo"]), 1)
        self.assertEqual(len(json2["completed"]), 0)
        self.assertEqual(json2["todo"][0]["obligation_id"], obl.pk)


    def test_companies_list_risky_filter_returns_only_low_scores(self):
        # düşük skor üretelim
        low = Sirket.objects.create(
            name="Riskli Şirket",
            sector="lojistik",
            employee_count=20,
            location_city="İzmir",
            is_exporter=False,
        )
        high = Sirket.objects.create(
            name="Sağlam Şirket",
            sector="lojistik",
            employee_count=20,
            location_city="İzmir",
            is_exporter=False,
        )

        r = Duzenleme.objects.create(
            source="resmi_gazete",
            title="Ceza Riski",
            publish_date=timezone.localdate(),
            raw_text="Bu yükümlülük zorunludur. İdari para cezası vardır.",
            impact_type="zorunlu",
            tags=["vergi"],
            sectors=["lojistik"],
        )
        SirketObligation.objects.create(
            sirket=low,
            duzenleme=r,
            is_applicable=True,
            is_compliant=False,
            due_date=timezone.localdate() - timedelta(days=1),
            risk_level="high",
        )

        url = reverse("Sirket-list-create") + "?risky=true&threshold=80"
        res = self.api.get(url)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        ids = [item["id"] for item in data]
        self.assertIn(low.id, ids)
        self.assertNotIn(high.id, ids)

    def test_companies_spa_detail_page_has_data_company_id(self):
        s = Sirket.objects.create(
            name="SPA Co",
            sector="yazilim",
            employee_count=3,
            location_city="İstanbul",
            is_exporter=False,
        )
        url = reverse("companies_spa_detail", kwargs={"pk": s.pk})
        res = self.client.get(url)  # Django test client
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'data-company-id')
        self.assertContains(res, str(s.pk))
    def test_sirket_list_page_no_nplus1(self):
        # 20 şirket üret
        for i in range(20):
            Sirket.objects.create(
                name=f"S{i}",
                sector="yazilim",
                employee_count=1,
                location_city="İstanbul",
                is_exporter=False,
            )
    
        url = reverse("sirket-list-page")
    
        with CaptureQueriesContext(connection) as ctx:
            res = self.client.get(url)

        self.assertEqual(res.status_code, 200)

        # N+1 olursa şirket sayısı kadar sorgu patlar.
        # Fix sonrası genelde birkaç sorgu olur. Güvenli limit:
        self.assertLessEqual(len(ctx), 15)
def test_sirket_list_page_no_nplus1(self):
    for i in range(20):
        Sirket.objects.create(
            name=f"S{i}",
            sector="yazilim",
            employee_count=1,
            location_city="İstanbul",
            is_exporter=False,
        )

    url = reverse("sirket-list-page")

    with CaptureQueriesContext(connection) as ctx:
        res = self.client.get(url)

    self.assertEqual(res.status_code, 200)
    self.assertLessEqual(len(ctx), 15)  # N+1 varsa bu sayı uçuyor
