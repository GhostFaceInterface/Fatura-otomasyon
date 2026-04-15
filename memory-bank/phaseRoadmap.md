# Phase Roadmap

Bu dosya projenin fazlarini unutmamak icin kalici roadmap olarak tutulur.

## Faz 1 - Proje iskeleti ve veri katmani

Hedef:

- Klasor yapisi
- Config
- SQLite setup
- Model ve repository
- Import service
- Basic UI skeleton

Teslim:

- Calisan proje iskeleti
- Excel/CSV import
- Kayit listeleme

## Faz 2 - Secim ekrani ve batch hazirligi

Hedef:

- Kayitlarin secilmesi
- Durum yonetimi
- Batch servis iskeleti
- Progress mantiginin temel yapisi

Teslim:

- Kullanici kayit secebilir
- Secilenler batch'e hazirlanir

## Faz 3 - Browser session yonetimi

Hedef:

- Playwright kurulumu
- Browser manager
- Session manager
- Login sayfasina gitme
- Kullanici adi/sifre doldurma
- 2FA bekleme akisi

Teslim:

- Tarayici acilir
- Login formu doldurulur
- Kullanici 2FA sonrasi devam edebilir

## Faz 4 - Tek kayit icin taslak olusturma POC

Hedef:

- Tek kisi icin portalda taslak olusturma
- Sayfa navigasyonu
- TCKN girme
- Musteri sorgulama
- Fatura kalemi ekleme
- Taslak kaydetme

Teslim:

- 1 kayit icin calisan gercek POC

## Faz 5 - Hata senaryolari

Hedef:

- Invalid TCKN
- e-Fatura mukellefi
- Timeout
- Bilinmeyen hata
- Screenshot/log alma

Teslim:

- Hatali kisiyi atlayip devam eden hata yonetimi

## Faz 6 - Coklu batch isleme

Hedef:

- Secili kisileri sirayla isleme
- Canli durum guncelleme
- Sonuc raporu

Teslim:

- 10+ kisi icin kontrollu batch calismasi

## Faz 7 - Temizlik ve sertlestirme

Hedef:

- Refactor
- Selector iyilestirmeleri
- Retry/backoff
- UI polishing
- README
- Testlerin tamamlanmasi

Teslim:

- Kullanilabilir v1 surumu
