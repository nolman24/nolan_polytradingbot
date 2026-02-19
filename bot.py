"""
PolyArb - Multi-Market Arbitrage Bot
Main orchestrator that coordinates all systems
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone

from config import (
    TRADING_CONFIG,
    MARKET_CONFIG,
    POLYMARKET_API_KEY,
    POLYMARKET_SECRET,
    THE_ODDS_API_KEY,
    PAPER_TRADING,
    LOG_LEVEL,
    validate_config
)
from models import Position, Side, MarketType
from monitors import MarketDataFeed
from polymarket import PolymarketInterface
from arbitrage import ArbitrageEngine
from positions import PositionManager
from telegram_bot import TelegramBot

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('polyarb.log')
    ]
)
log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# MAIN BOT ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

class PolyArbBot:
    """
    Main arbitrage bot orchestrator
    Coordinates all subsystems and executes trading logic
    """
    
    def __init__(self):
        # Initialize all systems
        log.info("Initializing PolyArb Bot...")
        
        self.market_feed = MarketDataFeed(THE_ODDS_API_KEY)
        self.poly = PolymarketInterface(POLYMARKET_API_KEY, POLYMARKET_SECRET)
        self.arbitrage = ArbitrageEngine()
        self.positions = PositionManager(self.poly)
        self.telegram = TelegramBot(
            self.positions,
            self.arbitrage,
            self.market_feed,
            self.poly
        )
        
        self.running = False
        self.telegram_app = None
    
    async def start(self):
        """Start the bot"""
        log.info("="*60)
        log.info("PolyArb - Multi-Market Arbitrage Bot")
        log.info("="*60)
        
        # Validate configuration
        issues = validate_config()
        if issues:
            log.warning("Configuration issues detected:")
            for issue in issues:
                log.warning(f"  {issue}")
        
        # Show configuration
        log.info(f"Mode: {'📄 PAPER TRADING' if PAPER_TRADING else '💰 LIVE TRADING'}")
        log.info(f"Min edge: {TRADING_CONFIG.min_edge_percent}%")
        log.info(f"Position size: ${TRADING_CONFIG.default_position_size}")
        log.info(f"Max exposure: ${TRADING_CONFIG.max_total_exposure}")
        
        self.running = True
        
        # Setup and initialize Telegram bot
        self.telegram_app = await self.telegram.setup()
        
        if self.telegram_app:
            await self.telegram_app.initialize()
            await self.telegram_app.start()
            self.telegram_app.updater.start_polling()
        
        # Start all subsystems concurrently
        tasks = [
            self.market_feed.start(),
            self.poly.start(),
            self.positions.monitor_positions(),
            self._trading_loop(),
        ]
        
        log.info("🚀 All systems online - bot is running!")
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            log.info("Shutdown signal received")
            await self.stop()
    
    async def _trading_loop(self):
        """Main trading loop - scans for opportunities and executes"""
        log.info("Trading loop started")
        
        while self.running:
            try:
                # Get all markets
                markets = await self.poly.get_markets()
                
                # Scan crypto markets
                if MARKET_CONFIG.monitor_btc_5m or MARKET_CONFIG.monitor_btc_15m:
                    await self._scan_crypto_markets(markets)
                
                # Scan sports markets
                if MARKET_CONFIG.monitor_nfl or MARKET_CONFIG.monitor_nba:
                    await self._scan_sports_markets(markets)
                
                # Scan stock markets
                if MARKET_CONFIG.monitor_stocks:
                    await self._scan_stock_markets(markets)
                
                # Clean expired opportunities
                self.arbitrage.clear_expired()
                
                # Wait before next scan
                await asyncio.sleep(3)
                
            except Exception as e:
                log.error(f"Trading loop error: {e}")
                await asyncio.sleep(10)
    
    async def _scan_crypto_markets(self, markets: list):
        """Scan crypto markets for arbitrage"""
        btc_price = self.market_feed.get_btc_price()
        eth_price = self.market_feed.get_eth_price()
        xrp_price = self.market_feed.get_xrp_price()
        sol_price = self.market_feed.get_sol_price()
        
        for market in markets:
            # Check all crypto market types including Up/Down
            if market.market_type not in [
                MarketType.CRYPTO_5M,
                MarketType.CRYPTO_15M,
                MarketType.CRYPTO_1H,
                MarketType.CRYPTO_UPDOWN  # NEW!
            ]:
                continue
            
            # Check if it's BTC, ETH, XRP, or SOL
            q_lower = market.question.lower()
            price = None
            
            if "btc" in q_lower or "bitcoin" in q_lower:
                price = btc_price
            elif "eth" in q_lower or "ethereum" in q_lower:
                price = eth_price
            elif "xrp" in q_lower or "ripple" in q_lower:
                price = xrp_price
            elif "sol" in q_lower or "solana" in q_lower:
                price = sol_price
            
            if not price:
                continue
            
            # Analyze for arbitrage
            opp = self.arbitrage.analyze_crypto_market(market, price)
            
            if opp:
                self.arbitrage.add_opportunity(opp)
                await self._consider_trade(opp)
    
    async def _scan_sports_markets(self, markets: list):
        """Scan sports markets for arbitrage"""
        # TODO: Implement sports arbitrage scanning
        pass
    
    async def _scan_stock_markets(self, markets: list):
        """Scan stock markets for arbitrage"""
        # TODO: Implement stock arbitrage scanning
        pass
    
    async def _consider_trade(self, opp):
        """Consider executing a trade"""
        # Check if we can open new position
        if not self.positions.can_open_position(opp.recommended_size):
            log.debug(f"Cannot open position - limits reached")
            return
        
        # Log opportunity
        log.info(
            f"🎯 Opportunity: {opp.side.value} on {opp.market.question[:40]} | "
            f"Edge: {opp.edge_percent:.1f}% | Size: ${opp.recommended_size:.0f}"
        )
        
        # Send Telegram notification
        if self.telegram and self.telegram.get_notifier():
            msg = (
                f"💎 *Arbitrage Opportunity*\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"📋 `{opp.market.question[:50]}`\n"
                f"🎯 {opp.side.value} @ {opp.poly_price:.4f}\n"
                f"⚡ Edge: *{opp.edge_percent:.1f}%*\n"
                f"💵 Size: ${opp.recommended_size:.0f}\n"
                f"📊 Confidence: {opp.confidence:.0%}\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"_Auto-executing..._"
            )
            await self.telegram.get_notifier().send_message(msg)
        
        # Execute trade
        await self._execute_trade(opp)
    
    async def _execute_trade(self, opp):
        """Execute a trade"""
        try:
            # Place order via Polymarket
            order_id = await self.poly.execute_trade(
                opp.market,
                opp.side,
                opp.recommended_size
            )
            
            if not order_id:
                log.error("Trade execution failed")
                return
            
            # Create position
            shares = opp.recommended_size / opp.poly_price
            position = Position(
                position_id=order_id,
                market=opp.market,
                side=opp.side,
                entry_price=opp.poly_price,
                shares=shares,
                cost_basis=opp.recommended_size,
                entry_time=datetime.now(timezone.utc),
                entry_reason=f"Edge: {opp.edge_percent:.1f}%",
                market_type=opp.market.market_type,
            )
            
            # Initialize current price
            position.update_current_price(opp.poly_price)
            
            # Add to position manager
            self.positions.add_position(position)
            
            log.info(f"✅ Trade executed: {order_id}")
            
            # Send success notification
            if self.telegram and self.telegram.get_notifier():
                msg = (
                    f"✅ *Trade Executed*\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"📋 `{opp.market.question[:50]}`\n"
                    f"🎯 {opp.side.value} · {shares:.2f} shares @ ${opp.poly_price:.4f}\n"
                    f"💰 Cost: ${opp.recommended_size:.2f}\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"Position ID: `{order_id}`"
                )
                await self.telegram.get_notifier().send_message(msg)
            
        except Exception as e:
            log.error(f"Trade execution error: {e}")
    
    async def stop(self):
        """Stop the bot"""
        log.info("Stopping PolyArb Bot...")
        self.running = False
        
        # Stop Telegram bot first
        if self.telegram_app:
            self.telegram_app.updater.stop()
            await self.telegram_app.stop()
            await self.telegram_app.shutdown()
        
        await asyncio.gather(
            self.market_feed.stop(),
            self.poly.stop(),
            self.positions.stop(),
        )
        
        log.info("Bot stopped")

# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    """Main entry point"""
    bot = PolyArbBot()
    await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutdown complete")
