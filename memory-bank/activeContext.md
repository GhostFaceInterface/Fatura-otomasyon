# Active Context

Mevcut aktif is son faz sertlestirme ve operasyon hazirligini tamamlamak olarak guncellendi.

Hedefler:

- Faz 2 secim ve batch hazirlik akisi tamamlandi.
- Faz 3 browser session yonetimi tamamlandi.
- Playwright browser manager ve portal session manager eklendi.
- Login formu .env credential'lariyla doldurulur.
- 2FA ekrani beklenir, kullanici kodu manuel girer.
- 2FA sonrasi session hazirligi `/Home/Index` veya e-Arsiv menu linki ile dogrulanir.
- Faz 4 tek kayit taslak POC tamamlandi.
- Hazir session ile e-Arsiv olustur ekranina gidilir.
- Tek kayit verisi forma yazilir, Taslak Kaydet butonu kullanilir.
- Sonuc repository status/hata alanlarina yazilir.
- Faz 5 hata senaryolari tamamlandi.
- Turmob servis hatasi, gecersiz VKN/TCKN ve e-Fatura mukellefi dialoglari gercek portal mesajlariyla yakalanir.
- Hata dialoglari OK ile kapatilir, screenshot alinir, status/hata alanlari repository'ye yazilir.
- Basari `/EArchive/Drafts` redirect'i ile dogrulanir.
- Faz 6 coklu batch isleme tamamlandi.
- Secili ve PENDING/SELECTED durumundaki kayitlar deterministic id sirasiyla islenir.
- Batch runner mevcut `SingleDraftService` tek kayit akisini cagirir; tek kayit otomasyonu yeniden yazilmamistir.
- Kayit bazli FAILED/SKIPPED durumlar batch'i durdurmaz.
- ABORTED_SESSION_LOST veya yeni e-Arsiv olustur sayfasina guvenli donus hatasi batch'i kritik nedenle durdurur.
- Batch sonunda UI/API uzerinden toplam success/skip/fail/abort ve kayit bazli detay raporu doner.
- Faz 7 oncesi kritik eksikler tamamlandi.
- Her import `import_batches` fatura donemine baglanir; `invoice_records.batch_id` ile donem izolasyonu saglanir.
- Excel import akisi sheet secimi, kolon mapping ve batch adi ile calisir; otomatik alias mapping fallback olarak kalir.
- Records ve batch ekranlari aktif fatura donemi baglaminda calisir.
- Records ekraninda uygun kayitlar icin `Tumunu Sec` checkbox'i vardir.
- Login sonrasi `/Home/Index`, e-Arsiv menu veya 2FA sayfasi ayirt edilir; 2FA yoksa session dogrudan READY olur.
- Turmob sonrasi `#txtPerson_FirstName` ve `#txtPerson_FamilyName` okunur; SQLite ad/soyad ile normalize edilerek karsilastirilir.
- Ad/soyad uyusmazligi `FAILED_NAME_MISMATCH` statusu ile kayit bazli fail olur ve batch devam eder.

- Son faz hardening tamamlandi.
- Login/session UI'da state ve kullanici yonlendirmesi daha net hale getirildi.
- Session READY degilse batch run UI'da engellenir; backend yine session check ile guvenli abort uretir.
- Navigation/form hazir kontrolu birden fazla kritik alanla yapilir.
- Retry/backoff icin merkezi helper ve config alanlari eklendi.
- Turmob ad/soyad alanlarini okuma ve Getir/Turmob tiklamalari kontrollu retry/backoff ile sertlestirildi.
- Draft success redirect timeout'u ayri config ile yonetilir.
- Records ekranina aktif batch icinde arama eklendi.
- Batch raporuna detay filtreleri eklendi: tum, failed, skip, screenshot olanlar.
- README, `docs/USAGE_GUIDE.md` ve `docs/OPERATIONS_CHECKLIST.md` operasyon odakli guncellendi.

Sonraki ana is canli kullanim oncesi kucuk kayit grubu ile pilot test ve portal selector davranislarini gercek ortamda dogrulamaktir.

Son bug fix:

- Import tutar parsing'i `parse_currency` ile merkezi hale getirildi.
- `$1.450`, `1.450`, `$850`, `$1,450` gibi binlik ayracli degerler deterministik olarak float tutara normalize edilir.
- `$1450.75` gibi decimal nokta iceren degerler decimal olarak korunur.
- Parse edilemeyen veya bos tutarlar satir bazli import hatasi olarak raporlanir ve loglanir.
