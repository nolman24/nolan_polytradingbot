"""
Telegram bot interface for monitoring and control
"""

import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import TELEGRAM_TOKEN, TRADING_CONFIG, MARKET_CONFIG, get_config_summary

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM NOTIFIER
# ═══════════════════════════════════════════════════════════════════════════

class TelegramNotifier:
    """Sends notifications to Telegram"""
    
    def __init__(self, app: Application):
        self.app = app
        self.chat_id = None
    
    def set_chat_id(self, chat_id: int):
        """Set the chat ID to send messages to"""
        self.chat_id = chat_id
    
    async def send_message(self, text: str):
        """Send a message"""
        if not self.chat_id:
            log.warning("No chat ID set, cannot send message")
            return
        
        try:
            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="Markdown"
            )
        except Exception as e:
            log.error(f"Telegram send error: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM BOT COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

class TelegramBot:
    """Telegram bot for control and monitoring"""
    
    def __init__(
        self,
        position_manager,
        arbitrage_engine,
        market_feed,
        polymarket_interface
    ):
        self.positions = position_manager
        self.arbitrage = arbitrage_engine
        self.market_feed = market_feed
        self.poly = polymarket_interface
        
        self.app = None
        self.notifier = None
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        chat_id = update.effective_chat.id
        
        # Store chat ID for notifications
        if self.notifier:
            self.notifier.set_chat_id(chat_id)
        
        welcome_msg = (
            "🤖 *PolyArb Bot Active*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Multi-market arbitrage bot for Polymarket\n\n"
            "*Commands:*\n"
            "/status - Bot status & performance\n"
            "/positions - View open positions\n"
            "/opportunities - Current arbitrage opportunities\n"
            "/config - View configuration\n"
            "/pnl - Profit & loss report\n"
            "/markets - Active markets\n"
            "/prices - Current external prices\n"
            "/help - Show all commands\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(welcome_msg, parse_mode="Markdown")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show bot status"""
        summary = self.positions.get_position_summary()
        
        # Get current prices
        btc_price = self.market_feed.get_btc_price()
        eth_price = self.market_feed.get_eth_price()
        xrp_price = self.market_feed.get_xrp_price()
        sol_price = self.market_feed.get_sol_price()
        
        price_lines = "━━━━━━━━━━━━━━━━\n"
        if btc_price:
            price_lines += f"💵 BTC: ${btc_price:,.2f}\n"
        if eth_price:
            price_lines += f"💵 ETH: ${eth_price:,.2f}\n"
        if xrp_price:
            price_lines += f"💵 XRP: ${xrp_price:.4f}\n"
        if sol_price:
            price_lines += f"💵 SOL: ${sol_price:,.2f}\n"
        
        msg = (
            "📊 *Bot Status*\n"
            "━━━━━━━━━━━━━━━━\n"
            f"💼 Open positions: {summary['open_positions']}\n"
            f"💰 Total exposure: {summary['total_exposure']}\n"
            f"🏆 Win rate: {summary['metrics']['win_rate']}\n"
            f"📈 Total P&L: {summary['metrics']['total_pnl']}\n"
            f"📅 Today P&L: {summary['metrics']['daily_pnl']}\n"
            f"🔄 Today trades: {summary['metrics']['daily_trades']}\n"
            f"{price_lines}"
        )
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show open positions"""
        if not self.positions.open_positions:
            await update.message.reply_text("No open positions")
            return
        
        msg = "*Open Positions*\n━━━━━━━━━━━━━━━━\n"
        
        for pos in list(self.positions.open_positions.values())[:10]:
            msg += (
                f"\n📋 {pos.market.question[:40]}...\n"
                f"🎯 {pos.side.value} · {pos.shares:.2f} @ {pos.entry_price:.4f}\n"
                f"💰 P&L: ${pos.unrealized_pnl:+.2f} ({pos.calculate_roi():+.1f}%)\n"
                f"Current: {pos.current_price:.4f}\n"
            )
        
        if len(self.positions.open_positions) > 10:
            msg += f"\n... and {len(self.positions.open_positions) - 10} more"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def opportunities_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current arbitrage opportunities"""
        opps = self.arbitrage.get_best_opportunities(count=5)
        
        if not opps:
            await update.message.reply_text("No opportunities detected")
            return
        
        msg = "💎 *Top Opportunities*\n━━━━━━━━━━━━━━━━\n"
        
        for i, opp in enumerate(opps, 1):
            msg += (
                f"\n*{i}. {opp.market.question[:35]}...*\n"
                f"🎯 {opp.side.value} @ {opp.poly_price:.4f}\n"
                f"📊 True prob: {opp.true_probability:.2%}\n"
                f"⚡ Edge: *{opp.edge_percent:.1f}%*\n"
                f"💵 Size: ${opp.recommended_size:.0f}\n"
                f"🎓 Confidence: {opp.confidence:.0%}\n"
            )
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show configuration"""
        msg = get_config_summary()
        await update.message.reply_text(f"```\n{msg}\n```", parse_mode="Markdown")
    
    async def pnl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show P&L report"""
        metrics = self.positions.metrics
        
        msg = (
            "💰 *Profit & Loss Report*\n"
            "━━━━━━━━━━━━━━━━\n"
            f"Total trades: {metrics.total_trades}\n"
            f"Wins: {metrics.winning_trades} ✅\n"
            f"Losses: {metrics.losing_trades} ❌\n"
            f"Win rate: {metrics.get_win_rate():.1f}%\n"
            "━━━━━━━━━━━━━━━━\n"
            f"Total P&L: ${metrics.total_pnl:.2f}\n"
            f"ROI: {metrics.get_roi():.1f}%\n"
            f"Largest win: ${metrics.largest_win:.2f}\n"
            f"Largest loss: ${metrics.largest_loss:.2f}\n"
            "━━━━━━━━━━━━━━━━\n"
            f"Today P&L: ${metrics.daily_pnl:.2f}\n"
            f"Today trades: {metrics.daily_trades}"
        )
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def markets_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show active markets"""
        markets = await self.poly.get_markets()
        
        if not markets:
            await update.message.reply_text("No markets loaded")
            return
        
        # Group by type
        by_type = {}
        for m in markets:
            t = m.market_type.value
            by_type[t] = by_type.get(t, 0) + 1
        
        # Build message without markdown to avoid parsing errors
        msg = "🏪 Active Markets\n"
        msg += "━━━━━━━━━━━━━━━━\n"
        for market_type, count in sorted(by_type.items()):
            # Escape special characters that could break parsing
            safe_type = market_type.replace("_", " ").replace("*", "").replace("[", "").replace("]", "")
            msg += f"{safe_type}: {count}\n"
        
        msg += f"\nTotal: {len(markets)} markets"
        
        # Send without markdown parsing to avoid errors
        await update.message.reply_text(msg)
    
    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed list of actual markets being scanned"""
        markets = await self.poly.get_markets()
        
        if not markets:
            await update.message.reply_text("No markets loaded")
            return
        
        # Group by type
        by_type = {}
        for m in markets:
            t = m.market_type.value
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(m.question)
        
        # Build message
        msg = "📋 Detailed Market List\n"
        msg += "━━━━━━━━━━━━━━━━\n\n"
        
        for market_type in sorted(by_type.keys()):
            questions = by_type[market_type]
            safe_type = market_type.replace("_", " ").title()
            msg += f"📊 {safe_type} ({len(questions)})\n"
            
            # Show first 3 markets of each type
            for i, q in enumerate(questions[:3]):
                # Truncate long questions
                short_q = q[:60] + "..." if len(q) > 60 else q
                msg += f"  • {short_q}\n"
            
            if len(questions) > 3:
                msg += f"  ... and {len(questions) - 3} more\n"
            
            msg += "\n"
        
        msg += f"Total: {len(markets)} markets"
        
        # Split into multiple messages if too long
        if len(msg) > 4000:
            # Send first part
            await update.message.reply_text(msg[:4000])
            # Send remainder
            await update.message.reply_text(msg[4000:])
        else:
            await update.message.reply_text(msg)
    
    async def prices_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current external prices"""
        btc = self.market_feed.get_btc_price()
        eth = self.market_feed.get_eth_price()
        xrp = self.market_feed.get_xrp_price()
        sol = self.market_feed.get_sol_price()
        
        msg = "💵 *Current Prices*\n━━━━━━━━━━━━━━━━\n"
        
        if btc:
            msg += f"BTC: ${btc:,.2f}\n"
        if eth:
            msg += f"ETH: ${eth:,.2f}\n"
        if xrp:
            msg += f"XRP: ${xrp:.4f}\n"
        if sol:
            msg += f"SOL: ${sol:,.2f}\n"
        
        if not any([btc, eth, xrp, sol]):
            msg += "No price data available"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help"""
        msg = (
            "📖 *PolyArb Commands*\n"
            "━━━━━━━━━━━━━━━━\n"
            "/status - Bot status & metrics\n"
            "/positions - View open positions\n"
            "/opportunities - Current arbitrage opps\n"
            "/config - View bot configuration\n"
            "/pnl - Detailed P&L report\n"
            "/markets - Market count by type\n"
            "/list - Detailed list of actual markets\n"
            "/prices - External price data\n"
            "/help - This help message"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def setup(self) -> Application:
        """Setup Telegram bot"""
        if not TELEGRAM_TOKEN:
            log.error("No Telegram token provided")
            return None
        
        # Create application
        self.app = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Create notifier
        self.notifier = TelegramNotifier(self.app)
        
        # Set position manager's telegram reference
        if self.positions:
            self.positions.telegram = self.notifier
        
        # Register command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("positions", self.positions_command))
        self.app.add_handler(CommandHandler("opportunities", self.opportunities_command))
        self.app.add_handler(CommandHandler("config", self.config_command))
        self.app.add_handler(CommandHandler("pnl", self.pnl_command))
        self.app.add_handler(CommandHandler("markets", self.markets_command))
        self.app.add_handler(CommandHandler("list", self.list_command))
        self.app.add_handler(CommandHandler("prices", self.prices_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        
        log.info("Telegram bot configured")
        return self.app
    
    def get_notifier(self) -> TelegramNotifier:
        """Get notifier for sending messages"""
        return self.notifier
