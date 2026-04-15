# Active Context

Mevcut aktif is Faz 5 hata senaryolarini tamamlamak ve Faz 6 coklu batch altyapisina hazir hale gecmektir.

Hedefler:

- Faz 2 secim ve batch hazirlik akisi tamamlandi.
- Faz 3 browser session yonetimi tamamlandi.
- Playwright browser manager ve portal session manager eklendi.
- Login formu .env credential'lariyla doldurulur.
- 2FA ekrani beklenir, kullanici kodu manuel girer.
- 2FA sonrasi session hazirligi e-Arsiv menu linki veya URL fallback ile dogrulanir.
- Faz 4 tek kayit taslak POC tamamlandi.
- Hazir session ile e-Arsiv olustur ekranina gidilir.
- Tek kayit verisi forma yazilir, Taslak Kaydet butonu kullanilir.
- Sonuc repository status/hata alanlarina yazilir.
- Faz 5 hata senaryolari tamamlandi.
- Turmob servis hatasi, gecersiz VKN/TCKN ve e-Fatura mukellefi dialoglari gercek portal mesajlariyla yakalanir.
- Hata dialoglari OK ile kapatilir, screenshot alinir, status/hata alanlari repository'ye yazilir.
- Basari `/EArchive/Drafts` redirect'i ile dogrulanir.
- Sonraki ana is Faz 6 coklu batch islemedir.

Coklu batch henuz uygulanmadi. Faz 6 secili kayitlari sirayla isleyip hata alan kaydi atlayarak devam etmeye odaklanacak.
