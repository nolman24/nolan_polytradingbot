# PolyArb - Quick Setup Guide

## 🚀 Get Started in 5 Minutes

### Step 1: Get Your Telegram Bot Token (2 min)
1. Open Telegram
2. Search for `@BotFather`
3. Send: `/newbot`
4. Choose a name: `MyPolyArbBot`
5. Choose a username: `mypolyarb_bot`
6. **Copy the token** (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Upload to GitHub (1 min)
1. Create new repository on GitHub (can be private)
2. Upload all files from the `polyarb` folder
3. Commit

### Step 3: Deploy to Railway (2 min)
1. Go to https://railway.app (sign up if needed)
2. Click **"New Project"**
3. Click **"Deploy from GitHub repo"**
4. Select your polyarb repository
5. Click **"Add variables"**
6. Add: `TELEGRAM_TOKEN` = your_token_from_step_1
7. Click **"Deploy"**

### Step 4: Start Using! (30 sec)
1. Open Telegram
2. Search for your bot username
3. Send: `/start`
4. Done! Bot is running in paper trading mode

---

## 📱 First Commands to Try

```
/status        ← See if bot is working
/opportunities ← View detected arbitrage opps
/config        ← Check your settings
/help          ← All available commands
```

---

## ⚙️ Configuration (Optional)

Edit `config.py` if you want to change:
- Position sizes ($50 default)
- Minimum edge (3% default)
- Exit strategies (profit target, stop loss)
- Which markets to monitor

---

## 💰 Going Live (When Ready)

**⚠️ Only after 2-4 weeks of successful paper trading!**

1. Get Polymarket API credentials:
   - Go to Polymarket settings
   - Generate API key
   
2. Add to Railway environment variables:
   - `POLYMARKET_API_KEY`
   - `POLYMARKET_SECRET`
   - `POLYMARKET_CLOB_KEY`

3. In `config.py`, change:
   ```python
   PAPER_TRADING = False
   ```

4. Redeploy

---

## 📊 Monitoring Performance

**Daily:** Check `/pnl` in Telegram
**Weekly:** Review win rate and average ROI
**Monthly:** Decide if strategy is profitable

Target metrics:
- Win rate: >60%
- Monthly ROI: 10-20%
- Average hold time: <30 minutes

---

## 🆘 Troubleshooting

**Bot not responding?**
- Check Railway logs: `railway logs`
- Verify TELEGRAM_TOKEN is set correctly
- Send `/start` to initialize

**No opportunities detected?**
- Check `/prices` - are price feeds working?
- Check `/markets` - are markets loading?
- Lower `min_edge_percent` in config

**Questions?**
- Read the full README.md
- Check inline code comments
- Review Railway error logs

---

## ✅ Success Checklist

- [ ] Telegram bot responding to `/start`
- [ ] `/status` shows bot metrics
- [ ] `/opportunities` shows some opportunities (even if small edge)
- [ ] `/prices` shows current BTC/ETH prices
- [ ] Paper trading for at least 2 weeks
- [ ] Win rate above 50%
- [ ] Monthly ROI above 10%
- [ ] Understand the code and strategy

**Only then consider live trading!**

---

Good luck! 🚀
