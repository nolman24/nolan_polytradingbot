"""
Polymarket CLOB API integration for trade execution and market monitoring
Now using official py-clob-client SDK
"""

import asyncio
import json
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict
import hashlib
import hmac

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds
    CLOB_CLIENT_AVAILABLE = True
except ImportError:
    CLOB_CLIENT_AVAILABLE = False
    ClobClient = None

from config import (
    POLYMARKET_CLOB_API,
    POLYMARKET_GAMMA_API,
    POLYMARKET_API_KEY,
    POLYMARKET_SECRET,
    POLYMARKET_SERIES,
    POLYMARKET_LIVE_WS_URL,
    MARKET_CONFIG,
    API_TIMEOUT,
    MAX_API_RETRIES,
    MARKET_KEYWORDS
)
from models import PolymarketMarket, MarketType, Side

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# POLYMARKET MARKET SCANNER
# ═══════════════════════════════════════════════════════════════════════════

class PolymarketScanner:
    """
    Scans Polymarket for relevant markets
    Identifies market types and extracts pricing data
    """
    
    def __init__(self):
        self.cached_markets: Dict[str, PolymarketMarket] = {}
        self.last_scan: Optional[datetime] = None
        self.ws_connection = None
        self.ws_running = False
        
        # Initialize official Polymarket SDK client
        if CLOB_CLIENT_AVAILABLE:
            try:
                # Try without credentials first (public read-only)
                self.clob_client = ClobClient(
                    host="https://clob.polymarket.com",
                    key="",
                    chain_id=137,  # Polygon mainnet
                    funder=""
                )
                log.info("✅ Official Polymarket SDK initialized")
            except Exception as e:
                log.warning(f"SDK initialization failed: {e}, will use direct API")
                self.clob_client = None
        else:
            log.warning("py-clob-client not installed")
            self.clob_client = None
    
    async def scan_markets(self) -> List[PolymarketMarket]:
        """Scan Polymarket for all relevant markets including crypto"""
        try:
            all_markets = []
            
            # Strategy 1: Fetch markets by SERIES (the correct way for 5/15-min markets!)
            log.info("📡 Fetching markets by series (crypto 5/15-min)...")
            for series_key, series_info in POLYMARKET_SERIES.items():
                try:
                    series_id = series_info["series_id"]
                    series_slug = series_info["series_slug"]
                    crypto = series_info.get("crypto", "CRYPTO")
                    
                    # Skip if series_id is not configured
                    if series_id is None:
                        log.debug(f"   ⏭️  Skipping {series_slug} (series_id not configured)")
                        continue
                    
                    log.info(f"   Fetching series: {series_slug} ({crypto}) - ID: {series_id}")
                    
                    # Query /events endpoint with series_id
                    response = requests.get(
                        f"{POLYMARKET_GAMMA_API}/events",
                        params={
                            "series_id": series_id,
                            "active": True,
                            "closed": False,
                            "limit": 100
                        },
                        timeout=API_TIMEOUT
                    )
                    
                    if response.status_code == 200:
                        events = response.json()
                        log.info(f"   ✅ Series {series_slug}: found {len(events)} events")
                        
                        # Extract markets from events
                        series_markets = []
                        for event in events:
                            event_markets = event.get("markets", [])
                            series_markets.extend(event_markets)
                            
                            # Log first sample only
                            if event_markets and len(series_markets) == len(event_markets):
                                sample = event_markets[0]
                                q = sample.get("question", "")
                                log.info(f"   📋 Sample market: '{q[:70]}'")
                        
                        log.info(f"   📊 Total markets in series: {len(series_markets)}")
                        all_markets.extend(series_markets)
                    else:
                        log.debug(f"Series fetch returned {response.status_code}")
                        
                except Exception as e:
                    log.warning(f"Failed to fetch series {series_key}: {e}")
            
            # Strategy 2: Try official SDK client if available
            if self.clob_client:
                try:
                    log.info("📡 Fetching markets via official SDK...")
                    
                    # Try get_markets() method
                    sdk_markets = self.clob_client.get_markets()
                    if sdk_markets:
                        log.info(f"   SDK get_markets() returned {len(sdk_markets)} markets")
                        
                        # Log sample market to see structure
                        if len(sdk_markets) > 0:
                            sample = sdk_markets[0]
                            log.info(f"   Sample SDK market keys: {list(sample.keys())[:10]}")
                            if "question" in sample or "market" in sample or "description" in sample:
                                q = sample.get("question") or sample.get("market") or sample.get("description", "")
                                log.info(f"   Sample question: '{q[:80]}'")
                        
                        all_markets.extend(sdk_markets)
                    
                    # Also try get_simplified_markets() if it exists
                    try:
                        simplified = self.clob_client.get_simplified_markets()
                        if simplified:
                            log.info(f"   SDK get_simplified_markets() returned {len(simplified)} markets")
                            # Add unique ones
                            existing_ids = {m.get("condition_id") or m.get("conditionId") for m in all_markets}
                            for market in simplified:
                                mid = market.get("condition_id") or market.get("conditionId")
                                if mid and mid not in existing_ids:
                                    all_markets.append(market)
                    except AttributeError:
                        log.debug("get_simplified_markets() not available")
                        
                except Exception as e:
                    log.warning(f"SDK market fetch failed: {e}, falling back to direct API")
            
            # Strategy 2: Get general active markets with higher limit
            log.info("Fetching general active markets...")
            response = requests.get(
                f"{POLYMARKET_GAMMA_API}/markets",
                params={"active": True, "closed": False, "limit": 1000},
                timeout=API_TIMEOUT
            )
            
            if response.status_code == 200:
                general_markets = response.json()
                
                # Filter out markets that already ended (API sometimes returns stale data)
                now = datetime.now(timezone.utc)
                valid_markets = []
                filtered_count = 0
                
                for market in general_markets:
                    end_time_str = market.get("end_date_iso") or market.get("end_date")
                    if end_time_str:
                        try:
                            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                            # Only include markets that end in the future or ended within last 5 minutes
                            if end_time > now - timedelta(minutes=5):
                                valid_markets.append(market)
                            else:
                                filtered_count += 1
                        except:
                            # If can't parse time, include it anyway
                            valid_markets.append(market)
                    else:
                        # No end time, include it
                        valid_markets.append(market)
                
                all_markets.extend(valid_markets)
                log.info(f"   Got {len(valid_markets)} valid markets (filtered {filtered_count} expired)")
            else:
                log.error(f"General market fetch failed: {response.status_code}")
            
            # Strategy 2: Try CLOB API markets endpoint
            try:
                log.info("Trying CLOB API for markets...")
                clob_response = requests.get(
                    "https://clob.polymarket.com/markets",
                    params={"active": True, "next_cursor": ""},
                    timeout=API_TIMEOUT
                )
                
                if clob_response.status_code == 200:
                    clob_data = clob_response.json()
                    clob_markets = clob_data.get("data", [])
                    log.info(f"   CLOB API returned {len(clob_markets)} markets")
                    
                    # Add unique markets
                    existing_ids = {m.get("conditionId") for m in all_markets if m.get("conditionId")}
                    for market in clob_markets:
                        cond_id = market.get("condition_id") or market.get("conditionId")
                        if cond_id and cond_id not in existing_ids:
                            all_markets.append(market)
                            existing_ids.add(cond_id)
                else:
                    log.debug(f"CLOB API returned {clob_response.status_code}")
            except Exception as e:
                log.debug(f"CLOB API fetch failed: {e}")
            
            # Strategy 3: Try fetching markets closing soon
            try:
                log.info("Fetching markets closing soon...")
                response = requests.get(
                    f"{POLYMARKET_GAMMA_API}/markets",
                    params={
                        "active": True, 
                        "closed": False,
                        "limit": 500,
                        "order": "end_date_min"
                    },
                    timeout=API_TIMEOUT
                )
                
                if response.status_code == 200:
                    closing_soon = response.json()
                    existing_ids = {m.get("conditionId") for m in all_markets}
                    new_count = 0
                    for market in closing_soon:
                        if market.get("conditionId") not in existing_ids:
                            all_markets.append(market)
                            existing_ids.add(market.get("conditionId"))
                            new_count += 1
                    if new_count > 0:
                        log.info(f"   Added {new_count} closing-soon markets")
            except Exception as e:
                log.debug(f"Closing-soon fetch failed: {e}")
            
            # Strategy 3: Search specifically for crypto markets
            crypto_searches = ["bitcoin", "ethereum", "btc", "eth", "xrp", "solana"]
            log.info("Searching for crypto markets...")
            for search_term in crypto_searches:
                try:
                    response = requests.get(
                        f"{POLYMARKET_GAMMA_API}/markets",
                        params={
                            "active": True,
                            "closed": False,
                            "limit": 100,
                            "search": search_term
                        },
                        timeout=API_TIMEOUT
                    )
                    
                    if response.status_code == 200:
                        search_results = response.json()
                        log.info(f"   Search '{search_term}': found {len(search_results)} markets")
                        # Add unique markets only
                        existing_ids = {m.get("conditionId") for m in all_markets}
                        new_count = 0
                        for market in search_results:
                            if market.get("conditionId") not in existing_ids:
                                all_markets.append(market)
                                existing_ids.add(market.get("conditionId"))
                                new_count += 1
                        if new_count > 0:
                            log.info(f"   Added {new_count} new markets from '{search_term}' search")
                except Exception as e:
                    log.debug(f"Search for {search_term} failed: {e}")
            
            # Parse all markets
            markets = []
            log.info(f"Parsing {len(all_markets)} total markets...")
            for market_data in all_markets:
                market = self._parse_market(market_data)
                if market:
                    markets.append(market)
                    self.cached_markets[market.condition_id] = market
            
            self.last_scan = datetime.now(timezone.utc)
            log.info(f"Scanned {len(markets)} Polymarket markets")
            
            # Debug: log market types found
            type_counts = {}
            for m in markets:
                t = m.market_type.value
                type_counts[t] = type_counts.get(t, 0) + 1
            log.info(f"Market types: {type_counts}")
            
            return markets
            
        except Exception as e:
            log.error(f"Market scan error: {e}")
            return list(self.cached_markets.values())
    
    def _parse_market(self, data: Dict) -> Optional[PolymarketMarket]:
        """Parse market data from API response or SDK"""
        try:
            # Handle both API format (conditionId) and SDK format (condition_id)
            question = data.get("question") or data.get("market") or data.get("description", "")
            condition_id = data.get("conditionId") or data.get("condition_id", "")
            
            if not question or not condition_id:
                return None
            
            # Identify market type
            market_type = self._identify_market_type(question)
            if not market_type:
                return None  # Not a market type we're monitoring
            
            # Extract pricing - handle different API formats
            outcome_prices = data.get("outcomePrices") or data.get("outcome_prices") or data.get("prices", [])
            if not outcome_prices or len(outcome_prices) < 2:
                return None
            
            # Parse prices - they might be strings, floats, or nested lists
            try:
                # If it's a string like "['0.5', '0.5']", parse it
                if isinstance(outcome_prices, str):
                    import ast
                    outcome_prices = ast.literal_eval(outcome_prices)
                
                # Extract first element if nested
                yes_val = outcome_prices[0]
                no_val = outcome_prices[1]
                
                # Handle nested lists [[value]] 
                if isinstance(yes_val, list):
                    yes_val = yes_val[0] if yes_val else 0
                if isinstance(no_val, list):
                    no_val = no_val[0] if no_val else 0
                
                yes_price = float(yes_val)
                no_price = float(no_val)
                
            except (ValueError, TypeError, IndexError) as e:
                log.debug(f"Could not parse prices from {outcome_prices}: {e}")
                return None
            
            # Get token IDs
            tokens = data.get("tokens", [])
            yes_token_id = tokens[0].get("token_id", "") if len(tokens) > 0 else ""
            no_token_id = tokens[1].get("token_id", "") if len(tokens) > 1 else ""
            
            # Parse end time
            end_date_str = data.get("endDate", "")
            try:
                end_time = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            except:
                end_time = datetime.now(timezone.utc) + timedelta(hours=1)
            
            # Additional metrics
            liquidity = float(data.get("liquidity", 0))
            volume_24h = float(data.get("volume24hr", 0))
            
            return PolymarketMarket(
                condition_id=condition_id,
                question=question,
                market_type=market_type,
                yes_price=yes_price,
                no_price=no_price,
                yes_token_id=yes_token_id,
                no_token_id=no_token_id,
                end_time=end_time,
                liquidity=liquidity,
                volume_24h=volume_24h,
            )
            
        except Exception as e:
            log.error(f"Error parsing market: {e}")
            return None
    
    def _identify_market_type(self, question: str) -> Optional[MarketType]:
        """Identify market type from question text"""
        q_lower = question.lower()
        
        # Use word boundaries to avoid false matches (e.g., "Netherlands" shouldn't match "eth")
        import re
        crypto_words = [
            r'\bbitcoin\b', r'\bbtc\b', 
            r'\bethereum\b', r'\beth\b',
            r'\bxrp\b', r'\bripple\b',
            r'\bsolana\b', r'\bsol\b'
        ]
        
        is_crypto = any(re.search(pattern, q_lower) for pattern in crypto_words)
        
        # Log for debugging
        if is_crypto:
            log.info(f"🔍 Checking crypto market: '{question[:80]}'")
            log.info(f"   Lowercase: '{q_lower[:80]}'")
        
        # Special handling for crypto time-based markets
        has_time = any(pattern in q_lower for pattern in ["am est", "pm est", "am et", "pm et", " am ", " pm ", ":00", ":05", ":10", ":15", ":20", ":25", ":30", ":35", ":40", ":45", ":50", ":55"])
        
        if is_crypto and has_time:
            log.info(f"   ✅ Matched crypto_5m (has time indicator)!")
            return MarketType("crypto_5m")
        
        # Check each market type's keywords
        for market_type, keywords in MARKET_KEYWORDS.items():
            if any(kw in q_lower for kw in keywords):
                if "crypto" in market_type and is_crypto:
                    log.info(f"   ✅ Matched {market_type}!")
                return MarketType(market_type)
        
        # If it's a crypto-related question but didn't match, log it
        if is_crypto:
            log.debug(f"   ℹ️ Crypto market but no specific type: '{question[:60]}'")
        
        return None
    
    async def start_websocket(self):
        """Start WebSocket connection for real-time market updates"""
        log.info("🎬 WebSocket start method called")
        
        try:
            import websockets
            log.info("✅ websockets library imported successfully")
        except ImportError as e:
            log.error(f"❌ Failed to import websockets: {e}")
            log.error("   Run: pip install websockets==12.0")
            return
        
        import asyncio
        
        # Use the CORRECT WebSocket URL for live data
        ws_url = POLYMARKET_LIVE_WS_URL
        self.ws_running = True
        
        log.info(f"🔌 Connecting to Polymarket Live Data WebSocket...")
        log.info(f"   URL: {ws_url}")
        
        while self.ws_running:
            try:
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as websocket:
                    self.ws_connection = websocket
                    log.info(f"✅ Connected to Polymarket Live Data!")
                    
                    # Subscribe to series updates
                    for series_key, series_info in POLYMARKET_SERIES.items():
                        try:
                            subscribe_msg = {
                                "type": "subscribe",
                                "channel": "series",
                                "series_id": series_info["series_id"]
                            }
                            await websocket.send(json.dumps(subscribe_msg))
                            log.info(f"📡 Subscribed to series: {series_info['series_slug']}")
                        except Exception as e:
                            log.debug(f"Subscription to {series_key} failed: {e}")
                    
                    log.info("👂 Listening for live market updates...")
                    
                    message_count = 0
                    
                    # Listen for messages
                    async for message in websocket:
                        if not self.ws_running:
                            break
                        
                        message_count += 1
                        
                        # Log first 5 messages to see format
                        if message_count <= 5:
                            log.info(f"📨 WebSocket message #{message_count}: {message[:300]}")
                        
                        try:
                            data = json.loads(message)
                            await self._handle_ws_message(data)
                        except json.JSONDecodeError as e:
                            log.debug(f"Non-JSON message: {message[:100]}")
                        except Exception as e:
                            log.debug(f"Message processing error: {e}")
                            
            except Exception as e:
                if self.ws_running:
                    log.warning(f"WebSocket disconnected: {e}")
                    log.info("   Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)
        
        log.info("WebSocket loop ended")
    
    async def _handle_ws_message(self, data: Dict):
        """Handle incoming WebSocket market update"""
        try:
            # Log first few messages to see format
            if len(self.cached_markets) < 10:
                log.info(f"📨 WebSocket message: {str(data)[:200]}")
            
            # WebSocket might send different message formats
            # Try to extract market data
            market_data = None
            
            if isinstance(data, dict):
                # Could be direct market data or wrapped
                if "data" in data:
                    market_data = data["data"]
                elif "question" in data:
                    market_data = data
                elif "event" in data or "type" in data:
                    # Might be a control message, skip
                    log.debug(f"Control message: {data.get('type', data.get('event'))}")
                    return
            
            if market_data:
                market = self._parse_market(market_data)
                
                if market:
                    # Add to cache
                    is_new = market.condition_id not in self.cached_markets
                    self.cached_markets[market.condition_id] = market
                    
                    # Log new crypto markets
                    if is_new and "crypto" in market.market_type.value:
                        log.info(f"🆕 New {market.market_type.value} market: {market.question[:50]}")
                        
        except Exception as e:
            log.debug(f"Error handling WebSocket message: {e}")
    
    async def stop_websocket(self):
        """Stop WebSocket connection"""
        self.ws_running = False
        if self.ws_connection:
            await self.ws_connection.close()
        log.info("WebSocket stopped")
    
    def get_market(self, condition_id: str) -> Optional[PolymarketMarket]:
        """Get cached market by condition ID"""
        return self.cached_markets.get(condition_id)
    
    def get_markets_by_type(self, market_type: MarketType) -> List[PolymarketMarket]:
        """Get all markets of a specific type"""
        return [m for m in self.cached_markets.values() if m.market_type == market_type]

# ═══════════════════════════════════════════════════════════════════════════
# POLYMARKET CLOB TRADER
# ═══════════════════════════════════════════════════════════════════════════

class PolymarketTrader:
    """
    Executes trades on Polymarket CLOB
    Handles order placement, fills, and position tracking
    """
    
    def __init__(self, api_key: str = "", secret: str = ""):
        self.api_key = api_key
        self.secret = secret
        self.base_url = POLYMARKET_CLOB_API
        self.session = requests.Session()
        
        if api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            })
    
    def _sign_request(self, method: str, path: str, body: str = "") -> str:
        """Generate HMAC signature for authenticated requests"""
        if not self.secret:
            return ""
        
        message = f"{method}{path}{body}"
        signature = hmac.new(
            self.secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def place_order(
        self,
        market: PolymarketMarket,
        side: Side,
        size_usd: float,
        price: float
    ) -> Optional[str]:
        """
        Place a market order on Polymarket
        Returns order ID if successful
        """
        try:
            token_id = market.yes_token_id if side == Side.YES else market.no_token_id
            
            # Calculate shares to buy
            shares = size_usd / price
            
            order_data = {
                "token_id": token_id,
                "side": "BUY",
                "type": "MARKET",  # Market order for speed
                "size": str(shares),
                "price": str(price),
            }
            
            log.info(f"Placing order: {side.value} {shares:.2f} shares @ ${price:.4f}")
            
            # In paper trading mode, simulate order
            if not self.api_key:
                log.info("📄 Paper trade simulated (no API key)")
                return f"paper_{datetime.now().timestamp()}"
            
            # Real order placement
            response = self.session.post(
                f"{self.base_url}/order",
                json=order_data,
                timeout=API_TIMEOUT
            )
            
            if response.status_code == 200 or response.status_code == 201:
                result = response.json()
                order_id = result.get("orderID", "")
                log.info(f"✅ Order placed: {order_id}")
                return order_id
            else:
                log.error(f"Order failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            log.error(f"Order placement error: {e}")
            return None
    
    async def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Check status of an order"""
        try:
            if order_id.startswith("paper_"):
                # Simulate filled for paper trades
                return {
                    "status": "FILLED",
                    "filled_size": "1.0",
                    "avg_fill_price": "0.50"
                }
            
            response = self.session.get(
                f"{self.base_url}/order/{order_id}",
                timeout=API_TIMEOUT
            )
            
            if response.status_code == 200:
                return response.json()
            return None
            
        except Exception as e:
            log.error(f"Order status error: {e}")
            return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order"""
        try:
            if order_id.startswith("paper_"):
                return True
            
            response = self.session.delete(
                f"{self.base_url}/order/{order_id}",
                timeout=API_TIMEOUT
            )
            
            return response.status_code == 200
            
        except Exception as e:
            log.error(f"Order cancellation error: {e}")
            return False
    
    async def get_positions(self) -> List[Dict]:
        """Get current positions"""
        try:
            if not self.api_key:
                return []  # Paper trading has separate tracking
            
            response = self.session.get(
                f"{self.base_url}/positions",
                timeout=API_TIMEOUT
            )
            
            if response.status_code == 200:
                return response.json()
            return []
            
        except Exception as e:
            log.error(f"Positions fetch error: {e}")
            return []

# ═══════════════════════════════════════════════════════════════════════════
# UNIFIED POLYMARKET INTERFACE
# ═══════════════════════════════════════════════════════════════════════════

class PolymarketInterface:
    """
    High-level interface to Polymarket
    Combines scanner and trader
    """
    
    def __init__(self, api_key: str = "", secret: str = ""):
        self.scanner = PolymarketScanner()
        self.trader = PolymarketTrader(api_key, secret)
        self.running = False
    
    async def start(self):
        """Start continuous market scanning via API and WebSocket"""
        self.running = True
        log.info("Starting Polymarket interface")
        
        # Run both API scanning and WebSocket concurrently
        log.info("🔄 Starting API scan loop...")
        log.info("🔄 Starting WebSocket connection...")
        
        tasks = [
            self._api_scan_loop(),
            self.scanner.start_websocket()
        ]
        
        # Gather with exception handling
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                task_name = ["API scan loop", "WebSocket"][i]
                log.error(f"❌ {task_name} failed: {result}")
    
    async def _api_scan_loop(self):
        """Periodic API scanning (backup for WebSocket)"""
        while self.running:
            try:
                await self.scanner.scan_markets()
                await asyncio.sleep(MARKET_CONFIG.polymarket_scan_interval)
            except Exception as e:
                log.error(f"Polymarket scan error: {e}")
                await asyncio.sleep(30)
    
    async def get_markets(self) -> List[PolymarketMarket]:
        """Get all monitored markets"""
        return list(self.scanner.cached_markets.values())
    
    async def get_markets_by_type(self, market_type: MarketType) -> List[PolymarketMarket]:
        """Get markets of specific type"""
        return self.scanner.get_markets_by_type(market_type)
    
    async def execute_trade(
        self,
        market: PolymarketMarket,
        side: Side,
        size_usd: float
    ) -> Optional[str]:
        """Execute trade at current market price"""
        price = market.get_price(side)
        return await self.trader.place_order(market, side, size_usd, price)
    
    def get_market(self, condition_id: str) -> Optional[PolymarketMarket]:
        """Get specific market"""
        return self.scanner.get_market(condition_id)
    
    async def stop(self):
        """Stop interface"""
        self.running = False
        await self.scanner.stop_websocket()
        log.info("Polymarket interface stopped")
