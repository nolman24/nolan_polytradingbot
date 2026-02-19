"""
AGGRESSIVE CONFIGURATION
For users targeting higher monthly ROI ($3,000/month with $3-5K capital)

⚠️ WARNING: Higher returns = Higher risk and volatility
- Larger position sizes
- Lower edge requirements  
- More concurrent positions
- Wider stop losses

USE THIS ONLY AFTER successful paper trading with default config!
"""

# TO USE THIS CONFIG:
# 1. Rename this file to config.py (backup original first!)
# 2. Or copy these values into your config.py

from datetime import timedelta
from dataclasses import dataclass
from typing import Dict
import os

# ═══════════════════════════════════════════════════════════════════════════
# API KEYS (same as regular config)
# ═══════════════════════════════════════════════════════════════════════════

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_CLOB_KEY = os.getenv("POLYMARKET_CLOB_KEY", "")
POLYMARKET_SECRET = os.getenv("POLYMARKET_SECRET", "")
THE_ODDS_API_KEY = os.getenv("THE_ODDS_API_KEY", "")

POLYMARKET_CLOB_API = "https://clob.polymarket.com"
POLYMARKET_GAMMA_API = "https://gamma-api.polymarket.com"

# ═══════════════════════════════════════════════════════════════════════════
# AGGRESSIVE TRADING PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TradingConfig:
    """AGGRESSIVE trading configuration for higher ROI"""
    
    # ⚡ AGGRESSIVE EDGE REQUIREMENTS
    min_edge_percent: float = 2.0  # Accept 2% edges (was 3%)
    
    # 💰 AGGRESSIVE POSITION SIZING  
    default_position_size: float = 150.0    # $150 per trade (was $50)
    max_position_size: float = 300.0        # $300 max (was $200)
    max_total_exposure: float = 3000.0      # $3K total (adjust to your capital!)
    
    # 🎯 FASTER EXITS (lock in profits quicker)
    profit_target_percent: float = 35.0     # Exit at +35% (was 50%)
    stop_loss_percent: float = 25.0         # Exit at -25% (was 20%)
    time_limit_minutes: int = 20            # Exit after 20min (was 30)
    
    # 🧠 Smart exit (keep enabled)
    smart_exit_enabled: bool = True
    smart_exit_threshold: float = 0.92      # Slightly lower threshold
    
    # ⚡ AGGRESSIVE RISK MANAGEMENT
    max_concurrent_positions: int = 15      # More positions (was 10)
    max_daily_loss: float = 500.0           # Higher daily limit (was $200)
    
    # Market-specific sizing (same as default)
    market_size_multipliers: Dict[str, float] = None
    
    def __post_init__(self):
        if self.market_size_multipliers is None:
            self.market_size_multipliers = {
                "crypto_5m": 1.0,
                "crypto_15m": 1.2,
                "crypto_1h": 1.5,
                "crypto_updown": 1.1,  # Slightly larger for Up/Down
                "sports_live": 0.8,
                "sports_pregame": 1.0,
                "stocks": 1.0,
                "news": 0.5,
            }

TRADING_CONFIG = TradingConfig()

# ═══════════════════════════════════════════════════════════════════════════
# AGGRESSIVE MARKET MONITORING
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MarketConfig:
    """Configuration for market monitoring"""
    
    # Crypto markets (all enabled)
    monitor_btc_5m: bool = True
    monitor_btc_15m: bool = True
    monitor_btc_1h: bool = True
    monitor_eth_5m: bool = True
    monitor_eth_15m: bool = True
    monitor_xrp_5m: bool = True
    monitor_xrp_15m: bool = True
    monitor_sol_5m: bool = True
    monitor_sol_15m: bool = True
    
    # Sports (disabled - not implemented)
    monitor_nfl: bool = False
    monitor_nba: bool = False
    monitor_mlb: bool = False
    monitor_soccer: bool = False
    
    # Other (disabled)
    monitor_stocks: bool = False
    monitor_economic_data: bool = False
    
    # ⚡ AGGRESSIVE UPDATE INTERVALS (faster scanning)
    crypto_update_interval: float = 0.5      # Every 0.5 sec (was 1.0)
    sports_update_interval: float = 5.0
    stocks_update_interval: float = 2.0
    polymarket_scan_interval: float = 2.0    # Every 2 sec (was 3.0)

MARKET_CONFIG = MarketConfig()

# ═══════════════════════════════════════════════════════════════════════════
# DATA SOURCES (same as default)
# ═══════════════════════════════════════════════════════════════════════════

BINANCE_WS_BASE = "wss://stream.binance.com:9443/ws"
BINANCE_STREAMS = {
    "BTCUSDT": f"{BINANCE_WS_BASE}/btcusdt@trade",
    "ETHUSDT": f"{BINANCE_WS_BASE}/ethusdt@trade",
    "XRPUSDT": f"{BINANCE_WS_BASE}/xrpusdt@trade",
    "SOLUSDT": f"{BINANCE_WS_BASE}/solusdt@trade",
}

COINBASE_WS = "wss://ws-feed.exchange.coinbase.com"
COINBASE_PAIRS = ["BTC-USD", "ETH-USD", "XRP-USD", "SOL-USD"]

KRAKEN_WS = "wss://ws.kraken.com"
KRAKEN_PAIRS = ["XBT/USD", "ETH/USD", "XRP/USD", "SOL/USD"]

ODDS_API_BASE = "https://api.the-odds-api.com/v4"
YAHOO_FINANCE_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

# ═══════════════════════════════════════════════════════════════════════════
# OPERATIONAL SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

PAPER_TRADING = True  # ⚠️ ALWAYS test in paper mode first!

LOG_LEVEL = "INFO"
LOG_FILE = "polyarb.log"

STATE_FILE = "polyarb_state.json"
POSITIONS_FILE = "positions.json"

TRACK_PERFORMANCE = True
PERFORMANCE_FILE = "performance.json"

NOTIFY_ON_OPPORTUNITY = True
NOTIFY_ON_TRADE = True
NOTIFY_ON_EXIT = True
NOTIFY_ON_PNL_UPDATE = True

MAX_API_RETRIES = 3
API_TIMEOUT = 10
WEBSOCKET_RECONNECT_DELAY = 5

# ═══════════════════════════════════════════════════════════════════════════
# MARKET TYPE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

MARKET_TYPES = {
    "crypto_5m": "5-Minute Crypto Price",
    "crypto_15m": "15-Minute Crypto Price",
    "crypto_1h": "1-Hour Crypto Price",
    "crypto_updown": "Crypto Up or Down",
    "sports_live": "Live Sports Game",
    "sports_pregame": "Pre-Game Sports",
    "stocks": "Stock Price Prediction",
    "economic": "Economic Data Release",
    "news": "Breaking News Event",
}

MARKET_KEYWORDS = {
    "crypto_5m": ["5 min", "5-min", "5min", "five minute"],
    "crypto_15m": ["15 min", "15-min", "15min", "fifteen minute"],
    "crypto_1h": ["1 hour", "1-hour", "1hr", "one hour"],
    "crypto_updown": ["up or down", "up/down", "higher or lower"],
    "sports_live": ["live", "in-game", "in game"],
    "sports_pregame": ["nfl", "nba", "mlb", "soccer", "game", "match"],
    "stocks": ["stock", "share", "nasdaq", "s&p", "dow"],
    "economic": ["gdp", "cpi", "inflation", "fed", "employment", "jobs"],
    "news": ["breaking", "announcement", "report"],
}

# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_config_summary() -> str:
    """Return human-readable config summary"""
    return f"""
PolyArb Configuration (AGGRESSIVE MODE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  AGGRESSIVE SETTINGS - Higher risk/reward
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Trading Mode: {'📄 Paper' if PAPER_TRADING else '💰 LIVE'}
Min Edge: {TRADING_CONFIG.min_edge_percent}% (AGGRESSIVE)
Position Size: ${TRADING_CONFIG.default_position_size} (LARGE)
Max Exposure: ${TRADING_CONFIG.max_total_exposure}
Profit Target: {TRADING_CONFIG.profit_target_percent}% (FAST)
Stop Loss: {TRADING_CONFIG.stop_loss_percent}% (WIDER)
Max Daily Loss: ${TRADING_CONFIG.max_daily_loss} (HIGH)

Monitored Markets:
{'✅' if MARKET_CONFIG.monitor_btc_5m else '⬜'} BTC 5-min
{'✅' if MARKET_CONFIG.monitor_btc_15m else '⬜'} BTC 15-min
{'✅' if MARKET_CONFIG.monitor_eth_5m else '⬜'} ETH 5-min
{'✅' if MARKET_CONFIG.monitor_eth_15m else '⬜'} ETH 15-min
{'✅' if MARKET_CONFIG.monitor_xrp_5m else '⬜'} XRP 5-min
{'✅' if MARKET_CONFIG.monitor_xrp_15m else '⬜'} XRP 15-min
{'✅' if MARKET_CONFIG.monitor_sol_5m else '⬜'} SOL 5-min
{'✅' if MARKET_CONFIG.monitor_sol_15m else '⬜'} SOL 15-min
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Expected ROI: 50-100% monthly (high variance)
Capital Required: $3,000-5,000
Risk Level: MODERATE-HIGH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

def validate_config() -> list:
    """Validate configuration and return list of issues"""
    issues = []
    
    if not TELEGRAM_TOKEN:
        issues.append("❌ TELEGRAM_TOKEN not set")
    
    if not PAPER_TRADING and not POLYMARKET_API_KEY:
        issues.append("❌ POLYMARKET_API_KEY required for live trading")
    
    if TRADING_CONFIG.default_position_size > TRADING_CONFIG.max_total_exposure / 5:
        issues.append("⚠️ Position size might be too large relative to total exposure")
    
    if TRADING_CONFIG.max_daily_loss > TRADING_CONFIG.max_total_exposure:
        issues.append("⚠️ max_daily_loss exceeds max_total_exposure")
    
    return issues
