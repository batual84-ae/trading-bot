from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st
from binance.client import Client

from bot_engine import BotConfig, TradingBot
from storage import get_logs, get_positions, get_trades, init_db

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = BASE_DIR / 'settings.json'

init_db()

st.set_page_config(page_title='Binance Al-Sat Botu', page_icon='📈', layout='wide')

DEFAULTS = {
    'mode': 'paper',
    'api_key': '',
    'api_secret': '',
    'symbols_text': 'BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT',
    'interval': '1m',
    'order_quote_amount': 10.0,
    'take_profit_pct': 1.0,
    'stop_loss_pct': 0.7,
    'max_open_positions': 2,
    'loop_seconds': 30,
    'ema_fast': 9,
    'ema_slow': 21,
    'rsi_period': 14,
    'rsi_buy_min': 56.0,
    'rsi_sell_max': 44.0,
}


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return {**DEFAULTS, **json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))}
        except Exception:
            return DEFAULTS.copy()
    return DEFAULTS.copy()


def save_settings(data: dict):
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


if 'settings' not in st.session_state:
    st.session_state.settings = load_settings()

if 'bot' not in st.session_state:
    st.session_state.bot = None

settings = st.session_state.settings

st.title('📈 Binance Momentum Al-Sat Uygulaması')
st.caption('Start verdiğinde seçtiğin coinleri tarar, en güçlü adayı alır, hedef yüzde gelince satar ve sen stoplayana kadar devam eder.')

with st.sidebar:
    st.header('Bot Kontrolü')
    current_bot = st.session_state.bot
    if current_bot and current_bot.running:
        st.success('Bot çalışıyor')
        if st.button('Botu Durdur', use_container_width=True):
            current_bot.stop()
    else:
        st.warning('Bot kapalı')
        if st.button('Botu Başlat', use_container_width=True):
            cfg = BotConfig(
                mode=settings['mode'],
                api_key=settings['api_key'],
                api_secret=settings['api_secret'],
                symbols=[s.strip().upper() for s in settings['symbols_text'].split(',') if s.strip()],
                interval=settings['interval'],
                order_quote_amount=float(settings['order_quote_amount']),
                take_profit_pct=float(settings['take_profit_pct']) / 100.0,
                stop_loss_pct=float(settings['stop_loss_pct']) / 100.0,
                max_open_positions=int(settings['max_open_positions']),
                loop_seconds=int(settings['loop_seconds']),
                ema_fast=int(settings['ema_fast']),
                ema_slow=int(settings['ema_slow']),
                rsi_period=int(settings['rsi_period']),
                rsi_buy_min=float(settings['rsi_buy_min']),
                rsi_sell_max=float(settings['rsi_sell_max']),
            )
            bot = TradingBot(cfg)
            try:
                bot.start()
                st.session_state.bot = bot
                st.success('Bot başlatıldı.')
            except Exception as e:
                st.error(f'Bot başlatılamadı: {e}')

    st.divider()
    st.info('Öneri: önce paper mod, sonra testnet, en son live.')
    st.info('Güvenlik için kullanıcı adı/şifre değil, API key + secret kullan.')


tab1, tab2, tab3, tab4 = st.tabs(['Ayarlar', 'Canlı Takip', 'Pozisyonlar & İşlemler', 'Loglar'])

with tab1:
    st.subheader('Bot Ayarları')
    col1, col2 = st.columns(2)
    with col1:
        settings['mode'] = st.selectbox('Mod', ['paper', 'testnet', 'live'], index=['paper', 'testnet', 'live'].index(settings['mode']))
        settings['api_key'] = st.text_input('API Key', value=settings['api_key'])
        settings['api_secret'] = st.text_input('API Secret', value=settings['api_secret'], type='password')
        settings['symbols_text'] = st.text_input('Taranacak coinler (virgülle)', value=settings['symbols_text'])
        settings['interval'] = st.selectbox('Tarama aralığı', ['1m', '3m', '5m', '15m'], index=['1m', '3m', '5m', '15m'].index(settings['interval']))
        settings['order_quote_amount'] = st.number_input('Her alımda USDT tutarı', min_value=5.0, value=float(settings['order_quote_amount']), step=1.0)
        settings['max_open_positions'] = st.number_input('Aynı anda açık coin sayısı', min_value=1, max_value=10, value=int(settings['max_open_positions']), step=1)

    with col2:
        settings['take_profit_pct'] = st.number_input('Kâr al %', min_value=0.2, value=float(settings['take_profit_pct']), step=0.1)
        settings['stop_loss_pct'] = st.number_input('Zarar durdur %', min_value=0.2, value=float(settings['stop_loss_pct']), step=0.1)
        settings['loop_seconds'] = st.number_input('Yeniden tarama saniyesi', min_value=10, value=int(settings['loop_seconds']), step=5)
        settings['ema_fast'] = st.number_input('EMA hızlı', min_value=2, value=int(settings['ema_fast']), step=1)
        settings['ema_slow'] = st.number_input('EMA yavaş', min_value=3, value=int(settings['ema_slow']), step=1)
        settings['rsi_period'] = st.number_input('RSI periyot', min_value=2, value=int(settings['rsi_period']), step=1)
        settings['rsi_buy_min'] = st.number_input('RSI al eşiği', min_value=1.0, max_value=99.0, value=float(settings['rsi_buy_min']), step=1.0)

    if st.button('Ayarları Kaydet'):
        save_settings(settings)
        st.success('Ayarlar kaydedildi.')

    st.markdown('''
**Senin istediğin davranış için önerilen ayar:**
- Tarama aralığı: `1m`
- Yeniden tarama: `30 sn`
- Kâr al: `%1.0`
- Aynı anda açık coin: `2`
- Coin listesi: `BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT`
''')

with tab2:
    st.subheader('Canlı Takip Ekranı')
    symbols = [s.strip().upper() for s in settings['symbols_text'].split(',') if s.strip()]
    client = Client('', '')

    if st.button('Fiyatları Yenile'):
        st.rerun()

    rows = []
    for symbol in symbols:
        try:
            ticker = client.get_symbol_ticker(symbol=symbol)
            klines = client.get_klines(symbol=symbol, interval=settings['interval'], limit=30)
            closes = [float(k[4]) for k in klines]
            last_price = float(ticker['price'])
            change = ((closes[-1] / closes[-6]) - 1) * 100 if len(closes) >= 6 else 0.0
            rows.append({'coin': symbol, 'anlık_fiyat': last_price, f'son_{settings["interval"]}_momentum_%': round(change, 3)})
        except Exception as e:
            rows.append({'coin': symbol, 'anlık_fiyat': None, f'son_{settings["interval"]}_momentum_%': None, 'hata': str(e)})

    live_df = pd.DataFrame(rows)
    st.dataframe(live_df, use_container_width=True)

    positions = pd.DataFrame(get_positions())
    st.subheader('Şu an açık olan coinler')
    if positions.empty:
        st.info('Şu an açık pozisyon yok.')
    else:
        pos_view = positions.copy()
        current_prices = []
        unrealized = []
        for _, row in pos_view.iterrows():
            try:
                p = float(client.get_symbol_ticker(symbol=row['symbol'])['price'])
            except Exception:
                p = None
            current_prices.append(p)
            unrealized.append((p - row['entry_price']) * row['quantity'] if p else None)
        pos_view['anlık_fiyat'] = current_prices
        pos_view['anlık_pnl'] = unrealized
        st.dataframe(pos_view, use_container_width=True)

with tab3:
    st.subheader('Son İşlemler')
    trades = pd.DataFrame(get_trades(300))
    if trades.empty:
        st.info('Henüz işlem yok.')
    else:
        st.dataframe(trades, use_container_width=True)
        sells = trades[trades['side'] == 'SELL'].copy()
        if not sells.empty:
            st.metric('Toplam gerçekleşen PnL', f"{sells['pnl'].fillna(0).sum():.4f} USDT")

with tab4:
    st.subheader('Bot Logları')
    logs = pd.DataFrame(get_logs(300))
    if logs.empty:
        st.info('Henüz log yok.')
    else:
        st.dataframe(logs, use_container_width=True)
        st.download_button('Logları indir (CSV)', logs.to_csv(index=False).encode('utf-8'), file_name='bot_logs.csv', mime='text/csv')
