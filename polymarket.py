"""
Polymarket CLOB API integration for trade execution and market monitoring
"""

import asyncio
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict
import hashlib
import hmac

from config import (
    POLYMARKET_CLOB_API,
    POLYMARKET_GAMMA_API,
    POLYMARKET_API_KEY,
    POLYMARKET_SECRET,
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
    
    async def scan_markets(self) -> List[PolymarketMarket]:
        """Scan Polymarket for all relevant markets including crypto"""
        try:
            all_markets = []
            
            # Strategy 1: Get general active markets with higher limit
            log.info("Fetching general active markets...")
            response = requests.get(
                f"{POLYMARKET_GAMMA_API}/markets",
                params={"active": True, "closed": False, "limit": 1000},
                timeout=API_TIMEOUT
            )
            
            if response.status_code == 200:
                general_markets = response.json()
                all_markets.extend(general_markets)
                log.info(f"   Got {len(general_markets)} general markets")
            else:
                log.error(f"General market fetch failed: {response.status_code}")
            
            # Strategy 2: Try fetching markets closing soon (might include 5/15 min markets)
            try:
                log.info("Fetching markets closing soon...")
                response = requests.get(
                    f"{POLYMARKET_GAMMA_API}/markets",
                    params={
                        "active": True, 
                        "closed": False,
                        "limit": 500,
                        "order": "end_date_min"  # Try sorting by end date
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
        """Parse market data from API response"""
        try:
            question = data.get("question", "")
            condition_id = data.get("conditionId", "")
            
            if not question or not condition_id:
                return None
            
            # Identify market type
            market_type = self._identify_market_type(question)
            if not market_type:
                return None  # Not a market type we're monitoring
            
            # Extract pricing - handle different API formats
            outcome_prices = data.get("outcomePrices", [])
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
        """Start continuous market scanning"""
        self.running = True
        log.info("Starting Polymarket interface")
        
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
        log.info("Polymarket interface stopped")
