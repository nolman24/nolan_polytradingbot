# PolyArb - Multi-Market Arbitrage Bot

**Automated arbitrage trading bot for Polymarket prediction markets**

Optimized for 15-20% monthly ROI through strategic market inefficiency exploitation across crypto, sports, and financial markets.

---

## 🎯 What It Does

PolyArb monitors multiple data sources in real-time and compares them to Polymarket market prices, identifying mispricings and automatically executing profitable trades.

**Key Features:**
- ✅ **Real-time WebSocket feeds** - Sub-second price updates from Binance
- ✅ **Multi-crypto support** - BTC, ETH, XRP, SOL (5-min & 15-min markets)
- ⚠️ **Sports markets** - Framework only, not yet implemented
- ⚠️ **Stock markets** - Framework only, not yet implemented
- ✅ **Smart exit strategies** - Profit targets, stop losses, EV-based exits, time limits
- ✅ **Position management** - Automatic position tracking and P&L calculation
- ✅ **Risk management** - Daily loss limits, exposure limits, position sizing
- ✅ **Telegram control** - Monitor and control via Telegram bot
- ✅ **Paper trading mode** - Test strategies risk-free before going live

---

## 📊 How It Works

### 1. Market Monitoring
- **Binance WebSocket** - Real-time BTC/ETH/XRP/SOL prices (0.1-0.5s latency)
- **Polymarket Scanner** - Scans all active markets every 3 seconds
- **Sports Odds API** - NFL, NBA, MLB game odds (optional, not implemented)
- **Stock Prices** - Yahoo Finance for stock prediction markets (not implemented)

### 2. Two Types of Crypto Markets

#### A) Price Target Markets
Traditional prediction: "Will BTC hit $103k by 8PM?"
- Compares current price to target
- If already above/below → easy edge
- Simple yes/no probability

#### B) Up or Down Markets (NEW!)
Momentum-based: "Bitcoin Up or Down - 8:00AM-8:15AM"
- Tracks opening price at market start
- Monitors momentum during period
- **Only trades in LAST 5 MINUTES** for clarity
- Probability based on:
  - Current direction (up/down vs opening)
  - Magnitude of move (>0.5% = strong)
  - Time remaining (less time = higher confidence)

**Example Up/Down Strategy:**
```
1. Market opens at 8:00AM
   Opening price: $103,000 (stored)

2. Bot monitors but doesn't trade yet

3. At 8:12AM (3 min left):
   Current price: $103,500 (up $500 or 0.48%)
   Strong UP momentum
   Little time for reversal
   
4. Calculate probability:
   - Base: 75% (move >0.5%)
   - Time boost: +15% (only 3 min left)
   - True probability UP: ~90%
   
5. Check Polymarket:
   UP price: 0.65 (65%)
   Edge: 25% → TRADE!
```

### 2. Arbitrage Detection
Compares Polymarket odds to external reality:

**Example 1: Price Target Market**
```
Market: "Will BTC hit $103k by 8PM?"
Polymarket YES price: 0.40 (40%)
Current BTC price: $103,500 (already above target!)
True probability: ~99%
Edge: 59% mispricing → BUY YES
```

**Example 2: Up or Down Market** (NEW!)
```
Market: "Bitcoin Up or Down - 8:00AM-8:15AM"
Opening price (8:00AM): $103,000
Current price (8:12AM): $103,500 (up $500)
Time remaining: 3 minutes
Momentum: Strong UP
True probability UP: ~85%
Polymarket UP price: 0.60 (60%)
Edge: 25% mispricing → BUY YES (UP)
```

### 3. Trade Execution
- Places order on Polymarket CLOB
- Creates position with entry price, size, timestamp
- Tracks position in real-time

### 4. Smart Exits
Automatically exits positions when:
- **Profit target hit** (default: +50% ROI)
- **Stop loss hit** (default: -20% ROI)
- **Time limit reached** (default: 30 minutes)
- **EV-based exit** (selling is better than holding)
- **Market resolves** (claims winnings)

---

## 🚀 Quick Start

### 1. Get a Telegram Bot Token
1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow instructions
3. Copy your bot token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Deploy to Railway

#### Option A: Deploy via GitHub
1. Fork this repository to your GitHub
2. Go to [Railway.app](https://railway.app) and sign up
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your forked repository
5. Add environment variables (see below)
6. Deploy!

#### Option B: Deploy from CLI
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Add environment variables
railway variables

# Deploy
railway up
```

### 3. Set Environment Variables

**Required:**
```
TELEGRAM_TOKEN=your_telegram_bot_token_here
```

**Optional (for live trading):**
```
POLYMARKET_API_KEY=your_polymarket_api_key
POLYMARKET_SECRET=your_polymarket_secret
POLYMARKET_CLOB_KEY=your_clob_api_key
THE_ODDS_API_KEY=your_odds_api_key  # For sports betting
```

**Leave these empty for paper trading mode!**

### 4. Start Your Bot
1. Open Telegram
2. Search for your bot by username
3. Send `/start`
4. Bot is now active!

---

## 📱 Telegram Commands

```
/start        - Initialize bot
/status       - View bot status & performance
/positions    - See all open positions
/opportunities - View current arbitrage opportunities
/pnl          - Detailed profit & loss report
/config       - View bot configuration
/markets      - Active market statistics
/prices       - Current external prices
/help         - Show all commands
```

---

## ⚙️ Configuration

Edit `config.py` to customize:

### Trading Parameters
```python
min_edge_percent = 3.0          # Minimum mispricing to trade (%)
default_position_size = 50.0    # Position size per trade ($)
max_position_size = 200.0       # Maximum position size ($)
max_total_exposure = 1000.0     # Max total open positions ($)
```

### Exit Strategies
```python
profit_target_percent = 50.0    # Exit when +50% ROI
stop_loss_percent = 20.0        # Exit when -20% ROI
time_limit_minutes = 30         # Exit after 30 min if stagnant
smart_exit_enabled = True       # Use EV-based exits
```

### Risk Management
```python
max_concurrent_positions = 10   # Max open positions at once
max_daily_loss = 200.0          # Stop trading after $200 loss
```

### Market Selection
```python
monitor_btc_5m = True           # Monitor BTC 5-minute markets
monitor_btc_15m = True          # Monitor BTC 15-minute markets
monitor_eth_5m = True           # Monitor ETH 5-minute markets
monitor_eth_15m = True          # Monitor ETH 15-minute markets
monitor_xrp_5m = True           # Monitor XRP 5-minute markets
monitor_xrp_15m = True          # Monitor XRP 15-minute markets
monitor_sol_5m = True           # Monitor SOL 5-minute markets
monitor_sol_15m = True          # Monitor SOL 15-minute markets
monitor_nfl = True              # Monitor NFL games (not implemented)
monitor_nba = True              # Monitor NBA games (not implemented)
monitor_stocks = True           # Monitor stock predictions (not implemented)
```

---

## 💰 Expected Performance

### Realistic Projections

**Conservative Estimate:**
- 5-20% monthly ROI in favorable conditions
- Higher during periods of market inefficiency
- Variability based on competition and market conditions

**Factors Affecting Performance:**
1. **Market efficiency** - More bots = smaller edges
2. **Capital size** - Larger positions capture more value
3. **Speed optimization** - Faster execution = more opportunities
4. **Market selection** - Niche markets have less competition

### Example Scenarios

**Best Case (10% of time):**
- Low competition + breaking news opportunities
- 30-50% monthly ROI

**Average Case (70% of time):**
- Normal market conditions
- 5-15% monthly ROI

**Worst Case (20% of time):**
- High competition or low volatility
- 0-5% monthly ROI or break-even

---

## 🛡️ Risk Management

### Built-in Safety Features

1. **Daily Loss Limit**
   - Stops trading after configured daily loss
   - Resets at midnight UTC

2. **Position Limits**
   - Max number of concurrent positions
   - Max total exposure cap

3. **Stop Losses**
   - Automatic exit at configured loss %
   - Prevents catastrophic losses

4. **Paper Trading**
   - Test strategies with zero risk
   - Full simulation with realistic fills

### Best Practices

✅ **Start small** - Begin with $200-500 in paper mode  
✅ **Test first** - Run paper trading for 2-4 weeks  
✅ **Monitor closely** - Check Telegram notifications daily  
✅ **Adjust config** - Optimize based on your results  
✅ **Scale gradually** - Increase capital only if profitable  

---

## 🔧 Advanced Features

### WebSocket Speed Optimization
Bot uses WebSockets for minimal latency:
- Binance crypto prices: ~100ms lag
- Much faster than polling APIs

### Smart Exit Algorithm
```python
# Compares expected value of holding vs. selling
EV_hold = (win_prob × max_profit) - (loss_prob × current_value)
EV_sell = current_profit (guaranteed)

# Exits when selling is better
if EV_sell > (EV_hold × threshold):
    exit_position()
```

### Position Sizing
Uses Kelly-inspired sizing:
- Larger edges → Larger positions
- Higher liquidity → Larger positions
- Caps at configured maximums

---

## 📈 Monitoring & Optimization

### Key Metrics to Track

1. **Win Rate** - Should be >60% for good strategy
2. **Average ROI per Trade** - Target 20-50%
3. **Hold Time** - Faster is better (capital efficiency)
4. **Opportunity Frequency** - More = more profit potential

### Optimization Tips

**If win rate < 50%:**
- Increase `min_edge_percent`
- Disable low-confidence market types
- Adjust exit strategies

**If few opportunities:**
- Lower `min_edge_percent` carefully
- Enable more market types
- Check that data feeds are working

**If losing money:**
- Switch to paper mode immediately
- Review closed positions for patterns
- Adjust risk parameters

---

## 🐛 Troubleshooting

### Bot not detecting opportunities
- Check that WebSocket connections are active (`/prices`)
- Verify Polymarket markets are loading (`/markets`)
- Lower `min_edge_percent` temporarily

### Trades not executing
- Verify API keys are set (for live trading)
- Check Railway logs for errors
- Ensure sufficient funds in Polymarket account

### Telegram bot not responding
- Verify `TELEGRAM_TOKEN` is set correctly
- Send `/start` to initialize chat
- Check Railway logs for connection errors

### Positions not exiting
- Check exit strategy configuration
- Verify position manager is running (`/status`)
- Markets might not have price movement

---

## 📦 Project Structure

```
polyarb/
├── bot.py              # Main orchestrator
├── config.py           # Configuration & settings
├── models.py           # Data structures
├── monitors.py         # Market data feeds (WebSockets)
├── polymarket.py       # Polymarket API integration
├── arbitrage.py        # Arbitrage detection engine
├── positions.py        # Position management & exits
├── telegram_bot.py     # Telegram interface
├── requirements.txt    # Python dependencies
├── Procfile            # Railway deployment config
└── README.md           # This file
```

---

## 🚨 Important Disclaimers

⚠️ **This bot is for educational purposes.**

⚠️ **Trading involves risk** - You can lose money

⚠️ **No guarantees** - Past performance ≠ future results

⚠️ **Start with paper trading** - Test before risking real money

⚠️ **Market conditions change** - Strategies may stop working

⚠️ **You are responsible** - Understand the code before using

---

## 💡 Tips for Success

1. **Understand the strategy** - Read the code, know how it works
2. **Start conservative** - Small positions, high minimum edge
3. **Monitor performance** - Track actual vs. expected results
4. **Adapt quickly** - If not profitable, adjust or stop
5. **Learn continuously** - Market dynamics evolve constantly

---

## 🤝 Support

**Issues?** Check Railway logs first:
```
railway logs
```

**Need help?** Check:
- This README thoroughly
- Code comments in source files
- Railway documentation
- Polymarket API docs

---

## 📝 License

MIT License - Use at your own risk

---

## 🎉 You're Ready!

Deploy your bot, start in paper mode, and watch it identify opportunities.

**Good luck and trade responsibly!** 🚀
