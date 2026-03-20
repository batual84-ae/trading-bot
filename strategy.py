from dataclasses import dataclass

import pandas as pd

from indicators import ema, rsi


@dataclass
class StrategyResult:
    signal: str
    reason: str
    score: float
    dataframe: pd.DataFrame


class EMARSITrendStrategy:
    def __init__(self, ema_fast: int, ema_slow: int, rsi_period: int, rsi_buy_min: float, rsi_sell_max: float):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period
        self.rsi_buy_min = rsi_buy_min
        self.rsi_sell_max = rsi_sell_max

    def apply(self, df: pd.DataFrame) -> StrategyResult:
        out = df.copy()
        out['ema_fast'] = ema(out['close'], self.ema_fast)
        out['ema_slow'] = ema(out['close'], self.ema_slow)
        out['rsi'] = rsi(out['close'], self.rsi_period)
        out['ret_3'] = out['close'].pct_change(3)
        out['ret_6'] = out['close'].pct_change(6)

        if len(out) < max(self.ema_slow + 5, self.rsi_period + 5):
            return StrategyResult('HOLD', 'Yetersiz veri', 0.0, out)

        last = out.iloc[-1]
        prev = out.iloc[-2]

        bullish_cross = prev['ema_fast'] <= prev['ema_slow'] and last['ema_fast'] > last['ema_slow']
        bearish_cross = prev['ema_fast'] >= prev['ema_slow'] and last['ema_fast'] < last['ema_slow']
        ema_gap_pct = ((last['ema_fast'] / last['ema_slow']) - 1.0) * 100 if last['ema_slow'] else 0.0
        short_momentum = float(last['ret_3'] if pd.notna(last['ret_3']) else 0.0) * 100
        medium_momentum = float(last['ret_6'] if pd.notna(last['ret_6']) else 0.0) * 100
        rsi_strength = max(0.0, float(last['rsi']) - self.rsi_buy_min)
        score = max(0.0, ema_gap_pct * 20 + short_momentum * 8 + medium_momentum * 4 + rsi_strength * 0.5)

        if bearish_cross and last['rsi'] <= self.rsi_sell_max:
            return StrategyResult('SELL', f"EMA aşağı kesişim + RSI {last['rsi']:.2f}", score, out)

        if bullish_cross and last['rsi'] >= self.rsi_buy_min:
            return StrategyResult('BUY', f"EMA yukarı kesişim + RSI {last['rsi']:.2f}", score + 8, out)

        if (
            last['ema_fast'] > last['ema_slow']
            and last['rsi'] >= self.rsi_buy_min
            and short_momentum > 0
            and medium_momentum > -0.5
        ):
            return StrategyResult('BUY', f"Trend+momen­tum uygun, RSI {last['rsi']:.2f}", score, out)

        return StrategyResult('HOLD', f"Koşul yok, RSI {last['rsi']:.2f}", score, out)
