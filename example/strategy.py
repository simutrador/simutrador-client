"""
Trading Strategy Module

This module contains the core trading strategy logic that can be used by both:
- backtest_strategy.py (for historical data analysis and backtesting)
- main.py (for live trading with real-time data from simutrador-server)

The strategy is decoupled from data sources and execution environments,
making it reusable and testable.
"""

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class Signal:
    """Represents a trading signal."""
    symbol: str
    action: str  # "BUY", "SELL", "HOLD"
    confidence: float  # 0.0 to 1.0
    price: float
    timestamp: str
    reason: str = ""


@dataclass
class Position:
    """Represents an open trading position."""
    symbol: str
    entry_price: float
    quantity: float
    entry_time: str
    status: str = "OPEN"  # "OPEN", "CLOSED"


class TradingStrategy:
    """
    Base trading strategy class.
    
    This class defines the interface for trading strategies.
    Implement the calculate_signal method with your specific strategy logic.
    """
    
    def __init__(self, name: str = "DefaultStrategy"):
        """
        Initialize the strategy.
        
        Args:
            name: Strategy name
        """
        self.name = name
        self.positions: dict[str, Position] = {}
        self.signals_history = []
    
    def calculate_signal(self, data: pd.DataFrame, symbol: str) -> Signal:
        """
        Calculate trading signal based on data.
        
        This is the main method to override with your strategy logic.
        
        Args:
            data: DataFrame with OHLCV data
            symbol: Trading symbol
        
        Returns:
            Signal object with trading action
        """
        # TODO: Implement your strategy logic here
        # Example: Calculate indicators, analyze patterns, generate signals
        
        if len(data) < 2:
            return Signal(
                symbol=symbol,
                action="HOLD",
                confidence=0.0,
                price=data.iloc[-1]['close'] if len(data) > 0 else 0,
                timestamp=str(data.index[-1]) if len(data) > 0 else "",
                reason="Insufficient data"
            )
        
        # Placeholder logic: Simple moving average crossover
        if len(data) >= 20:
            sma_short = data['close'].tail(5).mean()
            sma_long = data['close'].tail(20).mean()
            
            current_price = data.iloc[-1]['close']
            
            if sma_short > sma_long:
                action = "BUY"
                confidence = 0.6
                reason = "Short MA above Long MA"
            elif sma_short < sma_long:
                action = "SELL"
                confidence = 0.6
                reason = "Short MA below Long MA"
            else:
                action = "HOLD"
                confidence = 0.5
                reason = "MAs converging"
            
            return Signal(
                symbol=symbol,
                action=action,
                confidence=confidence,
                price=current_price,
                timestamp=str(data.index[-1]),
                reason=reason
            )
        
        return Signal(
            symbol=symbol,
            action="HOLD",
            confidence=0.0,
            price=data.iloc[-1]['close'],
            timestamp=str(data.index[-1]),
            reason="Insufficient data for analysis"
        )
    
    def on_signal(self, signal: Signal) -> dict[str, Any]:
        """
        Process a trading signal and execute action.
        
        Args:
            signal: Signal object
        
        Returns:
            Dictionary with execution details
        """
        self.signals_history.append(signal)
        
        if signal.action == "BUY":
            return self._execute_buy(signal)
        elif signal.action == "SELL":
            return self._execute_sell(signal)
        else:
            return {"action": "HOLD", "symbol": signal.symbol}
    
    def _execute_buy(self, signal: Signal) -> dict[str, Any]:
        """Execute a buy signal."""
        position = Position(
            symbol=signal.symbol,
            entry_price=signal.price,
            quantity=1.0,  # TODO: Implement position sizing
            entry_time=signal.timestamp
        )
        self.positions[signal.symbol] = position
        
        return {
            "action": "BUY",
            "symbol": signal.symbol,
            "price": signal.price,
            "confidence": signal.confidence,
            "reason": signal.reason
        }
    
    def _execute_sell(self, signal: Signal) -> dict[str, Any]:
        """Execute a sell signal."""
        if signal.symbol in self.positions:
            position = self.positions[signal.symbol]
            position.status = "CLOSED"
            
            return {
                "action": "SELL",
                "symbol": signal.symbol,
                "price": signal.price,
                "entry_price": position.entry_price,
                "pnl": (signal.price - position.entry_price) * position.quantity,
                "confidence": signal.confidence,
                "reason": signal.reason
            }
        
        return {
            "action": "SELL",
            "symbol": signal.symbol,
            "status": "no_position"
        }
    
    def get_positions(self) -> dict[str, Position]:
        """Get all open positions."""
        return {k: v for k, v in self.positions.items() if v.status == "OPEN"}
    
    def get_signals_history(self):
        """Get all signals generated by the strategy."""
        return self.signals_history
    
    def reset(self):
        """Reset strategy state."""
        self.positions.clear()
        self.signals_history.clear()

