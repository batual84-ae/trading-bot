# Binance Al-Sat Botu (Streamlit UI)

Bu uygulama, Binance spot piyasası için arayüzden yönetilebilen basit bir otomatik al-sat botudur.

## Özellikler
- Arayüzden API key, coin, TP/SL ve strateji ayarı girme
- `paper`, `testnet`, `live` modları
- EMA + RSI tabanlı giriş sinyali
- Açık pozisyon takibi
- TP / SL ile otomatik çıkış
- SQLite ile log, işlem ve pozisyon kaydı

## Uyarı
- **İlk kullanımda `paper` veya `testnet` kullanın.**
- `live` mod gerçek emir gönderir.
- API key'e sadece gerekli izinleri verin; çekim izni vermeyin.

## Kurulum
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Kullanım
1. Modu `paper` seçin.
2. Coinleri girin: `BTCUSDT,ETHUSDT,SOLUSDT`
3. İşlem başı USDT miktarını belirleyin.
4. Take profit ve stop loss yüzdelerini ayarlayın.
5. `Ayarları Kaydet` butonuna basın.
6. Sol menüden `Botu Başlat` butonuna basın.

## Testnet
`testnet` mod için Binance Spot Testnet API key oluşturun ve arayüze girin.

## Dosyalar
- `app.py`: Streamlit arayüzü
- `bot_engine.py`: bot motoru ve Binance erişimi
- `strategy.py`: EMA + RSI stratejisi
- `storage.py`: SQLite kayıt işlemleri
- `indicators.py`: indikatör hesapları
