from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Optional

import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException

from storage import add_log, add_trade, delete_position, get_positions, upsert_position
from strategy import EMARSITrendStrategy


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


@dataclass
class BotConfig:
    mode: str  # paper | testnet | live
    api_key: str
    api_secret: str
    symbols: list[str]
    interval: str
    order_quote_amount: float
    take_profit_pct: float
    stop_loss_pct: float
    max_open_positions: int
    loop_seconds: int
    ema_fast: int
    ema_slow: int
    rsi_period: int
    rsi_buy_min: float
    rsi_sell_max: float


class BinanceGateway:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.client = Client(api_key, api_secret, testnet=testnet)

    def ping(self):
        self.client.ping()

    def get_klines_df(self, symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
        rows = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(rows, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        return df

    def get_price(self, symbol: str) -> float:
        return float(self.client.get_symbol_ticker(symbol=symbol)['price'])

    def get_symbol_info(self, symbol: str) -> dict:
        return self.client.get_symbol_info(symbol)

    def market_buy_quote(self, symbol: str, quote_amount: float) -> dict:
        return self.client.create_order(symbol=symbol, side='BUY', type='MARKET', quoteOrderQty=f'{quote_amount:.8f}')

    def market_sell_qty(self, symbol: str, quantity: float) -> dict:
        quantity = self.normalize_quantity(symbol, quantity)
        return self.client.create_order(symbol=symbol, side='SELL', type='MARKET', quantity=f'{quantity:.8f}')

    def normalize_quantity(self, symbol: str, quantity: float) -> float:
        info = self.get_symbol_info(symbol)
        lot = next((f for f in info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
        if not lot:
            return quantity
        step = float(lot['stepSize'])
        min_qty = float(lot['minQty'])
        precision = max(0, int(round(-math.log10(step), 0))) if step < 1 else 0
        normalized = math.floor(quantity / step) * step
        normalized = round(normalized, precision)
        if normalized < min_qty:
            raise ValueError(f'{symbol} için miktar minQty altında: {normalized}')
        return normalized


class PaperGateway:
    def __init__(self):
        self.client = Client('', '')

    def ping(self):
        return True

    def get_klines_df(self, symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
        rows = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(rows, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        return df

    def get_price(self, symbol: str) -> float:
        return float(self.client.get_symbol_ticker(symbol=symbol)['price'])

    def market_buy_quote(self, symbol: str, quote_amount: float) -> dict:
        price = self.get_price(symbol)
        qty = quote_amount / price
        return {'status': 'FILLED', 'executedQty': qty, 'fills': [{'price': price, 'qty': qty}]}

    def market_sell_qty(self, symbol: str, quantity: float) -> dict:
        price = self.get_price(symbol)
        return {'status': 'FILLED', 'executedQty': quantity, 'fills': [{'price': price, 'qty': quantity}]}


class TradingBot:
    def __init__(self, config: BotConfig):
        self.config = config
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self.strategy = EMARSITrendStrategy(
            ema_fast=config.ema_fast,
            ema_slow=config.ema_slow,
            rsi_period=config.rsi_period,
            rsi_buy_min=config.rsi_buy_min,
            rsi_sell_max=config.rsi_sell_max,
        )
        self.gateway = self._build_gateway(config)

    @staticmethod
    def _build_gateway(config: BotConfig):
        if config.mode == 'paper':
            return PaperGateway()
        return BinanceGateway(config.api_key, config.api_secret, testnet=config.mode == 'testnet')

    @property
    def running(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            return
        self._stop_event.clear()
        self.gateway.ping()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._running = True
        self.log('INFO', f'Bot başlatıldı: {asdict(self.config)}')

    def stop(self):
        self._stop_event.set()
        self._running = False
        self.log('INFO', 'Bot durduruldu.')

    def log(self, level: str, message: str):
        add_log(now_iso(), level, message)

    def _current_positions(self) -> Dict[str, dict]:
        return {p['symbol']: p for p in get_positions()}

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self._check_open_positions()
                self._scan_for_entries()
            except BinanceAPIException as e:
                self.log('ERROR', f'Binance API hatası: {e.message}')
            except Exception as e:
                self.log('ERROR', f'Beklenmeyen hata: {e}')
            time.sleep(max(5, self.config.loop_seconds))
        self._running = False

    def _check_open_positions(self):
        positions = self._current_positions()
        for symbol, pos in positions.items():
            current_price = self.gateway.get_price(symbol)
            self.log('INFO', f'{symbol} açık pozisyon kontrol: fiyat={current_price:.6f} tp={pos["take_profit"]:.6f} sl={pos["stop_loss"]:.6f}')
            if current_price >= pos['take_profit']:
                self._close_position(symbol, pos, current_price, 'TP % hedef')
            elif current_price <= pos['stop_loss']:
                self._close_position(symbol, pos, current_price, 'SL % koruma')

    def _close_position(self, symbol: str, pos: dict, current_price: float, note: str):
        self.gateway.market_sell_qty(symbol, float(pos['quantity']))
        pnl = (current_price - float(pos['entry_price'])) * float(pos['quantity'])
        add_trade(
            symbol=symbol,
            side='SELL',
            price=current_price,
            quantity=float(pos['quantity']),
            notional=current_price * float(pos['quantity']),
            pnl=pnl,
            mode=self.config.mode,
            created_at=now_iso(),
            note=note,
        )
        delete_position(symbol)
        self.log('INFO', f'{symbol} pozisyon kapandı ({note}). PnL={pnl:.4f}')

    def _scan_for_entries(self):
        positions = self._current_positions()
        if len(positions) >= self.config.max_open_positions:
            self.log('INFO', 'Maksimum açık pozisyon limiti dolu.')
            return

        ranked = []
        for symbol in self.config.symbols:
            if symbol in positions:
                continue
            df = self.gateway.get_klines_df(symbol, self.config.interval, 250)
            result = self.strategy.apply(df)
            last_price = float(result.dataframe['close'].iloc[-1])
            last_rsi = float(result.dataframe['rsi'].iloc[-1]) if 'rsi' in result.dataframe.columns else 0.0
            self.log('INFO', f'{symbol} sinyal={result.signal} skor={result.score:.2f} fiyat={last_price:.6f} rsi={last_rsi:.2f} neden={result.reason}')
            ranked.append((symbol, result.score, result.signal, result.reason))

        ranked.sort(key=lambda x: x[1], reverse=True)
        buy_candidates = [x for x in ranked if x[2] == 'BUY']

        for symbol, score, _signal, reason in buy_candidates:
            positions = self._current_positions()
            if len(positions) >= self.config.max_open_positions:
                break
            self.log('INFO', f'En güçlü aday seçildi: {symbol} skor={score:.2f} neden={reason}')
            self._open_position(symbol)

    def _open_position(self, symbol: str):
        order = self.gateway.market_buy_quote(symbol, self.config.order_quote_amount)
        fills = order.get('fills', [])
        qty = float(order.get('executedQty', 0.0))
        if qty <= 0:
            self.log('WARN', f'{symbol} için executedQty 0 geldi, pozisyon açılmadı.')
            return
        if fills:
            total_qty = sum(float(f['qty']) for f in fills)
            total_cost = sum(float(f['price']) * float(f['qty']) for f in fills)
            entry_price = total_cost / total_qty if total_qty else self.gateway.get_price(symbol)
        else:
            entry_price = self.gateway.get_price(symbol)
        take_profit = entry_price * (1 + self.config.take_profit_pct)
        stop_loss = entry_price * (1 - self.config.stop_loss_pct)
        upsert_position(
            symbol=symbol,
            entry_price=entry_price,
            quantity=qty,
            take_profit=take_profit,
            stop_loss=stop_loss,
            mode=self.config.mode,
            opened_at=now_iso(),
        )
        add_trade(
            symbol=symbol,
            side='BUY',
            price=entry_price,
            quantity=qty,
            notional=entry_price * qty,
            pnl=None,
            mode=self.config.mode,
            created_at=now_iso(),
            note='entry',
        )
        self.log('INFO', f'{symbol} pozisyon açıldı. entry={entry_price:.6f}, qty={qty:.8f}, tp={take_profit:.6f}, sl={stop_loss:.6f}')
