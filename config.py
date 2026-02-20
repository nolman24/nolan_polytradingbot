"""
PolyArb - Multi-Market Arbitrage Bot Configuration
Optimized for 15-20% monthly ROI through strategic market inefficiency exploitation
"""

import os
from dataclasses import dataclass
from typing import Dict, List

# ═══════════════════════════════════════════════════════════════════════════
# API KEYS & CREDENTIALS
# ═══════════════════════════════════════════════════════════════════════════

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_CLOB_KEY = os.getenv("POLYMARKET_CLOB_KEY", "")
POLYMARKET_SECRET = os.getenv("POLYMARKET_SECRET", "")

# Optional: For sports odds
THE_ODDS_API_KEY = os.getenv("THE_ODDS_API_KEY", "")

# ═══════════════════════════════════════════════════════════════════════════
# POLYMARKET ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

POLYMARKET_CLOB_API = "https://clob.polymarket.com"
POLYMARKET_GAMMA_API = "https://gamma-api.polymarket.com"

# Polymarket Series IDs for crypto markets
# These are the "channels" that contain the rotating short-duration markets
POLYMARKET_SERIES = {
    # BTC Markets
    "btc_15m": {
        "series_id": "10192",  # Confirmed working!
        "series_slug": "btc-up-or-down-15m",
        "market_type": "crypto_15m",
        "crypto": "BTC"
    },
    "btc_5m": {
        "series_id": None,  # Will be discovered via API
        "series_slug": "btc-up-or-down-5m",
        "market_type": "crypto_5m",
        "crypto": "BTC"
    },
    
    # ETH Markets
    "eth_15m": {
        "series_id": None,  # Will be discovered via API
        "series_slug": "eth-up-or-down-15m",
        "market_type": "crypto_15m",
        "crypto": "ETH"
    },
    "eth_5m": {
        "series_id": None,  # Will be discovered via API
        "series_slug": "eth-up-or-down-5m",
        "market_type": "crypto_5m",
        "crypto": "ETH"
    },
    
    # SOL Markets
    "sol_15m": {
        "series_id": None,  # Will be discovered via API
        "series_slug": "sol-up-or-down-15m",
        "market_type": "crypto_15m",
        "crypto": "SOL"
    },
    "sol_5m": {
        "series_id": None,  # Will be discovered via API
        "series_slug": "sol-up-or-down-5m",
        "market_type": "crypto_5m",
        "crypto": "SOL"
    },
    
    # XRP Markets
    "xrp_15m": {
        "series_id": None,  # Will be discovered via API
        "series_slug": "xrp-up-or-down-15m",
        "market_type": "crypto_15m",
        "crypto": "XRP"
    },
    "xrp_5m": {
        "series_id": None,  # Will be discovered via API
        "series_slug": "xrp-up-or-down-5m",
        "market_type": "crypto_5m",
        "crypto": "XRP"
    },
}

# Polymarket live data WebSocket (the correct one!)
POLYMARKET_LIVE_WS_URL = "wss://ws-live-data.polymarket.com"

# ═══════════════════════════════════════════════════════════════════════════
# TRADING PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TradingConfig:
    """Core trading configuration optimized for profitability"""
    
    # Minimum edge to consider an opportunity (higher = fewer but better trades)
    min_edge_percent: float = 3.0  # 3% minimum mispricing
    
    # Position sizing
    default_position_size: float = 50.0  # $50 USD per trade
    max_position_size: float = 200.0     # $200 max per trade
    max_total_exposure: float = 1000.0   # $1000 max total open positions
    
    # Exit strategies
    profit_target_percent: float = 50.0  # Sell when +50% profit
    stop_loss_percent: float = 20.0      # Sell when -20% loss
    time_limit_minutes: int = 30         # Exit if no movement after 30min
    
    # Smart exit (EV-based)
    smart_exit_enabled: bool = True
    smart_exit_threshold: float = 0.95   # Sell if EV(sell) > 0.95 * EV(hold)
    
    # Risk management
    max_concurrent_positions: int = 10
    max_daily_loss: float = 200.0
    
    # Market-specific sizing multipliers
    market_size_multipliers: Dict[str, float] = None
    
    def __post_init__(self):
        if self.market_size_multipliers is None:
            self.market_size_multipliers = {
                "crypto_5m": 1.0,    # Standard sizing for 5-min crypto
                "crypto_15m": 1.2,   # Slightly larger for 15-min
                "crypto_1h": 1.5,    # Larger for 1-hour
                "sports_live": 0.8,  # Smaller for live sports (more volatile)
                "sports_pregame": 1.0,
                "stocks": 1.0,
                "news": 0.5,         # Smaller for breaking news (unpredictable)
            }

TRADING_CONFIG = TradingConfig()

# ═══════════════════════════════════════════════════════════════════════════
# MARKET MONITORING
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MarketConfig:
    """Configuration for which markets to monitor"""
    
    # Crypto markets
    monitor_btc_5m: bool = True
    monitor_btc_15m: bool = True
    monitor_btc_1h: bool = True
    monitor_eth_5m: bool = True
    monitor_eth_15m: bool = True
    monitor_xrp_5m: bool = True
    monitor_xrp_15m: bool = True
    monitor_sol_5m: bool = True
    monitor_sol_15m: bool = True
    
    # Sports markets
    monitor_nfl: bool = True
    monitor_nba: bool = True
    monitor_mlb: bool = True
    monitor_soccer: bool = False  # International, harder to get odds
    
    # Financial markets
    monitor_stocks: bool = True
    monitor_economic_data: bool = True
    
    # Update intervals (seconds)
    crypto_update_interval: float = 1.0      # Check crypto every 1 second
    sports_update_interval: float = 5.0      # Check sports every 5 seconds
    stocks_update_interval: float = 2.0      # Check stocks every 2 seconds
    
    # Polymarket market scanning
    polymarket_scan_interval: float = 3.0    # Scan all markets every 3 seconds
    
MARKET_CONFIG = MarketConfig()

# ═══════════════════════════════════════════════════════════════════════════
# DATA SOURCES
# ═══════════════════════════════════════════════════════════════════════════

# Multi-Exchange WebSocket endpoints for cross-verification
BINANCE_WS_BASE = "wss://stream.binance.com:9443/ws"
BINANCE_STREAMS = {
    "BTCUSDT": f"{BINANCE_WS_BASE}/btcusdt@trade",
    "ETHUSDT": f"{BINANCE_WS_BASE}/ethusdt@trade",
    "XRPUSDT": f"{BINANCE_WS_BASE}/xrpusdt@trade",
    "SOLUSDT": f"{BINANCE_WS_BASE}/solusdt@trade",
}

# Coinbase WebSocket
COINBASE_WS = "wss://ws-feed.exchange.coinbase.com"
COINBASE_PAIRS = ["BTC-USD", "ETH-USD", "XRP-USD", "SOL-USD"]

# Kraken WebSocket
KRAKEN_WS = "wss://ws.kraken.com"
KRAKEN_PAIRS = ["XBT/USD", "ETH/USD", "XRP/USD", "SOL/USD"]

# Sports odds API
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Stock data (using Yahoo Finance as free option)
YAHOO_FINANCE_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

# ═══════════════════════════════════════════════════════════════════════════
# OPERATIONAL SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

# Trading mode
PAPER_TRADING = True  # Start in paper mode by default

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "polyarb.log"

# State persistence
STATE_FILE = "polyarb_state.json"
POSITIONS_FILE = "positions.json"

# Performance tracking
TRACK_PERFORMANCE = True
PERFORMANCE_FILE = "performance.json"

# Telegram notifications
NOTIFY_ON_OPPORTUNITY = True
NOTIFY_ON_TRADE = True
NOTIFY_ON_EXIT = True
NOTIFY_ON_PNL_UPDATE = True  # Hourly P&L updates

# Safety limits
MAX_API_RETRIES = 3
API_TIMEOUT = 10  # seconds
WEBSOCKET_RECONNECT_DELAY = 5  # seconds

# ═══════════════════════════════════════════════════════════════════════════
# MARKET TYPE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

MARKET_TYPES = {
    "crypto_5m": "5-Minute Crypto Price",
    "crypto_15m": "15-Minute Crypto Price",
    "crypto_1h": "1-Hour Crypto Price",
    "sports_live": "Live Sports Game",
    "sports_pregame": "Pre-Game Sports",
    "stocks": "Stock Price Prediction",
    "economic": "Economic Data Release",
    "news": "Breaking News Event",
}

# Keywords to identify Polymarket market types
MARKET_KEYWORDS = {
    "crypto_5m": ["5 minutes", "5 minute", "5-minute", "5min"],  # Now includes actual format!
    "crypto_15m": ["15 minutes", "15 minute", "15-minute", "15min"],
    "crypto_1h": ["1 hour", "60 minutes", "60 minute"],
    "crypto_updown": ["up or down", "up/down", "higher or lower", "above or below"],
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
PolyArb Configuration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Trading Mode: {'📄 Paper' if PAPER_TRADING else '💰 LIVE'}
Min Edge: {TRADING_CONFIG.min_edge_percent}%
Position Size: ${TRADING_CONFIG.default_position_size}
Max Exposure: ${TRADING_CONFIG.max_total_exposure}
Profit Target: {TRADING_CONFIG.profit_target_percent}%
Stop Loss: {TRADING_CONFIG.stop_loss_percent}%

Monitored Markets:
{'✅' if MARKET_CONFIG.monitor_btc_5m else '⬜'} BTC 5-min
{'✅' if MARKET_CONFIG.monitor_btc_15m else '⬜'} BTC 15-min
{'✅' if MARKET_CONFIG.monitor_eth_5m else '⬜'} ETH 5-min
{'✅' if MARKET_CONFIG.monitor_eth_15m else '⬜'} ETH 15-min
{'✅' if MARKET_CONFIG.monitor_xrp_5m else '⬜'} XRP 5-min
{'✅' if MARKET_CONFIG.monitor_xrp_15m else '⬜'} XRP 15-min
{'✅' if MARKET_CONFIG.monitor_sol_5m else '⬜'} SOL 5-min
{'✅' if MARKET_CONFIG.monitor_sol_15m else '⬜'} SOL 15-min
{'✅' if MARKET_CONFIG.monitor_nfl else '⬜'} NFL
{'✅' if MARKET_CONFIG.monitor_nba else '⬜'} NBA
{'✅' if MARKET_CONFIG.monitor_stocks else '⬜'} Stocks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

def validate_config() -> List[str]:
    """Validate configuration and return list of issues"""
    issues = []
    
    if not TELEGRAM_TOKEN:
        issues.append("❌ TELEGRAM_TOKEN not set")
    
    if not PAPER_TRADING and not POLYMARKET_API_KEY:
        issues.append("❌ POLYMARKET_API_KEY required for live trading")
    
    if TRADING_CONFIG.min_edge_percent < 1.0:
        issues.append("⚠️ min_edge_percent < 1% may generate too many false signals")
    
    if TRADING_CONFIG.default_position_size > TRADING_CONFIG.max_total_exposure:
        issues.append("❌ default_position_size exceeds max_total_exposure")
    
    return issues
