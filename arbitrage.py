"""
Arbitrage detection engine
Compares Polymarket prices to external data sources and identifies mispricings
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict
import math

from config import TRADING_CONFIG
from models import (
    PolymarketMarket,
    ExternalPrice,
    ArbitrageOpportunity,
    MarketType,
    Side
)

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# PRICE COMPARISON STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════

class CryptoArbitrageDetector:
    """
    Detect arbitrage opportunities in crypto prediction markets
    Compares Polymarket odds to actual exchange prices
    """
    
    def __init__(self):
        # Track opening prices for Up/Down markets
        self.opening_prices: Dict[str, float] = {}
        self.market_start_times: Dict[str, datetime] = {}
    
    def detect(
        self,
        poly_market: PolymarketMarket,
        current_price: float
    ) -> Optional[ArbitrageOpportunity]:
        """
        Detect mispricing in crypto markets
        Handles both price target markets and Up/Down markets
        """
        question = poly_market.question.lower()
        
        # Check if this is an Up/Down market
        if any(kw in question for kw in ["up or down", "up/down", "higher or lower"]):
            return self._detect_updown(poly_market, current_price)
        else:
            return self._detect_price_target(poly_market, current_price)
    
    def _detect_price_target(
        self,
        poly_market: PolymarketMarket,
        current_price: float
    ) -> Optional[ArbitrageOpportunity]:
        """
        Detect mispricing in price target markets
        
        Example: Market asks "Will BTC hit $103k by 8PM?"
        - Current BTC price: $103,500
        - Polymarket YES price: 0.40 (40%)
        - True probability: ~99% (BTC already above $103k)
        - Edge: 59% mispricing!
        """
        try:
            question = poly_market.question.lower()
            
            # Extract target price from question
            target_price = self._extract_target_price(question)
            if not target_price:
                return None
            
            # Determine which side is mispriced
            if current_price > target_price:
                # BTC is already above target - YES should be ~100%
                true_prob = 0.99  # Very high probability
                poly_price = poly_market.yes_price
                side = Side.YES
                
            elif current_price < target_price:
                # BTC is below target - NO should be higher
                # Calculate based on how far below
                distance_pct = ((target_price - current_price) / current_price) * 100
                
                # Use simple model: further away = lower YES probability
                if distance_pct > 5:
                    true_prob = 0.10  # Very unlikely to hit
                elif distance_pct > 2:
                    true_prob = 0.30
                else:
                    true_prob = 0.60
                
                # Check if NO is underpriced
                if poly_market.no_price < (1 - true_prob - 0.1):
                    poly_price = poly_market.no_price
                    side = Side.NO
                    true_prob = 1 - true_prob
                else:
                    # Check if YES is overpriced (bet against it)
                    return None
            else:
                # Price is exactly at target - no clear edge
                return None
            
            # Calculate edge
            edge_percent = ((true_prob - poly_price) / poly_price) * 100
            
            # Check if edge meets minimum
            if edge_percent < TRADING_CONFIG.min_edge_percent:
                return None
            
            # Calculate recommended size
            size = self._calculate_position_size(
                edge_percent,
                poly_market.market_type,
                poly_market.liquidity
            )
            
            # Expected profit
            if side == Side.YES:
                exp_profit = size * (true_prob - poly_price)
            else:
                exp_profit = size * (true_prob - poly_price)
            
            # Time until expiration
            time_remaining = poly_market.end_time - datetime.now(timezone.utc)
            expires_at = datetime.now(timezone.utc) + min(time_remaining, timedelta(seconds=30))
            
            return ArbitrageOpportunity(
                market=poly_market,
                external_price=ExternalPrice(
                    source="binance",
                    symbol="BTC",
                    price=current_price,
                    timestamp=datetime.now(timezone.utc)
                ),
                side=side,
                poly_price=poly_price,
                true_probability=true_prob,
                edge_percent=edge_percent,
                expected_profit=exp_profit,
                recommended_size=size,
                expires_at=expires_at,
                confidence=0.9 if current_price > target_price else 0.7
            )
            
        except Exception as e:
            log.error(f"Crypto arbitrage detection error: {e}")
            return None
    
    def _detect_updown(
        self,
        poly_market: PolymarketMarket,
        current_price: float
    ) -> Optional[ArbitrageOpportunity]:
        """
        Detect mispricing in Up/Down markets with ENHANCED probability model
        
        Uses multiple factors:
        - Price momentum (magnitude and direction)
        - Time remaining (less time = higher confidence)
        - Volatility analysis
        - Recent price action patterns
        """
        try:
            condition_id = poly_market.condition_id
            
            # Parse market timing from question
            start_time, end_time = self._extract_updown_times(poly_market.question)
            if not start_time or not end_time:
                return None
            
            now = datetime.now(timezone.utc)
            
            # Store opening price when market opens
            if condition_id not in self.opening_prices:
                if now >= start_time and now < start_time + timedelta(minutes=1):
                    # Market just opened - store opening price
                    self.opening_prices[condition_id] = current_price
                    self.market_start_times[condition_id] = start_time
                    log.info(f"Stored opening price for {condition_id}: ${current_price:,.2f}")
                return None  # Don't trade at opening
            
            opening_price = self.opening_prices[condition_id]
            
            # Calculate time remaining
            time_remaining = (end_time - now).total_seconds() / 60  # minutes
            total_duration = (end_time - start_time).total_seconds() / 60
            time_elapsed = total_duration - time_remaining
            
            # ENHANCED: Only trade in LAST 5 MINUTES when momentum is clearer
            if time_remaining > 5:
                return None
            
            # Calculate movement metrics
            price_change = current_price - opening_price
            price_change_pct = (price_change / opening_price) * 100
            
            # ENHANCED: Calculate momentum strength
            # Strong moves are more likely to persist
            momentum_strength = abs(price_change_pct)
            
            # Determine direction and calculate probability
            if price_change > 0:
                # Currently UP
                side = Side.YES  # YES = UP
                direction = "UP"
                
                # ENHANCED PROBABILITY MODEL
                # Base probability increases with momentum strength
                if momentum_strength >= 1.5:
                    base_prob = 0.92  # Very strong move
                elif momentum_strength >= 1.0:
                    base_prob = 0.88  # Strong move  
                elif momentum_strength >= 0.5:
                    base_prob = 0.78  # Moderate move
                elif momentum_strength >= 0.3:
                    base_prob = 0.68  # Small but meaningful
                else:
                    base_prob = 0.58  # Barely up
                
                # Time factor: Less time = more confidence it holds
                # At 5 min left: +0%
                # At 3 min left: +8%
                # At 1 min left: +12%
                time_boost = (1 - (time_remaining / 5)) * 0.12
                
                # Duration factor: Longer it's been up, more likely to stay up
                # If up for most of the period, add confidence
                persistence_boost = min((time_elapsed / total_duration) * 0.05, 0.05)
                
                true_prob = base_prob + time_boost + persistence_boost
                true_prob = min(true_prob, 0.96)  # Cap at 96%
                
                poly_price = poly_market.yes_price
                
            else:
                # Currently DOWN
                side = Side.NO  # NO = DOWN (means bet on DOWN)
                direction = "DOWN"
                
                # Same enhanced logic for DOWN
                if momentum_strength >= 1.5:
                    base_prob = 0.92
                elif momentum_strength >= 1.0:
                    base_prob = 0.88
                elif momentum_strength >= 0.5:
                    base_prob = 0.78
                elif momentum_strength >= 0.3:
                    base_prob = 0.68
                else:
                    base_prob = 0.58
                
                time_boost = (1 - (time_remaining / 5)) * 0.12
                persistence_boost = min((time_elapsed / total_duration) * 0.05, 0.05)
                
                true_prob = base_prob + time_boost + persistence_boost
                true_prob = min(true_prob, 0.96)
                
                poly_price = poly_market.no_price
            
            # Calculate edge
            edge_percent = ((true_prob - poly_price) / poly_price) * 100
            
            # Check minimum edge
            if edge_percent < TRADING_CONFIG.min_edge_percent:
                return None
            
            # Calculate position size with enhanced sizing
            # Bigger edges and stronger momentum = larger positions
            size = self._calculate_position_size(
                edge_percent,
                poly_market.market_type,
                poly_market.liquidity
            )
            
            # Increase size for very strong setups
            if momentum_strength >= 1.0 and time_remaining <= 3:
                size *= 1.2  # 20% larger position
                size = min(size, TRADING_CONFIG.max_position_size)
            
            # Expected profit
            exp_profit = size * (true_prob - poly_price)
            
            # Enhanced confidence score
            confidence = 0.6  # Base
            if momentum_strength >= 0.5:
                confidence += 0.1
            if momentum_strength >= 1.0:
                confidence += 0.1
            if time_remaining <= 3:
                confidence += 0.1
            confidence = min(confidence, 0.95)
            
            log.info(
                f"📈 Up/Down: {direction} | "
                f"Move: {price_change_pct:+.3f}% | "
                f"Time left: {time_remaining:.1f}min | "
                f"Prob: {true_prob:.1%} | "
                f"Edge: {edge_percent:.1f}% | "
                f"Confidence: {confidence:.0%}"
            )
            
            return ArbitrageOpportunity(
                market=poly_market,
                external_price=ExternalPrice(
                    source="binance",
                    symbol="crypto",
                    price=current_price,
                    timestamp=datetime.now(timezone.utc),
                    metadata={
                        "opening_price": opening_price,
                        "price_change": price_change,
                        "price_change_pct": price_change_pct,
                        "direction": direction,
                        "momentum_strength": momentum_strength,
                        "time_remaining_min": time_remaining
                    }
                ),
                side=side,
                poly_price=poly_price,
                true_probability=true_prob,
                edge_percent=edge_percent,
                expected_profit=exp_profit,
                recommended_size=size,
                expires_at=end_time,
                confidence=confidence
            )
            
        except Exception as e:
            log.error(f"Up/Down detection error: {e}")
            return None
    
    def _extract_target_price(self, question: str) -> Optional[float]:
        """Extract target price from market question"""
        import re
        
        # Look for patterns like "$103,000", "$103k", "103000"
        patterns = [
            r'\$(\d{1,3}(?:,\d{3})*(?:\.\d+)?)',  # $103,000 or $103,000.50
            r'\$(\d+)k',  # $103k
            r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)',  # 103000
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, question)
            if matches:
                price_str = matches[0].replace(',', '')
                
                # Handle 'k' suffix
                if 'k' in question[question.index(matches[0]):question.index(matches[0])+5]:
                    return float(price_str) * 1000
                
                return float(price_str)
        
        return None
    
    def _extract_updown_times(self, question: str) -> tuple[Optional[datetime], Optional[datetime]]:
        """
        Extract start and end times from Up/Down market question
        
        Example: "Bitcoin Up or Down - February 9, 8:00AM-8:15AM ET"
        Returns: (datetime(8:00AM), datetime(8:15AM))
        """
        import re
        from dateutil import parser
        
        try:
            # Look for time pattern like "8:00AM-8:15AM" or "8:00-8:15"
            time_pattern = r'(\d{1,2}:\d{2}(?:AM|PM)?)\s*[-–]\s*(\d{1,2}:\d{2}(?:AM|PM)?)'
            time_match = re.search(time_pattern, question, re.IGNORECASE)
            
            if not time_match:
                return None, None
            
            start_str = time_match.group(1)
            end_str = time_match.group(2)
            
            # Look for date pattern like "February 9"
            date_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})'
            date_match = re.search(date_pattern, question, re.IGNORECASE)
            
            if date_match:
                month = date_match.group(1)
                day = date_match.group(2)
                year = datetime.now(timezone.utc).year
                date_str = f"{month} {day}, {year}"
            else:
                # Use today's date
                date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
            
            # Parse full datetime strings
            start_dt_str = f"{date_str} {start_str}"
            end_dt_str = f"{date_str} {end_str}"
            
            start_time = parser.parse(start_dt_str)
            end_time = parser.parse(end_dt_str)
            
            # Convert to UTC (assuming ET timezone mentioned)
            # ET is UTC-5 or UTC-4 depending on DST
            # For simplicity, using UTC-5
            from datetime import timezone as tz
            start_time = start_time.replace(tzinfo=tz(timedelta(hours=-5)))
            end_time = end_time.replace(tzinfo=tz(timedelta(hours=-5)))
            
            start_time = start_time.astimezone(timezone.utc)
            end_time = end_time.astimezone(timezone.utc)
            
            return start_time, end_time
            
        except Exception as e:
            log.error(f"Error parsing Up/Down times: {e}")
            return None, None
    
    def _calculate_position_size(
        self,
        edge_percent: float,
        market_type: MarketType,
        liquidity: float
    ) -> float:
        """Calculate optimal position size based on edge and market conditions"""
        base_size = TRADING_CONFIG.default_position_size
        
        # Apply market type multiplier
        multiplier = TRADING_CONFIG.market_size_multipliers.get(
            market_type.value,
            1.0
        )
        
        # Scale up for larger edges (Kelly-inspired)
        if edge_percent > 10:
            multiplier *= 1.5
        elif edge_percent > 20:
            multiplier *= 2.0
        
        # Scale down for low liquidity
        if liquidity < 1000:
            multiplier *= 0.5
        
        size = base_size * multiplier
        
        # Apply limits
        size = min(size, TRADING_CONFIG.max_position_size)
        size = max(size, 10)  # Minimum $10
        
        return size

class SportsArbitrageDetector:
    """Detect arbitrage in sports markets (TODO: implement)"""
    
    def detect(
        self,
        poly_market: PolymarketMarket,
        external_odds: dict
    ) -> Optional[ArbitrageOpportunity]:
        # Placeholder for sports arbitrage
        log.debug("Sports arbitrage detection (not implemented)")
        return None

class StocksArbitrageDetector:
    """Detect arbitrage in stock prediction markets (TODO: implement)"""
    
    def detect(
        self,
        poly_market: PolymarketMarket,
        stock_price: float
    ) -> Optional[ArbitrageOpportunity]:
        # Placeholder for stock arbitrage
        log.debug("Stock arbitrage detection (not implemented)")
        return None

# ═══════════════════════════════════════════════════════════════════════════
# UNIFIED ARBITRAGE ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class ArbitrageEngine:
    """
    Main arbitrage detection system
    Coordinates all detectors and ranks opportunities
    """
    
    def __init__(self):
        self.crypto_detector = CryptoArbitrageDetector()
        self.sports_detector = SportsArbitrageDetector()
        self.stocks_detector = StocksArbitrageDetector()
        
        self.detected_opportunities: List[ArbitrageOpportunity] = []
    
    def analyze_crypto_market(
        self,
        market: PolymarketMarket,
        current_price: float
    ) -> Optional[ArbitrageOpportunity]:
        """Analyze a crypto market for arbitrage"""
        return self.crypto_detector.detect(market, current_price)
    
    def analyze_sports_market(
        self,
        market: PolymarketMarket,
        external_odds: dict
    ) -> Optional[ArbitrageOpportunity]:
        """Analyze a sports market for arbitrage"""
        return self.sports_detector.detect(market, external_odds)
    
    def analyze_stock_market(
        self,
        market: PolymarketMarket,
        stock_price: float
    ) -> Optional[ArbitrageOpportunity]:
        """Analyze a stock market for arbitrage"""
        return self.stocks_detector.detect(market, stock_price)
    
    def rank_opportunities(
        self,
        opportunities: List[ArbitrageOpportunity]
    ) -> List[ArbitrageOpportunity]:
        """
        Rank opportunities by quality
        Higher edge + higher confidence = better opportunity
        """
        def score(opp: ArbitrageOpportunity) -> float:
            # Score = edge * confidence * size potential
            return opp.edge_percent * opp.confidence * math.log(opp.recommended_size + 1)
        
        return sorted(opportunities, key=score, reverse=True)
    
    def add_opportunity(self, opp: ArbitrageOpportunity):
        """Add opportunity to tracking list"""
        # Remove expired opportunities
        now = datetime.now(timezone.utc)
        self.detected_opportunities = [
            o for o in self.detected_opportunities
            if o.expires_at > now
        ]
        
        # Add new opportunity
        self.detected_opportunities.append(opp)
    
    def get_best_opportunities(self, count: int = 5) -> List[ArbitrageOpportunity]:
        """Get top N opportunities"""
        ranked = self.rank_opportunities(self.detected_opportunities)
        return ranked[:count]
    
    def clear_expired(self):
        """Remove expired opportunities"""
        now = datetime.now(timezone.utc)
        before = len(self.detected_opportunities)
        self.detected_opportunities = [
            o for o in self.detected_opportunities
            if o.expires_at > now
        ]
        after = len(self.detected_opportunities)
        if before != after:
            log.debug(f"Cleared {before - after} expired opportunities")
