"""
Real-time market data monitors using WebSockets for minimal latency
Enhanced with multi-exchange price aggregation and technical indicators
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Callable, Optional, List
from collections import deque
import websockets
from websockets.exceptions import ConnectionClosed

from config import BINANCE_STREAMS, COINBASE_WS, COINBASE_PAIRS, KRAKEN_WS, KRAKEN_PAIRS, MARKET_CONFIG
from models import ExternalPrice

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# PRICE AGGREGATOR
# ═══════════════════════════════════════════════════════════════════════════

class PriceAggregator:
    """
    Aggregates prices from multiple exchanges
    Provides best price, average price, and detects arbitrage
    """
    
    def __init__(self):
        self.prices: Dict[str, Dict[str, float]] = {}  # {symbol: {exchange: price}}
        self.price_history: Dict[str, deque] = {}  # For technical analysis
        
    def update_price(self, symbol: str, exchange: str, price: float):
        """Update price from an exchange"""
        # Normalize symbol (BTC-USD, BTCUSDT, XBT/USD all become BTC)
        normalized = self._normalize_symbol(symbol)
        
        if normalized not in self.prices:
            self.prices[normalized] = {}
            self.price_history[normalized] = deque(maxlen=100)  # Keep last 100 prices
        
        self.prices[normalized][exchange] = price
        self.price_history[normalized].append({
            'price': price,
            'timestamp': datetime.now(timezone.utc),
            'exchange': exchange
        })
    
    def get_best_price(self, symbol: str) -> Optional[float]:
        """Get most reliable price (median of all exchanges)"""
        normalized = self._normalize_symbol(symbol)
        
        if normalized not in self.prices or not self.prices[normalized]:
            return None
        
        prices = list(self.prices[normalized].values())
        
        if len(prices) == 1:
            return prices[0]
        
        # Return median to avoid outliers
        prices.sort()
        mid = len(prices) // 2
        
        if len(prices) % 2 == 0:
            return (prices[mid-1] + prices[mid]) / 2
        return prices[mid]
    
    def get_price_history(self, symbol: str, count: int = 20) -> List[float]:
        """Get recent price history for technical analysis"""
        normalized = self._normalize_symbol(symbol)
        
        if normalized not in self.price_history:
            return []
        
        history = list(self.price_history[normalized])
        return [h['price'] for h in history[-count:]]
    
    def get_volume_weighted_price(self, symbol: str) -> Optional[float]:
        """Get volume-weighted average (if we had volume data)"""
        # Simplified: just use average for now
        normalized = self._normalize_symbol(symbol)
        
        if normalized not in self.prices or not self.prices[normalized]:
            return None
        
        prices = list(self.prices[normalized].values())
        return sum(prices) / len(prices)
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol names across exchanges"""
        # Convert all to simple format: BTC, ETH, XRP, SOL
        symbol = symbol.upper()
        
        if 'BTC' in symbol or 'XBT' in symbol:
            return 'BTC'
        elif 'ETH' in symbol:
            return 'ETH'
        elif 'XRP' in symbol:
            return 'XRP'
        elif 'SOL' in symbol:
            return 'SOL'
        
        return symbol

# ═══════════════════════════════════════════════════════════════════════════
# BINANCE WEBSOCKET MONITOR
# ═══════════════════════════════════════════════════════════════════════════

class BinanceMonitor:
    """
    Monitor Binance real-time prices via WebSocket
    Ultra-low latency for crypto arbitrage
    """
    
    def __init__(self, aggregator=None):
        self.aggregator = aggregator
        self.connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.latest_prices: Dict[str, ExternalPrice] = {}
        self.callbacks: Dict[str, list] = {}
        self.running = False
    
    async def start(self, symbols: list = None):
        """Start monitoring specified symbols"""
        if symbols is None:
            symbols = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT"]
        
        self.running = True
        log.info(f"Starting Binance WebSocket monitors for {symbols}")
        
        # Start a monitor task for each symbol
        tasks = [self._monitor_symbol(symbol) for symbol in symbols]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _monitor_symbol(self, symbol: str):
        """Monitor a single symbol with auto-reconnect"""
        ws_url = BINANCE_STREAMS.get(symbol)
        if not ws_url:
            log.error(f"No WebSocket URL configured for {symbol}")
            return
        
        while self.running:
            try:
                async with websockets.connect(ws_url) as websocket:
                    self.connections[symbol] = websocket
                    log.info(f"✅ Connected to Binance {symbol} stream")
                    
                    async for message in websocket:
                        if not self.running:
                            break
                        
                        await self._handle_message(symbol, message)
                        
            except ConnectionClosed:
                log.warning(f"Binance {symbol} connection closed, reconnecting...")
                await asyncio.sleep(2)
            except Exception as e:
                log.error(f"Binance {symbol} error: {e}")
                await asyncio.sleep(5)
    
    async def _handle_message(self, symbol: str, message: str):
        """Process incoming price update"""
        try:
            data = json.loads(message)
            
            # Binance trade stream format: {"p": "price", "q": "quantity", "T": timestamp}
            price = float(data.get("p", 0))
            if price <= 0:
                return
            
            # Update aggregator if available
            if self.aggregator:
                self.aggregator.update_price(symbol, "binance", price)
            
            # Create price object
            price_obj = ExternalPrice(
                source="binance",
                symbol=symbol,
                price=price,
                timestamp=datetime.now(timezone.utc),
                metadata={"quantity": data.get("q")}
            )
            
            # Store latest
            self.latest_prices[symbol] = price_obj
            
            # Call registered callbacks
            for callback in self.callbacks.get(symbol, []):
                try:
                    await callback(price_obj)
                except Exception as e:
                    log.error(f"Callback error for {symbol}: {e}")
                    
        except Exception as e:
            log.error(f"Error handling Binance message: {e}")
    
    def get_latest_price(self, symbol: str) -> Optional[ExternalPrice]:
        """Get most recent price for symbol"""
        return self.latest_prices.get(symbol)
    
    def register_callback(self, symbol: str, callback: Callable):
        """Register callback for price updates"""
        if symbol not in self.callbacks:
            self.callbacks[symbol] = []
        self.callbacks[symbol].append(callback)
    
    async def stop(self):
        """Stop all monitors"""
        self.running = False
        for ws in self.connections.values():
            await ws.close()
        log.info("Binance monitors stopped")

# ═══════════════════════════════════════════════════════════════════════════
# COINBASE WEBSOCKET MONITOR
# ═══════════════════════════════════════════════════════════════════════════

class CoinbaseMonitor:
    """Monitor Coinbase real-time prices"""
    
    def __init__(self, aggregator: PriceAggregator):
        self.aggregator = aggregator
        self.connection = None
        self.running = False
    
    async def start(self):
        """Start Coinbase WebSocket"""
        self.running = True
        log.info("Starting Coinbase WebSocket monitor")
        
        while self.running:
            try:
                async with websockets.connect(COINBASE_WS) as websocket:
                    self.connection = websocket
                    
                    # Subscribe to ticker channel
                    subscribe_msg = {
                        "type": "subscribe",
                        "product_ids": COINBASE_PAIRS,
                        "channels": ["ticker"]
                    }
                    await websocket.send(json.dumps(subscribe_msg))
                    log.info(f"✅ Connected to Coinbase")
                    
                    async for message in websocket:
                        if not self.running:
                            break
                        await self._handle_message(message)
                        
            except ConnectionClosed:
                log.warning("Coinbase connection closed, reconnecting...")
                await asyncio.sleep(2)
            except Exception as e:
                log.error(f"Coinbase error: {e}")
                await asyncio.sleep(5)
    
    async def _handle_message(self, message: str):
        """Process Coinbase message"""
        try:
            data = json.loads(message)
            
            if data.get("type") != "ticker":
                return
            
            product_id = data.get("product_id")
            price = float(data.get("price", 0))
            
            if price > 0:
                self.aggregator.update_price(product_id, "coinbase", price)
                
        except Exception as e:
            log.error(f"Error handling Coinbase message: {e}")
    
    async def stop(self):
        """Stop monitor"""
        self.running = False
        if self.connection:
            await self.connection.close()
        log.info("Coinbase monitor stopped")

# ═══════════════════════════════════════════════════════════════════════════
# KRAKEN WEBSOCKET MONITOR
# ═══════════════════════════════════════════════════════════════════════════

class KrakenMonitor:
    """Monitor Kraken real-time prices"""
    
    def __init__(self, aggregator: PriceAggregator):
        self.aggregator = aggregator
        self.connection = None
        self.running = False
    
    async def start(self):
        """Start Kraken WebSocket"""
        self.running = True
        log.info("Starting Kraken WebSocket monitor")
        
        while self.running:
            try:
                async with websockets.connect(KRAKEN_WS) as websocket:
                    self.connection = websocket
                    
                    # Subscribe to ticker channel
                    subscribe_msg = {
                        "event": "subscribe",
                        "pair": KRAKEN_PAIRS,
                        "subscription": {"name": "ticker"}
                    }
                    await websocket.send(json.dumps(subscribe_msg))
                    log.info(f"✅ Connected to Kraken")
                    
                    async for message in websocket:
                        if not self.running:
                            break
                        await self._handle_message(message)
                        
            except ConnectionClosed:
                log.warning("Kraken connection closed, reconnecting...")
                await asyncio.sleep(2)
            except Exception as e:
                log.error(f"Kraken error: {e}")
                await asyncio.sleep(5)
    
    async def _handle_message(self, message: str):
        """Process Kraken message"""
        try:
            data = json.loads(message)
            
            # Kraken ticker format is array-based
            if isinstance(data, list) and len(data) >= 4:
                if data[2] == "ticker":
                    pair = data[3]
                    ticker_data = data[1]
                    
                    # ticker_data["c"][0] is last trade price
                    if "c" in ticker_data and len(ticker_data["c"]) > 0:
                        price = float(ticker_data["c"][0])
                        if price > 0:
                            self.aggregator.update_price(pair, "kraken", price)
                
        except Exception as e:
            log.error(f"Error handling Kraken message: {e}")
    """
    Monitor sports betting odds from The Odds API
    Polls API at configured intervals
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.latest_odds: Dict[str, ExternalPrice] = {}
        self.callbacks: list = []
        self.running = False
    
    async def start(self):
        """Start monitoring sports odds"""
        if not self.api_key:
            log.warning("No Odds API key provided, sports monitoring disabled")
            return
        
        self.running = True
        log.info("Starting sports odds monitor")
        
        while self.running:
            try:
                await self._fetch_odds()
                await asyncio.sleep(MARKET_CONFIG.sports_update_interval)
            except Exception as e:
                log.error(f"Sports odds error: {e}")
                await asyncio.sleep(30)
    
    async def _fetch_odds(self):
        """Fetch current odds from API"""
        # TODO: Implement actual API calls
        # For now, placeholder
        log.debug("Fetching sports odds (placeholder)")
    
    def get_odds_for_game(self, game_id: str) -> Optional[ExternalPrice]:
        """Get odds for specific game"""
        return self.latest_odds.get(game_id)
    
    def register_callback(self, callback: Callable):
        """Register callback for odds updates"""
        self.callbacks.append(callback)
    
    async def stop(self):
        """Stop monitor"""
        self.running = False
        log.info("Sports odds monitor stopped")

# ═══════════════════════════════════════════════════════════════════════════
# STOCK PRICE MONITOR  
# ═══════════════════════════════════════════════════════════════════════════

class StockPriceMonitor:
    """
    Monitor stock prices using Yahoo Finance API
    Polls at configured intervals
    """
    
    def __init__(self):
        self.latest_prices: Dict[str, ExternalPrice] = {}
        self.callbacks: list = []
        self.running = False
        self.symbols = ["AAPL", "TSLA", "NVDA", "SPY"]  # Default watchlist
    
    async def start(self):
        """Start monitoring stock prices"""
        self.running = True
        log.info(f"Starting stock price monitor for {self.symbols}")
        
        while self.running:
            try:
                await self._fetch_prices()
                await asyncio.sleep(MARKET_CONFIG.stocks_update_interval)
            except Exception as e:
                log.error(f"Stock price error: {e}")
                await asyncio.sleep(30)
    
    async def _fetch_prices(self):
        """Fetch current stock prices"""
        # TODO: Implement actual Yahoo Finance API calls
        # For now, placeholder
        log.debug("Fetching stock prices (placeholder)")
    
    def get_price(self, symbol: str) -> Optional[ExternalPrice]:
        """Get latest price for symbol"""
        return self.latest_prices.get(symbol)
    
    def add_symbol(self, symbol: str):
        """Add symbol to watchlist"""
        if symbol not in self.symbols:
            self.symbols.append(symbol)
            log.info(f"Added {symbol} to stock watchlist")
    
    def register_callback(self, callback: Callable):
        """Register callback for price updates"""
        self.callbacks.append(callback)
    
    async def stop(self):
        """Stop monitor"""
        self.running = False
        log.info("Stock price monitor stopped")

# ═══════════════════════════════════════════════════════════════════════════
# UNIFIED MARKET DATA FEED
# ═══════════════════════════════════════════════════════════════════════════

class MarketDataFeed:
    """
    Unified interface to all market data sources
    Manages all monitors and provides single access point
    """
    
    def __init__(self, odds_api_key: str = ""):
        self.binance = BinanceMonitor()
        self.sports = SportsOddsMonitor(odds_api_key)
        self.stocks = StockPriceMonitor()
        self.running = False
    
    async def start(self):
        """Start all monitors"""
        self.running = True
        log.info("🚀 Starting market data feeds")
        
        # Start all monitors concurrently
        tasks = []
        
        # Determine which crypto symbols to monitor
        symbols = []
        if MARKET_CONFIG.monitor_btc_5m or MARKET_CONFIG.monitor_btc_15m or MARKET_CONFIG.monitor_btc_1h:
            symbols.append("BTCUSDT")
        if MARKET_CONFIG.monitor_eth_5m or MARKET_CONFIG.monitor_eth_15m:
            symbols.append("ETHUSDT")
        if MARKET_CONFIG.monitor_xrp_5m or MARKET_CONFIG.monitor_xrp_15m:
            symbols.append("XRPUSDT")
        if MARKET_CONFIG.monitor_sol_5m or MARKET_CONFIG.monitor_sol_15m:
            symbols.append("SOLUSDT")
        
        if symbols:
            tasks.append(self.binance.start(symbols))
        
        if MARKET_CONFIG.monitor_nfl or MARKET_CONFIG.monitor_nba or MARKET_CONFIG.monitor_mlb:
            tasks.append(self.sports.start())
        
        if MARKET_CONFIG.monitor_stocks:
            tasks.append(self.stocks.start())
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_btc_price(self) -> Optional[float]:
        """Get current BTC price"""
        price_obj = self.binance.get_latest_price("BTCUSDT")
        return price_obj.price if price_obj else None
    
    def get_eth_price(self) -> Optional[float]:
        """Get current ETH price"""
        price_obj = self.binance.get_latest_price("ETHUSDT")
        return price_obj.price if price_obj else None
    
    def get_xrp_price(self) -> Optional[float]:
        """Get current XRP price"""
        price_obj = self.binance.get_latest_price("XRPUSDT")
        return price_obj.price if price_obj else None
    
    def get_sol_price(self) -> Optional[float]:
        """Get current SOL price"""
        price_obj = self.binance.get_latest_price("SOLUSDT")
        return price_obj.price if price_obj else None
    
    def get_stock_price(self, symbol: str) -> Optional[float]:
        """Get current stock price"""
        price_obj = self.stocks.get_price(symbol)
        return price_obj.price if price_obj else None
    
    def register_crypto_callback(self, symbol: str, callback: Callable):
        """Register callback for crypto price updates"""
        self.binance.register_callback(symbol, callback)
    
    async def stop(self):
        """Stop all monitors"""
        log.info("Stopping market data feeds")
        await asyncio.gather(
            self.binance.stop(),
            self.sports.stop(),
            self.stocks.stop(),
        )
