"""
Data models for market monitoring and position tracking
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, List
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════

class MarketType(Enum):
    CRYPTO_5M = "crypto_5m"
    CRYPTO_15M = "crypto_15m"
    CRYPTO_1H = "crypto_1h"
    CRYPTO_UPDOWN = "crypto_updown"  # NEW!
    SPORTS_LIVE = "sports_live"
    SPORTS_PREGAME = "sports_pregame"
    STOCKS = "stocks"
    ECONOMIC = "economic"
    NEWS = "news"

class Side(Enum):
    YES = "YES"
    NO = "NO"

class PositionStatus(Enum):
    OPEN = "open"
    CLOSED_WIN = "closed_win"
    CLOSED_LOSS = "closed_loss"
    CLOSED_BREAK_EVEN = "closed_break_even"

class ExitReason(Enum):
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    TIME_LIMIT = "time_limit"
    SMART_EXIT = "smart_exit"
    MANUAL = "manual"
    RESOLVED = "resolved"

# ═══════════════════════════════════════════════════════════════════════════
# MARKET DATA
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ExternalPrice:
    """Price from external source (Binance, sportsbook, etc.)"""
    source: str
    symbol: str
    price: float
    timestamp: datetime
    metadata: Dict = field(default_factory=dict)

@dataclass
class PolymarketMarket:
    """Polymarket market data"""
    condition_id: str
    question: str
    market_type: MarketType
    yes_price: float
    no_price: float
    yes_token_id: str
    no_token_id: str
    end_time: datetime
    liquidity: float = 0.0
    volume_24h: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def get_price(self, side: Side) -> float:
        return self.yes_price if side == Side.YES else self.no_price

@dataclass
class ArbitrageOpportunity:
    """Detected arbitrage opportunity"""
    market: PolymarketMarket
    external_price: ExternalPrice
    side: Side  # Which side to buy on Polymarket
    poly_price: float  # Price on Polymarket
    true_probability: float  # Calculated from external data
    edge_percent: float  # Mispricing percentage
    expected_profit: float  # Expected profit in USD
    recommended_size: float  # Position size in USD
    expires_at: datetime  # When opportunity likely expires
    confidence: float = 1.0  # 0-1, how confident we are
    
    def to_dict(self) -> Dict:
        return {
            "question": self.market.question,
            "market_type": self.market.market_type.value,
            "side": self.side.value,
            "poly_price": self.poly_price,
            "true_prob": self.true_probability,
            "edge": f"{self.edge_percent:.2f}%",
            "expected_profit": f"${self.expected_profit:.2f}",
            "size": f"${self.recommended_size:.2f}",
            "confidence": f"{self.confidence*100:.0f}%",
        }

# ═══════════════════════════════════════════════════════════════════════════
# POSITION TRACKING
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Position:
    """Open or closed trading position"""
    position_id: str
    market: PolymarketMarket
    side: Side
    entry_price: float
    shares: float
    cost_basis: float  # Total USD spent
    
    # Entry details
    entry_time: datetime
    entry_reason: str  # Why we took this trade
    market_type: MarketType
    
    # Current state
    status: PositionStatus = PositionStatus.OPEN
    current_price: float = 0.0
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    
    # Exit details (if closed)
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[ExitReason] = None
    realized_pnl: float = 0.0
    
    # Tracking
    max_price: float = 0.0
    min_price: float = 0.0
    
    def update_current_price(self, price: float):
        """Update current market price and calculate unrealized P&L"""
        self.current_price = price
        self.current_value = self.shares * price
        self.unrealized_pnl = self.current_value - self.cost_basis
        
        # Track highs/lows
        if price > self.max_price:
            self.max_price = price
        if self.min_price == 0 or price < self.min_price:
            self.min_price = price
    
    def calculate_roi(self) -> float:
        """Return ROI as percentage"""
        if self.cost_basis == 0:
            return 0.0
        if self.status == PositionStatus.OPEN:
            return (self.unrealized_pnl / self.cost_basis) * 100
        return (self.realized_pnl / self.cost_basis) * 100
    
    def should_exit_profit_target(self, target_percent: float) -> bool:
        """Check if profit target hit"""
        return self.calculate_roi() >= target_percent
    
    def should_exit_stop_loss(self, stop_percent: float) -> bool:
        """Check if stop loss hit"""
        return self.calculate_roi() <= -stop_percent
    
    def should_exit_time_limit(self, limit_minutes: int) -> bool:
        """Check if time limit exceeded"""
        elapsed = (datetime.now(timezone.utc) - self.entry_time).seconds / 60
        return elapsed >= limit_minutes
    
    def calculate_ev_hold(self) -> float:
        """Calculate expected value of holding position"""
        # Simplified: assume 50/50 if market resolves in our favor
        # In reality, would use external data to estimate win probability
        win_prob = 0.5
        max_profit = self.shares * (1.0 - self.entry_price)
        max_loss = self.cost_basis
        return (win_prob * max_profit) - ((1 - win_prob) * max_loss)
    
    def calculate_ev_sell(self) -> float:
        """Calculate expected value of selling now"""
        return self.unrealized_pnl  # Guaranteed
    
    def to_dict(self) -> Dict:
        """Convert to dict for JSON serialization"""
        return {
            "position_id": self.position_id,
            "question": self.market.question,
            "side": self.side.value,
            "entry_price": self.entry_price,
            "shares": self.shares,
            "cost_basis": self.cost_basis,
            "status": self.status.value,
            "current_price": self.current_price,
            "current_value": self.current_value,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "roi_percent": self.calculate_roi(),
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_reason": self.exit_reason.value if self.exit_reason else None,
        }

# ═══════════════════════════════════════════════════════════════════════════
# PERFORMANCE TRACKING
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PerformanceMetrics:
    """Track bot performance over time"""
    
    # Overall stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    break_even_trades: int = 0
    
    # P&L
    total_pnl: float = 0.0
    total_invested: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    # By market type
    pnl_by_market_type: Dict[str, float] = field(default_factory=dict)
    trades_by_market_type: Dict[str, int] = field(default_factory=dict)
    
    # Timing
    avg_hold_time_minutes: float = 0.0
    fastest_profit_seconds: float = 0.0
    
    # Current period
    daily_pnl: float = 0.0
    daily_trades: int = 0
    last_reset: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def add_closed_position(self, position: Position):
        """Update metrics with closed position"""
        self.total_trades += 1
        self.total_pnl += position.realized_pnl
        self.daily_pnl += position.realized_pnl
        self.daily_trades += 1
        
        if position.realized_pnl > 0:
            self.winning_trades += 1
            if position.realized_pnl > self.largest_win:
                self.largest_win = position.realized_pnl
        elif position.realized_pnl < 0:
            self.losing_trades += 1
            if position.realized_pnl < self.largest_loss:
                self.largest_loss = position.realized_pnl
        else:
            self.break_even_trades += 1
        
        # Track by market type
        mt = position.market_type.value
        self.pnl_by_market_type[mt] = self.pnl_by_market_type.get(mt, 0) + position.realized_pnl
        self.trades_by_market_type[mt] = self.trades_by_market_type.get(mt, 0) + 1
    
    def get_win_rate(self) -> float:
        """Calculate win rate percentage"""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    def get_roi(self) -> float:
        """Calculate overall ROI"""
        if self.total_invested == 0:
            return 0.0
        return (self.total_pnl / self.total_invested) * 100
    
    def reset_daily_stats(self):
        """Reset daily tracking"""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.last_reset = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict:
        return {
            "total_trades": self.total_trades,
            "win_rate": f"{self.get_win_rate():.1f}%",
            "total_pnl": f"${self.total_pnl:.2f}",
            "roi": f"{self.get_roi():.1f}%",
            "daily_pnl": f"${self.daily_pnl:.2f}",
            "daily_trades": self.daily_trades,
            "largest_win": f"${self.largest_win:.2f}",
            "largest_loss": f"${self.largest_loss:.2f}",
        }
