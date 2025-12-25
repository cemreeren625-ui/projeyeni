# Django model altyapısı (DB tablolarını tanımlamak için)
from django.db import models

# Mevzuat metninden otomatik tag/sector/impact çıkaran fonksiyon
# (Senin yazdığın NLP kural motoru)
from .nlp_rules import analyze_regulation_text


class Sirket(models.Model):
    # UI'da sektör seçimi için seçenek listesi
    SECTOR_CHOICES = [
        ("yazilim", "Yazılım"),
        ("imalat", "İmalat"),
        ("perakende", "Perakende"),
        ("lojistik", "Lojistik"),
    ]

    # Şirket adı
    name = models.CharField(max_length=255)

    # Şirketin sektörü (choices ile kısıtlı)
    sector = models.CharField(max_length=50, choices=SECTOR_CHOICES)

    # Çalışan sayısı (negatif olmasın diye PositiveIntegerField)
    employee_count = models.PositiveIntegerField()

    # Şirketin bulunduğu şehir
    location_city = models.CharField(max_length=100)

    # İhracatçı mı? (True/False)
    is_exporter = models.BooleanField(default=False)

    # Kayıt DB’ye eklendiği an otomatik tarih atar
    created_at = models.DateTimeField(auto_now_add=True)

    # Ünvan alanı: boş geçilebilir (blank=True)
    # DB tarafında boş gelmesin diye default "" veriyoruz
    unvan = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        # Admin panelde veya template’te {{ sirket }} yazınca gözükecek metin
        return self.name


class Duzenleme(models.Model):
    # Mevzuat kaynağı seçenekleri
    SOURCE_CHOICES = [
        ("resmi_gazete", "Resmî Gazete"),
        ("gib", "Gelir İdaresi Başkanlığı"),
    ]

    # Mevzuatın etki türü seçenekleri
    IMPACT_CHOICES = [
        ("zorunlu", "Zorunlu"),
        ("opsiyonel_tesvik", "Opsiyonel Teşvik"),
        ("risk", "Dikkat / Risk"),
    ]

    # Kaynak (choices ile kısıtlı)
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)

    # Başlık
    title = models.CharField(max_length=500)

    # Yayın tarihi
    publish_date = models.DateField()

    # Kaynak URL (opsiyonel)
    url = models.URLField(blank=True, null=True)

    # Mevzuatın ham tam metni (zorunlu)
    raw_text = models.TextField()

    # Özet metin (opsiyonel)
    summary = models.TextField(blank=True, null=True)

    # Etiketler (JSON listesi olarak saklanır)
    # default=list => boşsa [] ile başlar
    tags = models.JSONField(default=list, blank=True)     # örn: ["vergi", "KDV"]

    # Hangi sektörleri ilgilendiriyor (JSON listesi)
    sectors = models.JSONField(default=list, blank=True)  # örn: ["yazilim", "imalat"]

    # Etki tipi (zorunlu/teşvik/risk)
    # boş bırakılabilir; NLP otomatik doldurabilir
    impact_type = models.CharField(
        max_length=50,
        choices=IMPACT_CHOICES,
        blank=True,
        null=True,
    )

    # Oluşturulma zamanı
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Admin panelde daha anlamlı görünmesi için
        return f"{self.title} ({self.source})"

    def save(self, *args, **kwargs):
        """
        Bu model kaydedilirken:
        - tags, sectors veya impact_type boşsa
        - title + raw_text üzerinden analyze_regulation_text çalıştır
        - çıkan sonuçları otomatik doldur
        """

        # NLP'ye verilecek metni birleştiriyoruz:
        # raw_text None olabilir diye "or ''" ile güvene alıyoruz
        combined_text = f"{self.title}\n{self.raw_text or ''}"

        # NLP kural motoru: (tags_list, sectors_list, impact_type) döndürsün
        auto_tags, auto_sectors, auto_impact = analyze_regulation_text(combined_text)

        # Eğer tags boşsa ve NLP tags bulduysa doldur
        if (not self.tags) and auto_tags:
            self.tags = auto_tags

        # Eğer sectors boşsa ve NLP sectors bulduysa doldur
        if (not self.sectors) and auto_sectors:
            self.sectors = auto_sectors

        # Eğer impact_type boşsa ve NLP impact tipi bulduysa doldur
        if (not self.impact_type) and auto_impact:
            self.impact_type = auto_impact

        # Normal Django save'i çağır (DB’ye yaz)
        super().save(*args, **kwargs)


class SirketObligation(models.Model):
    # Risk seviyesi seçenekleri
    RISK_CHOICES = [
        ("low", "Düşük"),
        ("medium", "Orta"),
        ("high", "Yüksek"),
    ]

    # Bu obligation hangi şirkete ait?
    # Şirket silinirse obligationlar da silinsin (CASCADE)
    sirket = models.ForeignKey(Sirket, on_delete=models.CASCADE)

    # Bu obligation hangi mevzuattan geliyor?
    # Mevzuat silinirse obligationlar da silinsin (CASCADE)
    duzenleme = models.ForeignKey(Duzenleme, on_delete=models.CASCADE)

    # Bu mevzuat bu şirket için geçerli mi?
    is_applicable = models.BooleanField(default=True)

    # Şirket bu yükümlülüğü yerine getirdi mi?
    is_compliant = models.BooleanField(default=False)

    # Son tarih (opsiyonel)
    due_date = models.DateField(blank=True, null=True)

    # Risk seviyesi (choices ile)
    risk_level = models.CharField(
        max_length=10,
        choices=RISK_CHOICES,
        default="medium",
    )

    # Kayıt oluşturulma zamanı
    created_at = models.DateTimeField(auto_now_add=True)

    # Kayıt her güncellendiğinde otomatik güncellenir
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        # Admin panelde obligation daha okunur görünür
        return f"{self.sirket.name} / {self.duzenleme.title}"
