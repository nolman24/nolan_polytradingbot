"""
Position management system with intelligent exit strategies
"""

import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict
import uuid

from config import TRADING_CONFIG, STATE_FILE, POSITIONS_FILE
from models import (
    Position,
    PositionStatus,
    ExitReason,
    PolymarketMarket,
    Side,
    PerformanceMetrics
)

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# POSITION MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class PositionManager:
    """
    Manages all open positions and executes exit strategies
    """
    
    def __init__(self, polymarket_interface, telegram_notifier=None):
        self.poly = polymarket_interface
        self.telegram = telegram_notifier
        
        self.open_positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        self.metrics = PerformanceMetrics()
        
        self.running = False
        self.daily_loss = 0.0
        self.last_daily_reset = datetime.now(timezone.utc)
        
        # Load state if exists
        self._load_state()
    
    def add_position(self, position: Position):
        """Add new position to tracking"""
        self.open_positions[position.position_id] = position
        self.metrics.total_invested += position.cost_basis
        
        log.info(f"📍 Opened position: {position.position_id} - {position.side.value} on {position.market.question[:50]}")
        self._save_state()
    
    async def monitor_positions(self):
        """Continuously monitor and manage positions"""
        self.running = True
        log.info("Starting position monitor")
        
        while self.running:
            try:
                await self._check_all_positions()
                await self._check_daily_limits()
                await asyncio.sleep(2)  # Check every 2 seconds
            except Exception as e:
                log.error(f"Position monitor error: {e}")
                await asyncio.sleep(10)
    
    async def _check_all_positions(self):
        """Check all open positions for exit conditions"""
        for position in list(self.open_positions.values()):
            try:
                # Update current price
                market = self.poly.get_market(position.market.condition_id)
                if market:
                    current_price = market.get_price(position.side)
                    position.update_current_price(current_price)
                
                # Check exit conditions
                should_exit, reason = await self._should_exit_position(position)
                
                if should_exit:
                    await self._exit_position(position, reason)
                    
            except Exception as e:
                log.error(f"Error checking position {position.position_id}: {e}")
    
    async def _should_exit_position(self, position: Position) -> tuple[bool, Optional[ExitReason]]:
        """
        Determine if position should be exited
        Returns (should_exit, reason)
        """
        
        # 1. Check profit target
        if TRADING_CONFIG.profit_target_percent > 0:
            if position.should_exit_profit_target(TRADING_CONFIG.profit_target_percent):
                return (True, ExitReason.PROFIT_TARGET)
        
        # 2. Check stop loss
        if TRADING_CONFIG.stop_loss_percent > 0:
            if position.should_exit_stop_loss(TRADING_CONFIG.stop_loss_percent):
                return (True, ExitReason.STOP_LOSS)
        
        # 3. Check time limit
        if TRADING_CONFIG.time_limit_minutes > 0:
            if position.should_exit_time_limit(TRADING_CONFIG.time_limit_minutes):
                return (True, ExitReason.TIME_LIMIT)
        
        # 4. Smart exit (EV-based)
        if TRADING_CONFIG.smart_exit_enabled:
            ev_hold = position.calculate_ev_hold()
            ev_sell = position.calculate_ev_sell()
            
            threshold = TRADING_CONFIG.smart_exit_threshold
            if ev_sell > (ev_hold * threshold):
                log.info(f"Smart exit triggered: EV_sell (${ev_sell:.2f}) > EV_hold (${ev_hold:.2f})")
                return (True, ExitReason.SMART_EXIT)
        
        # 5. Check if market has resolved
        market = self.poly.get_market(position.market.condition_id)
        if market and market.end_time < datetime.now(timezone.utc):
            # Market expired - should be resolved
            return (True, ExitReason.RESOLVED)
        
        return (False, None)
    
    async def _exit_position(self, position: Position, reason: ExitReason):
        """Exit a position"""
        try:
            log.info(f"🚪 Exiting position {position.position_id}: {reason.value}")
            
            # Execute sell order (or simulate in paper mode)
            sell_price = position.current_price
            
            # Calculate realized P&L
            position.exit_time = datetime.now(timezone.utc)
            position.exit_price = sell_price
            position.exit_reason = reason
            position.realized_pnl = position.unrealized_pnl
            
            # Update status
            if position.realized_pnl > 0:
                position.status = PositionStatus.CLOSED_WIN
            elif position.realized_pnl < 0:
                position.status = PositionStatus.CLOSED_LOSS
            else:
                position.status = PositionStatus.CLOSED_BREAK_EVEN
            
            # Move to closed positions
            self.open_positions.pop(position.position_id)
            self.closed_positions.append(position)
            
            # Update metrics
            self.metrics.add_closed_position(position)
            
            # Update daily loss tracking
            if position.realized_pnl < 0:
                self.daily_loss += abs(position.realized_pnl)
            
            # Notify via Telegram
            if self.telegram:
                await self._send_exit_notification(position)
            
            self._save_state()
            
            log.info(f"✅ Position closed: {position.position_id} - "
                    f"P&L: ${position.realized_pnl:.2f} ({position.calculate_roi():.1f}%)")
            
        except Exception as e:
            log.error(f"Error exiting position: {e}")
    
    async def _send_exit_notification(self, position: Position):
        """Send Telegram notification about position exit"""
        emoji = "✅" if position.realized_pnl > 0 else "❌"
        
        message = (
            f"{emoji} *Position Closed*\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📋 `{position.market.question[:50]}`\n"
            f"🎯 {position.side.value} · {position.shares:.2f} shares\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📍 Entry: `{position.entry_price:.4f}` → Exit: `{position.exit_price:.4f}`\n"
            f"💰 P&L: `${position.realized_pnl:.2f}` ({position.calculate_roi():+.1f}%)\n"
            f"🚪 Reason: _{position.exit_reason.value.replace('_', ' ')}_\n"
            f"⏱ Hold time: {self._format_hold_time(position)}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📊 Today: ${self.metrics.daily_pnl:.2f} · "
            f"Total: ${self.metrics.total_pnl:.2f}"
        )
        
        try:
            await self.telegram.send_message(message)
        except:
            pass
    
    def _format_hold_time(self, position: Position) -> str:
        """Format hold time for display"""
        if not position.exit_time:
            return "N/A"
        
        duration = position.exit_time - position.entry_time
        minutes = duration.seconds // 60
        seconds = duration.seconds % 60
        
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"
    
    async def _check_daily_limits(self):
        """Check if daily loss limit reached"""
        now = datetime.now(timezone.utc)
        
        # Reset daily tracking if new day
        if (now - self.last_daily_reset).days >= 1:
            self.daily_loss = 0.0
            self.last_daily_reset = now
            self.metrics.reset_daily_stats()
            log.info("Daily stats reset")
        
        # Check daily loss limit
        if self.daily_loss >= TRADING_CONFIG.max_daily_loss:
            log.warning(f"⚠️ Daily loss limit reached: ${self.daily_loss:.2f}")
            # Could implement auto-pause here
    
    def get_total_exposure(self) -> float:
        """Calculate total USD value of open positions"""
        return sum(pos.current_value for pos in self.open_positions.values())
    
    def can_open_position(self, size: float) -> bool:
        """Check if we can open a new position"""
        # Check position count limit
        if len(self.open_positions) >= TRADING_CONFIG.max_concurrent_positions:
            return False
        
        # Check exposure limit
        if self.get_total_exposure() + size > TRADING_CONFIG.max_total_exposure:
            return False
        
        # Check daily loss limit
        if self.daily_loss >= TRADING_CONFIG.max_daily_loss:
            return False
        
        return True
    
    def get_position_summary(self) -> Dict:
        """Get summary of all positions"""
        return {
            "open_positions": len(self.open_positions),
            "total_exposure": f"${self.get_total_exposure():.2f}",
            "closed_positions": len(self.closed_positions),
            "metrics": self.metrics.to_dict(),
        }
    
    def _save_state(self):
        """Save positions to disk"""
        try:
            state = {
                "open_positions": [p.to_dict() for p in self.open_positions.values()],
                "closed_positions": [p.to_dict() for p in self.closed_positions],
                "metrics": self.metrics.to_dict(),
                "daily_loss": self.daily_loss,
            }
            
            with open(POSITIONS_FILE, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            log.error(f"Error saving state: {e}")
    
    def _load_state(self):
        """Load positions from disk"""
        try:
            with open(POSITIONS_FILE, 'r') as f:
                state = json.load(f)
                
            # TODO: Reconstruct Position objects from saved data
            # For now, start fresh
            log.info("State loaded (reconstruction not implemented)")
            
        except FileNotFoundError:
            log.info("No saved state found, starting fresh")
        except Exception as e:
            log.error(f"Error loading state: {e}")
    
    async def stop(self):
        """Stop position manager"""
        self.running = False
        self._save_state()
        log.info("Position manager stopped")
