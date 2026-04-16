# Operasyon Checklist

## A. Import Oncesi

- Dogru Excel/CSV dosyasi secildi mi?
- Dosyanin guncel oldugu dogrulandi mi?
- Excel icinde dogru sheet belirlendi mi?
- Kolon mapping icin ad, soyad, TCKN ve tutar kolonlari net mi?
- Batch/fatura donemi adi operasyon ekibi tarafindan anlasilir mi?
- Dosyada test veya bos satir olmadigi kontrol edildi mi?

## B. Import Sonrasi

- Import sonucu hata listesi kontrol edildi mi?
- Aktif batch/fatura donemi records ekraninda dogru gorunuyor mu?
- Kayit sayisi beklenen sayi mi?
- Ad, soyad, TCKN ve tutar kolonlari dogru aktarilmis mi?
- Hatalı satirlar gerekiyorsa kaynak dosyada duzeltildi mi?

## C. Batch Baslatmadan Once

- Aktif fatura donemi dogru mu?
- Sadece islenecek kayitlar secildi mi?
- `Tumunu Sec` kullanildiysa gorunen filtre dogru mu?
- Secili uygun kayit sayisi beklenen sayi mi?
- Session durumu `READY` mi?
- Browser acik ve portal session kullanilabilir mi?
- `.env` icinde sleep prevention ayarlari aktif mi?
- Ilk kullanimda kucuk kayit grubu ile deneme yapildi mi?

## D. Batch Sirasinda

- Bilgisayar uyumamali; sleep prevention logu `data/logs/app.log` icinde gorulebilir.
- Portal ekraninda beklenmeyen popup var mi?
- Uygulama batch sonuc ekranina donuyor mu?
- Kritik abort mesaji gorulurse islem durdurulup log incelendi mi?

## E. Batch Sonrasi

- Basarili taslak sayisi kontrol edildi mi?
- Failed ve skipped sayilari kontrol edildi mi?
- `FAILED_NAME_MISMATCH` kayitlari manuel incelendi mi?
- `FAILED_INVALID_TCKN` kayitlari kaynak veriyle karsilastirildi mi?
- `SKIPPED_EFATURA_MUKELLEFI` kayitlari ayri not edildi mi?
- Screenshot path olan hatalar incelendi mi?
- `data/logs/app.log` icindeki batch ozeti kontrol edildi mi?
- Gereken manuel duzeltmeler belirlendi mi?

## F. Canli Kullanim Uyarilari

- READY olmadan batch baslatmayin.
- Yanlis fatura donemiyle islem yapmayin.
- Import sonrasi kayitlari kontrol etmeden toplu taslak olusturmayin.
- Portal selector veya ekran davranisi degistiyse once tek kayit POC calistirin.
- Hata alan kayitlari ayni batch icinde otomatik tekrar denemeyin; once nedeni inceleyin.
- `.env` dosyasini paylasmayin veya repoya commit etmeyin.
