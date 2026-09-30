# FinansMaster — PRD

## Amaç
Türkçe, modern finans yönetim uygulaması. Kullanıcı gelir/gider, banka hesapları, cari hesaplar, yaklaşan ödemeler ve tahsilatlar ile finansal raporları tek yerden yönetir; nakit akışını anlık takip eder.

## Kullanıcı Personası
- KOBİ sahibi / işletme yöneticisi. Muhasebe uzmanı değil; hızlı görsel özet ve minimal veri girişi ister.
- Dashboard'dan işletmenin nabzını takip eder, ay içi kayıt girer, ay sonu rapor indirir.

## Temel Gereksinimler (Statik)
- İlk ekran: Dashboard; anlık nakit akışı ve hesap bakiyeleri öne çıkar.
- Para birimleri: TRY, USD, EUR.
- Modüller: Genel Bakış, Gelir & Gider, Banka Hesapları, Cariler, Ödemeler (takvim), Raporlar.
- Gelir/gider kayıtlarında ekleme, listeleme, silme ve CSV içe aktarma.
- Hesap ve cari için tam CRUD; cari bakiyesi manuel.
- Raporlar: aylık nakit akışı, kategori analizi, cari vade yaşlandırma, CSV dışa aktarım.
- Açık, ferah ve modern arayüz.

## Uygulanan Özellikler
### İterasyon 1-3
- FinansMaster açık tema tasarımı (DM Sans + Plus Jakarta Sans).
- Dashboard, işlem CRUD, CSV import, takvim, temel raporlar.
- Canlı dashboard özetleri (aylık gelir/gider/bekleyen/toplam bakiye).
- Hesap bakiyesi işlem sırasında mutabık güncelleniyor.

### İterasyon 4 (30 Eylül 2026)
- **Banka hesabı CRUD**: ekleme, düzenleme (isim değişince transactions.account'ta cascade), silme.
- **Cari hesaplar (Cariler)**: ayrı sol menü sekmesi + tablo; manuel bakiye, vade, tür (Müşteri/Tedarikçi), telefon/e-posta, tam CRUD.
- **Cari vade yaşlandırma raporu**: overdue / 0-7 / 8-30 / 30+ gün segmentleri; alacak/borç toplamları + detay tablosu.
- **Rapor CSV dışa aktarımı**: /api/reports/export/cashflow ve /api/reports/export/aging — UTF-8 BOM + Türkçe başlıklar; frontend blob indirmesi.
- **Generic Modal**: tek modal artık transaction/account/contact modlarını destekliyor.
- Dashboard özetine `receivable` ve `payable` toplamları eklendi.

## Test Durumu
- Backend: `/app/backend/tests/backend_test.py`; iterasyon 4'te 15/15 pytest geçti.
- Frontend: manuel screenshot doğrulaması (dashboard, cariler, hesaplar, raporlar).

## Backlog
### P1
- Ayarlarda "Demo verilerini temizle" akışı.
- CSV içe aktarma sonrası detay rapor (kaç kayıt işlendi, hangileri hatalı).
- Rapor PDF dışa aktarımı.
- Çoklu para birimi kur dönüşümü (dashboard toplam bakiye eşdeğeri).

### P2
- Auth / çoklu kullanıcı.
- Banka ekstresi eşleştirme.
- Tekrarlayan işlemler (kira, abonelik).
- Kategori özelleştirme (kullanıcı tanımlı).

## Not (İç kalite)
- `delete_account` şu an referans kontrolü yapmıyor; büyümeden önce cascade/warn eklenmesi önerildi.
- `server.py` ~400 satır — 700'ü geçerse router bazlı ayrım (accounts/contacts/transactions/reports).
