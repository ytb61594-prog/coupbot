# 🎴 Coup Discord Bot

A fully-featured Discord bot for playing the card game **Coup** with your friends! Built with modern Discord.py features including buttons, slash commands, and ephemeral messages.

## ✨ Features

- 🎮 **Full Coup Game Implementation** - Complete rules with all 5 roles and actions
- 🏆 **Server Leaderboards** - Track wins, losses, and win rates per server
- 🎯 **Modern Button UI** - Beautiful button-based interface (no reactions needed!)
- 🔒 **Perfect Card Privacy** - Cards sent via DM with Card A/B selection system
- 💎 **Beautiful Embeds** - Color-coded embeds with card emojis (👑 🗡️ 🤝 ⚓ 🛡️)
- 📊 **Statistics Tracking** - Persistent JSON-based leaderboard storage
- ⚡ **Fast & Responsive** - Interactive gameplay with instant button responses
- 🎲 **Bluffing Mechanics** - Full challenge and block system with proper validation

## 🎮 Commands

### Text Commands (prefix: `c!`)

| Command | Description |
|---------|-------------|
| `c!start` | Start a new game of Coup (creates lobby) |
| `c!stop` / `c!end` | Stop the current game (host only) |
| `c!leaderboard` / `c!lb` | View server leaderboard with stats |
| `c!rules` | View complete game rules and card abilities |
| `c!help` | Show all available commands |

### Slash Commands

| Command | Description |
|---------|-------------|
| `/coup` | View Coup game rules and card information |

## 🚀 Setup

### Prerequisites

- **Python 3.9+** (tested on Python 3.9-3.11)
- **Discord Bot Token** - [Create one here](https://discord.com/developers/applications)
- **Git** (for cloning the repository)

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/coup-discord-bot.git
   cd coup-discord-bot
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate
   
   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure your bot token**
   
   Create a `.env` file in the root directory:
   ```env
   DISCORD_TOKEN=your_discord_bot_token_here
   ```
   
   > **How to get a token:**
   > 1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
   > 2. Click "New Application" → Name it → Create
   > 3. Go to "Bot" tab → Click "Add Bot"
   > 4. Under "Token" section → Click "Reset Token" → Copy it
   > 5. Paste the token into your `.env` file

5. **Invite the bot to your server**
   
   Generate an invite link with these permissions:
   - Send Messages
   - Embed Links
   - Read Message History
   - Add Reactions
   - Use Slash Commands
   
   Or use this invite URL (replace `YOUR_CLIENT_ID`):
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=277025508416&scope=bot%20applications.commands
   ```

6. **Run the bot**
   ```bash
   python bot.py
   ```
   
   You should see: `Logged in as BotName#1234`

## 🎯 How to Play

### Starting a Game

1. **Create a lobby** - Type `c!start` in any text channel
2. **Join the game** - Click the ✅ button to join (2-6 players)
3. **Start playing** - Host clicks ▶️ to begin the game
4. **Check your cards** - Bot sends you a DM with your 2 cards

### During Your Turn

1. **Choose an action** - Click a button from the action menu
2. **Wait for responses** - Other players can challenge or block
3. **Respond to challenges** - Prove you have the card or lose influence
4. **Lose cards** - When you lose influence, choose Card A or Card B to reveal

### Winning

- **Be the last player standing** with at least one card remaining
- **Eliminate opponents** by forcing them to lose both cards
- **Use strategy and bluffing** to outsmart other players!

## 📜 Game Rules

### 🎴 Character Cards (Roles)

Each card grants unique abilities. **You can claim any role - bluffing is allowed!**

| Card | Action | Block Ability | Emoji |
|------|--------|---------------|-------|
| **Duke** | Tax (take 3 coins) | Blocks Foreign Aid | 👑 |
| **Assassin** | Assassinate (pay 3 coins, target loses influence) | None | 🗡️ |
| **Ambassador** | Exchange (draw 2, choose which to keep) | Blocks Steal | 🤝 |
| **Captain** | Steal (take 2 coins from target) | Blocks Steal | ⚓ |
| **Contessa** | None | Blocks Assassination | 🛡️ |

### 💰 General Actions (No Card Required)

| Action | Cost | Effect | Can be Blocked? |
|--------|------|--------|-----------------|
| **Income** | Free | Take 1 coin | ❌ No |
| **Foreign Aid** | Free | Take 2 coins | ✅ Yes (by Duke) |
| **Coup** | 7 coins | Target loses influence | ❌ No (mandatory at 10+ coins) |

### ⚔️ Challenges & Bluffing

**Anyone can challenge a role claim!**

- 🎯 **Challenge successful** (they're bluffing) → They lose influence
- 🛡️ **Challenge failed** (they have the card) → You lose influence, they shuffle card back and draw a new one

**Bluffing is part of the strategy!** You don't need the card to claim its action.

### 🏆 Winning the Game

- Be the **last player with influence** (cards) remaining
- When you lose both cards, you're eliminated
- Strategic bluffing and reading opponents is key!

## 📊 Leaderboard

Each server maintains its own persistent leaderboard tracking:
- **Wins** - Total games won
- **Losses** - Total games lost  
- **Win Rate** - Percentage calculated from W/L ratio

View with `c!leaderboard` or `c!lb`

Stats are saved automatically after each game to `leaderboard.json`

## 🔧 Technical Details

**Built with:**
- `discord.py 2.3.0+` - Modern Discord API wrapper
- `python-dotenv` - Environment variable management
- Discord Buttons & Slash Commands
- JSON-based persistent storage

**Architecture:**
- `bot.py` - Main bot client and command handlers
- `CoupGame.py` - Game state and turn management
- `CoupPlayer.py` - Player data and card management
- `CoupDeck.py` - Deck shuffling and card distribution
- `button_views.py` - Interactive UI components

**Features:**
- Ephemeral (private) messages for sensitive information
- Button-based interactions (no reaction collecting)
- Pass-based challenge/block system
- Proper card shuffling with Python's `random` module
- Server-specific game instances

## 🐛 Troubleshooting

**Bot doesn't respond:**
- Ensure bot has `Send Messages` and `Embed Links` permissions
- Check that the bot is online (green status)

**Can't see slash commands:**
- Wait 5-10 seconds after bot starts (command sync delay)
- Try refreshing Discord (Ctrl+R / Cmd+R)
- Ensure bot was invited with `applications.commands` scope

**No DM received:**
- Check your Discord privacy settings: Server Settings → Privacy Settings → Allow DMs
- Make sure you're not blocking the bot

**Game stuck/not progressing:**
- Host can use `c!stop` to end the game
- Restart the bot if needed

## 🤝 Contributing

Contributions are welcome! Areas for improvement:
- Additional game modes (2v2, teams, etc.)
- Custom rule sets
- More detailed statistics
- Tournament bracket system

Please feel free to submit a Pull Request or open an issue!

## 📄 License

This project is open source and available under the MIT License for educational and personal use.

## 💬 Support

- **Issues:** Open an issue on GitHub
- **Questions:** Check existing issues or start a discussion
- **Discord Support:** Coming soon!

---

### 🎮 Ready to Play?

```bash
python bot.py
```

**Then in Discord:** `c!start`

**Enjoy playing Coup!** 🎲 May the best bluffer win!
