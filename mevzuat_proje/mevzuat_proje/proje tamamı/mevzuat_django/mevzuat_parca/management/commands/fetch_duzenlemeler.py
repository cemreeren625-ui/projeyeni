# Django'da custom management command yazmak için temel sınıf
from django.core.management.base import BaseCommand

# Bugünün tarihini almak için
from datetime import date

# Düzenleme modelini DB’ye yazmak/okumak için
from mevzuat_parca.models import Duzenleme


def run():
    """
    Bu fonksiyon:
    - Test amaçlı DB’ye 1 tane Duzenleme kaydı ekler (veya varsa tekrar eklemez).
    - get_or_create sayesinde aynı başlık + tarih + source ile duplicate üretmez.
    """

    # 1) Test amaçlı DB’ye 1 tane kayıt atıyoruz (varsa tekrar eklemez)
    obj, created = Duzenleme.objects.get_or_create(
        source="resmi_gazete",               # kaynağı
        title="TEST - Örnek Düzenleme",      # başlığı (unique davranış için kritik)
        publish_date=date.today(),           # yayın tarihi = bugün

        # Eğer kayıt yoksa, oluştururken doldurulacak ekstra alanlar
        defaults={
            "raw_text": "Bu bir test metnidir.",  # ham metin
            "summary": "Test özet.",              # özet
            "url": "https://example.com",         # link
        },
    )

    # created=True ise yeni oluşturdu demek
    if created:
        print("✅ DB’ye eklendi:", obj.id)
    else:
        # created=False ise zaten vardı, tekrar eklemedi
        print("ℹ️ Zaten vardı, tekrar eklemedim:", obj.id)


class Command(BaseCommand):
    """
    Bu sınıf Django'nun management command sistemine bağlanır.
    Dosya adı fetch_duzenlemeler.py ise:
      python manage.py fetch_duzenlemeler
    komutuyla çalışır.
    """

    # Komut açıklaması (python manage.py help komutunda görünür)
    help = "Resmî kaynaklardan düzenlemeleri çek ve veritabanına kaydet."

    def handle(self, *args, **options):
        """
        Komut çalıştırılınca burası tetiklenir.
        Burada run() fonksiyonunu çağırıyoruz.
        """
        run()

        # Terminalde yeşil SUCCESS mesajı basar
        self.stdout.write(self.style.SUCCESS("Bitti: fetch_duzenlemeler"))

