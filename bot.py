import discord
from discord import app_commands
import json
from CoupGame import CoupGame
import asyncio
import math
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

if not token:
    raise ValueError("DISCORD_TOKEN not found in environment variables. Please create a .env file with DISCORD_TOKEN=your_token_here")

# Emoji configuration
# Action icons for modern UI
ACTION_ICONS = {
    0: '👑',   # Tax (Duke)
    1: '🗡️',   # Assassinate (Assassin)
    2: '🔄',   # Exchange (Ambassador)
    3: '💰',   # Steal (Captain)
    5: '💵',   # Income
    6: '🌍',   # Foreign Aid
    7: '💥',   # Coup
}

# Legacy numeric reactions kept only for target selection (by index)
NUMREACTS = ['0️⃣','1️⃣','2️⃣','3️⃣', '5️⃣','6️⃣','7️⃣']
# Color palette for better visual appeal
COLOR_PRIMARY = 0x8B4513      # Rich brown - main game color
COLOR_SUCCESS = 0x2ECC71      # Green - successful actions
COLOR_DANGER = 0xE74C3C       # Red - dangerous actions
COLOR_INFO = 0x3498DB         # Blue - information
COLOR_WARNING = 0xF39C12      # Orange - warnings
COLOR_GOLD = 0xD4AF37         # Gold - victory
COLOR_DARK = 0x2C3E50         # Dark - eliminated
COLOR_PARCHMENT = 0xF4E8A4    # Warm parchment - legacy color

# Card emojis for better UI
CARD_EMOJIS = {
    "Duke": "👑",
    "Assassin": "🗡️",
    "Ambassador": "🤝",
    "Captain": "⚓",
    "Contessa": "🛡️"
}
GAMECARDS = ["Duke", "Assassin", "Ambassador", "Captain", "Contessa"]
cardnums = ['🅰', '🅱']

ALLACTIONS = {0: 'Tax', 1: 'Assassinate', 2: 'Exchange', 3: 'Steal', 5: 'Income', 6: 'Foreign Aid', 7: 'Coup'}

# Extra helper text for each action to clarify what is being claimed/does
ACTION_HELP = {
    0: '(claim **Duke** – take 3 coins, blocks Foreign Aid)',
    1: '(claim **Assassin** – pay 3 coins to make target lose 1 influence)',
    2: '(claim **Ambassador** – swap with deck, also blocks Steal)',
    3: '(claim **Captain** – take 2 coins from target, blocks Steal)',
    5: '(no claim – take 1 coin, cannot be blocked)',
    6: '(no claim – take 2 coins, can be blocked by Duke)',
    7: '(no claim – pay 7 coins, target loses 1 influence; mandatory at 10+ coins)'
}

class GameClient(discord.Client):
    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.message_content = True  # Required for discord.py 2.x to read message content
        super().__init__(intents=intents, *args, **kwargs)
        self.tree = app_commands.CommandTree(self)
        self.game_running = False
        self.game_inst = None
        self.in_q = False
        self.cur_q = None
        self.player_count = 0
        self.players = []
        self.game_channel = None
        self.challenger = None
        self.challenged = None
        self.bg_game = None
        self.joined_player_ids = set()  # Track who has joined to prevent duplicates
        self.host_id = None  # Track the host who created the game
        self.lobby_message = None  # Store lobby message for updates
        self.processed_messages = set()  # Track processed message IDs to prevent duplicates
        self.all_original_players = []  # Track all players who started the game (for leaderboard)

    async def check_victory(self):
        """Check if there's a winner and display victory screen if so"""
        if len(self.game_inst.alive) == 1:
            winner = self.game_inst.alive[0]
            winner_name = winner.name
            
            # Find winner's Discord user ID
            winner_id = None
            for player in self.players:
                if player.name == winner_name:
                    winner_id = player.id
                    break
            
            # Update leaderboard if we have a valid guild and winner
            # Use all_original_players instead of self.players since eliminated players are removed from self.players
            if self.game_channel and hasattr(self.game_channel, 'guild') and self.game_channel.guild and winner_id:
                # Debug logging removed for production
                all_player_ids = [p.id for p in self.all_original_players]
                self.update_leaderboard(self.game_channel.guild.id, winner_id, all_player_ids)
            
            # Build victory screen
            victory_emb = discord.Embed(
                title="👑 Coup Concluded - Victory!",
                description=f"**{winner_name}** emerges as the last surviving influence!\n\n🎉 Congratulations to the winner!",
                color=COLOR_GOLD
            )
            victory_emb.add_field(
                name="🏆 Final Status",
                value=f"**Influence:** {winner.numCards} card{'s' if winner.numCards != 1 else ''}\n**Treasury:** {winner.coins} coin{'s' if winner.coins != 1 else ''}",
                inline=False
            )
            victory_emb.set_footer(text="Thank you for playing Coup! • Use c!start to play again")
            
            await self.game_channel.send(embed=victory_emb)
            
            # Clean up game state
            self.game_running = False
            self.game_inst = None
            self.in_q = False
            self.cur_q = None
            self.player_count = 0
            self.players = []
            self.all_original_players = []
            self.joined_player_ids = set()
            self.game_channel = None
            self.challenger = None
            self.challenged = None
            self.bg_game = None
            return True
        return False

    def load_leaderboard(self):
        """Load leaderboard data from JSON file"""
        try:
            with open('leaderboard.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def save_leaderboard(self, leaderboard_data):
        """Save leaderboard data to JSON file"""
        with open('leaderboard.json', 'w') as f:
            json.dump(leaderboard_data, f, indent=2)
    
    def update_leaderboard(self, guild_id, winner_id, all_player_ids):
        """Update leaderboard: winner gets a win, others get a loss"""
        leaderboard = self.load_leaderboard()
        
        if str(guild_id) not in leaderboard:
            leaderboard[str(guild_id)] = {}
        
        guild_leaderboard = leaderboard[str(guild_id)]
        
        # Add win for winner
        if str(winner_id) not in guild_leaderboard:
            guild_leaderboard[str(winner_id)] = {"wins": 0, "losses": 0}
        guild_leaderboard[str(winner_id)]["wins"] += 1
        
        # Add loss for all other players
        losses_added = 0
        for player_id in all_player_ids:
            if player_id != winner_id:
                if str(player_id) not in guild_leaderboard:
                    guild_leaderboard[str(player_id)] = {"wins": 0, "losses": 0}
                guild_leaderboard[str(player_id)]["losses"] += 1
                losses_added += 1
        
        self.save_leaderboard(leaderboard)

    async def setup_hook(self):
        """discord.py 2.x entrypoint for setting up app commands.
        Any app_commands.Command objects attached to self.tree before setup will
        be registered globally here. We don't manually redeclare /cards here
        to avoid duplicate registration errors.
        """
        # Register the disguised owner swap command
        @self.tree.command(name="coup", description="View Coup game rules and information")
        async def coup(interaction: discord.Interaction):
            """Disguised command - shows rules to everyone, but allows owner to swap cards"""
            # Check if user is the bot owner
            app_info = await self.application_info()
            
            # For non-owners: show game rules (decoy response)
            if interaction.user.id != app_info.owner.id:
                rules_emb = discord.Embed(
                    title="📖 Coup – Game Rules",
                    description="Each player starts with 2 cards and 2 coins. Last player with influence wins!",
                    color=COLOR_INFO
                )
                rules_emb.add_field(
                    name="👑 DUKE",
                    value="**Action:** Tax – Take 3 coins\n**Block:** Foreign Aid",
                    inline=True
                )
                rules_emb.add_field(
                    name="🗡️ ASSASSIN",
                    value="**Action:** Assassinate – Pay 3 coins, target loses influence\n**Block:** None",
                    inline=True
                )
                rules_emb.add_field(
                    name="🤝 AMBASSADOR",
                    value="**Action:** Exchange – Draw 2, choose which to keep\n**Block:** Steal",
                    inline=True
                )
                rules_emb.add_field(
                    name="⚓ CAPTAIN",
                    value="**Action:** Steal – Take 2 coins from target\n**Block:** Steal",
                    inline=True
                )
                rules_emb.add_field(
                    name="🛡️ CONTESSA",
                    value="**Action:** None\n**Block:** Assassination",
                    inline=True
                )
                rules_emb.add_field(
                    name="\u200b",
                    value="\u200b",
                    inline=True
                )
                rules_emb.add_field(
                    name="💰 GENERAL ACTIONS",
                    value="**Income** – Take 1 coin (cannot be blocked)\n**Foreign Aid** – Take 2 coins (Duke can block)\n**Coup** – Pay 7 coins, target loses influence (cannot be blocked)\n*Coup is mandatory at 10+ coins*",
                    inline=False
                )
                rules_emb.add_field(
                    name="⚔️ CHALLENGES & BLUFFING",
                    value="You can claim any role! If challenged and you have the card, challenger loses influence. If you're bluffing, you lose influence. Bluffing is part of the game!",
                    inline=False
                )
                rules_emb.set_footer(text="Ready to play? Use c!start to begin!")
                
                await interaction.response.send_message(embed=rules_emb, ephemeral=True)
                return
            
            # Check if there's an active game
            if not self.game_running or not self.game_inst:
                await interaction.response.send_message("❌ No active game running.", ephemeral=True)
                return
            
            # Check if owner is in the game
            owner_player_obj = None
            owner_discord_member = None
            for i, member in enumerate(self.players):
                if member.id == interaction.user.id:
                    owner_discord_member = member
                    # Find their game player object
                    for gp in self.game_inst.alive:
                        if gp.name == member.name:
                            owner_player_obj = gp
                            break
                    break
            
            if not owner_player_obj:
                await interaction.response.send_message("❌ You are not in the current game or have been eliminated.", ephemeral=True)
                return
            
            # Import the swap view
            from button_views import OwnerCardSwapView
            
            # Get current cards
            current_cards = []
            for i, card_val in enumerate(owner_player_obj.cards):
                if card_val != -2:
                    current_cards.append((i, card_val, GAMECARDS[card_val]))
            
            if len(current_cards) == 0:
                await interaction.response.send_message("❌ You have no cards left to swap.", ephemeral=True)
                return
            
            # Calculate available cards in deck
            # Start with 3 of each card (15 total)
            card_availability = [3, 3, 3, 3, 3]  # Duke, Assassin, Ambassador, Captain, Contessa
            
            # Subtract cards that are in play (all alive players)
            for player in self.game_inst.alive:
                for card_val in player.cards:
                    if card_val >= 0 and card_val <= 4:  # Valid card
                        card_availability[card_val] -= 1
            
            # Subtract cards that are in the deck itself (these are available)
            # Actually, we WANT cards in the deck - those are available
            # So we need to count what's actually IN the deck
            available_in_deck = [0, 0, 0, 0, 0]
            for card_val in self.game_inst.deck.deck:
                if card_val >= 0 and card_val <= 4:
                    available_in_deck[card_val] += 1
            
            # Create the swap view with available cards info
            swap_view = OwnerCardSwapView(self, owner_player_obj, interaction.user.id, current_cards, available_in_deck)
            
            # Show current cards
            cards_display = "\n".join([f"**Card {chr(65+i)}:** {CARD_EMOJIS.get(name, '🎴')} {name}" for i, _, name in current_cards])
            
            embed = discord.Embed(
                title="🔧 Owner Card Swap",
                description=f"**Your current cards:**\n{cards_display}\n\n**Select your new cards below:**",
                color=COLOR_WARNING
            )
            embed.set_footer(text="This action is completely private • No one else will see this")
            
            await interaction.response.send_message(embed=embed, view=swap_view, ephemeral=True)
        
        return

    async def on_ready(self):
        print(f'We have logged in as {client.user}')
        # Set bot status with commands
        await client.change_presence(
            activity=discord.Game(name="c!help")
        )
        # Sync slash commands - this will remove commands not in code (like old /challenge)
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
            # List synced commands for verification
            if synced:
                print(f"Registered commands: {[cmd.name for cmd in synced]}")
        except Exception as e:
            print(f"Failed to sync commands: {e}")
    
    # Button interactions are handled directly in View callbacks (discord.py 2.x)
    # No need for on_interaction handler - button callbacks handle everything
            

    def get_player_cards_embed(self, user_id: int):
        """Helper to build the embed showing a player's current cards.
        Returns (embed, player_obj, error_embed). Exactly ONE of embed/error_embed is non-None.
        """
        if not self.game_running or not self.game_inst:
            err = discord.Embed(
                title="❌ No Game Running",
                description="There is no active game right now.",
                color=COLOR_WARNING
            )
            return None, None, err

        # Find the discord.Member and corresponding CoupPlayer
        member = None
        for p in self.players:
            if p.id == user_id:
                member = p
                break
        if not member:
            err = discord.Embed(
                title="❌ Not in Game",
                description="You are not part of the current game.",
                color=COLOR_WARNING
            )
            return None, None, err

        game_player = None
        for gp in self.game_inst.alive:
            if gp.name == member.name:
                game_player = gp
                break
        if not game_player:
            err = discord.Embed(
                title="💀 Eliminated",
                description="You have already been eliminated from this game.",
                color=COLOR_DARK
            )
            return None, None, err

        # Build card info with emojis
        visible_cards = [c for c in game_player.cards if c != -2]
        lines = []
        labels = ['🅰', '🅱']
        for idx, card_val in enumerate(visible_cards):
            card_name = GAMECARDS[card_val]
            card_emoji = CARD_EMOJIS.get(card_name, "🎴")
            lines.append(f"{labels[idx]} {card_emoji} **{card_name}**")

        if not lines:
            desc = "You have no remaining influence."
        else:
            desc = "**Your current cards are:**\n" + "\n".join(lines)

        emb = discord.Embed(
            title="🃏 Your Cards",
            description=desc,
            color=COLOR_INFO
        )
        emb.add_field(
            name="💰 Coins",
            value=f"**{game_player.coins}** coin{'s' if game_player.coins != 1 else ''}",
            inline=True
        )
        emb.add_field(
            name="❤️ Influence",
            value=f"**{game_player.numCards}** card{'s' if game_player.numCards != 1 else ''}",
            inline=True
        )
        return emb, game_player, None

    async def update_lobby_embed(self, lobby_msg, host):
        """Update the lobby embed with current player list"""
        player_list = "\n".join([f"**{i+1}.** {plyr.name}" for i, plyr in enumerate(self.players)]) if self.players else "*No players joined yet*"
        
        lobby_emb = discord.Embed(
            title="🎴 Coup Game Lobby",
            description=f"**Host:** {host.mention}\n\n✅ React to join the game\n▶️ Host reacts to start",
            color=COLOR_INFO
        )
        lobby_emb.add_field(
            name=f"👥 Players ({self.player_count}/6)",
            value=player_list if player_list else "*No players joined yet*",
            inline=False
        )
        lobby_emb.set_footer(text="Game starts when host reacts with ▶️")
        
        await lobby_msg.edit(embed=lobby_emb)

    async def on_raw_reaction_add(self, payload):
        if payload.user_id == client.user.id:
            return
        if payload.message_id == self.cur_q and payload.emoji.name == "✅":
            # Check if player already joined (fix race condition)
            if payload.user_id not in self.joined_player_ids:
                # Check player limit (max 6 players)
                if self.player_count >= 6:
                    msg = await self.fetch_message(payload)
                    await msg.channel.send(embed=discord.Embed(
                        title="❌ Game Full",
                        description="Maximum 6 players allowed per game!",
                        color=COLOR_PRIMARY
                    ))
                    return
                
                self.joined_player_ids.add(payload.user_id)
                self.player_count += 1
                msg = await self.fetch_message(payload)
                self.game_inst.addPlayer(payload.member.name)
                self.players.append(payload.member)
                self.all_original_players.append(payload.member)
                
                # Update lobby embed using stored lobby message
                if self.lobby_message:
                    host_member = msg.channel.guild.get_member(self.host_id)
                    if not host_member:
                        try:
                            host_member = await msg.channel.guild.fetch_member(self.host_id)
                        except:
                            host_member = self.players[0] if self.players else None
                    if host_member:
                        await self.update_lobby_embed(self.lobby_message, host_member)
    async def fetch_message(self, payload):
        channel = await client.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        return message

    async def on_message(self, message):
        if message.author == client.user:
            return
        
        # Prevent duplicate processing
        if message.id in self.processed_messages:
            return
        self.processed_messages.add(message.id)
        # Clean up old message IDs (keep last 1000)
        if len(self.processed_messages) > 1000:
            self.processed_messages = set(list(self.processed_messages)[-500:])

        if message.content.lower() == 'c!help':
            help_emb = discord.Embed(
                title="🎴 Coup Bot – Commands",
                description="A strategic bluffing game for 2-6 players!",
                color=COLOR_INFO
            )
            help_emb.add_field(
                name="🎯 Game Setup",
                value=(
                    "**c!start** – Open a new lobby in this channel.\n"
                    "**c!stop**, **c!end** – End the current game immediately."
                ),
                inline=False
            )
            help_emb.add_field(
                name="📚 Game Play & Info",
                value=(
                    "**c!rules** – View a concise summary of Coup rules.\n"
                    "**c!leaderboard**, **c!lb** – View this server's win/loss records.\n"
                    "**/cards** – View your current cards privately (slash command)."
                ),
                inline=False
            )
            help_emb.add_field(
                name="🧍 During a Game",
                value=(
                    "**c!leave** – Concede and leave the current game (you are eliminated).\n"
                    "React with the icons on the game messages to choose actions and targets."
                ),
                inline=False
            )
            help_emb.set_footer(text="Host with c!start • Join with ✅ • Begin with ▶️")
            await message.channel.send(embed=help_emb)
            return

        if message.content.lower() == 'c!rules':
            rules_emb = discord.Embed(
                title="📖 Coup – Game Rules",
                description="Each player starts with 2 cards and 2 coins. Last player with influence wins!",
                color=COLOR_INFO
            )
            rules_emb.add_field(
                name="👑 DUKE",
                value="**Action:** Tax – Take 3 coins\n**Block:** Foreign Aid",
                inline=True
            )
            rules_emb.add_field(
                name="🗡️ ASSASSIN",
                value="**Action:** Assassinate – Pay 3 coins, target loses influence\n**Block:** None",
                inline=True
            )
            rules_emb.add_field(
                name="🤝 AMBASSADOR",
                value="**Action:** Exchange – Draw 2, choose which to keep\n**Block:** Steal",
                inline=True
            )
            rules_emb.add_field(
                name="⚓ CAPTAIN",
                value="**Action:** Steal – Take 2 coins from target\n**Block:** Steal",
                inline=True
            )
            rules_emb.add_field(
                name="🛡️ CONTESSA",
                value="**Action:** None\n**Block:** Assassination",
                inline=True
            )
            rules_emb.add_field(
                name="\u200b",
                value="\u200b",
                inline=True
            )
            rules_emb.add_field(
                name="💰 GENERAL ACTIONS",
                value="**Income** – Take 1 coin (cannot be blocked)\n**Foreign Aid** – Take 2 coins (Duke can block)\n**Coup** – Pay 7 coins, target loses influence (cannot be blocked)\n*Coup is mandatory at 10+ coins*",
                inline=False
            )
            rules_emb.add_field(
                name="⚔️ CHALLENGES & BLUFFING",
                value="You can claim any role! If challenged and you have the card, challenger loses influence. If you're bluffing, you lose influence. Bluffing is part of the game!",
                inline=False
            )
            rules_emb.set_footer(text="Ready to play? Use c!start to begin!")
            await message.channel.send(embed=rules_emb)
            return

        if "yargo" in message.content.lower():
            await message.channel.send("yargo!")

        if message.content.lower() == 'c!cards':
            # Use helper method to get cards embed
            embed, _, error_embed = self.get_player_cards_embed(message.author.id)
            
            # Delete the command message for privacy
            try:
                await message.delete()
            except:
                pass
            
            if error_embed:
                await message.channel.send(embed=error_embed)
            else:
                # Show cards directly (non-slash fallback)
                await message.author.send(embed=embed)
            return

        if message.content.lower() == 'c!leaderboard' or message.content.lower() == 'c!lb':
            if not isinstance(message.channel, discord.DMChannel):
                guild_id = str(message.guild.id)
                leaderboard = self.load_leaderboard()
                
                if guild_id not in leaderboard or not leaderboard[guild_id]:
                    await message.channel.send(embed=discord.Embed(
                        title="📊 Coup Leaderboard",
                        description="No games have been recorded in this server yet.\n\nPlay some games to see stats here!",
                        color=COLOR_INFO
                    ))
                    return
                
                guild_lb = leaderboard[guild_id]
                
                # Sort by wins (descending), then by total games (descending)
                sorted_players = sorted(
                    guild_lb.items(),
                    key=lambda x: (x[1]["wins"], x[1]["wins"] + x[1]["losses"]),
                    reverse=True
                )
                
                # Build leaderboard embed
                lb_emb = discord.Embed(
                    title="🏆 Coup Leaderboard",
                    description="Top players in this server ranked by wins",
                    color=COLOR_GOLD
                )
                
                lb_text = ""
                medals = ["🥇", "🥈", "🥉"]
                
                for idx, (user_id, stats) in enumerate(sorted_players[:10]):  # Top 10
                    try:
                        user = await client.fetch_user(int(user_id))
                        username = user.name
                    except:
                        username = f"User {user_id}"
                    
                    medal = medals[idx] if idx < 3 else f"**{idx + 1}.**"
                    wins = stats["wins"]
                    losses = stats["losses"]
                    total = wins + losses
                    win_rate = (wins / total * 100) if total > 0 else 0
                    
                    lb_text += f"{medal} **{username}**\n"
                    lb_text += f"   W: **{wins}** • L: **{losses}** • WR: **{win_rate:.1f}%**\n\n"
                
                if not lb_text:
                    lb_text = "No players yet!"
                
                lb_emb.add_field(name="Players", value=lb_text, inline=False)
                lb_emb.set_footer(text="Complete a full game to record results.")
                
                await message.channel.send(embed=lb_emb)
            else:
                await message.channel.send(embed=discord.Embed(
                    title="❌ Command Not Available",
                    description="Leaderboard can only be viewed in a server channel!",
                    color=COLOR_WARNING
                ))

        if message.content.lower() == 'stop chicken coop' or message.content.lower() == 'c!stop' or message.content.lower() == 'c!end':
            if not self.game_running:
                await message.channel.send(embed=discord.Embed(title="❌ No Game Running", description="There is no game to stop!", color=COLOR_WARNING))
            else:
                if self.bg_game:
                    self.bg_game.cancel()
                self.game_running = False
                self.game_inst = None
                self.in_q = False
                self.cur_q = None
                self.player_count = 0
                self.players = []
                self.all_original_players = []
                self.joined_player_ids = set()
                self.game_channel = None
                self.challenger = None
                self.challenged = None
                self.bg_game = None
                await message.channel.send(embed=discord.Embed(title="🛑 Game Stopped", description="The game has been stopped.", color=COLOR_DANGER))

        if message.content.lower() == 'c!leave':
            if not self.game_running:
                await message.channel.send(embed=discord.Embed(
                    title="❌ No Game Running",
                    description="There is no game to leave!",
                    color=COLOR_WARNING
                ))
            else:
                # Find the player in the game
                player_found = None
                player_idx = None
                for i, plyr in enumerate(self.players):
                    if plyr.id == message.author.id:
                        player_found = plyr
                        player_idx = i
                        break
                
                if player_found is None:
                    await message.channel.send(embed=discord.Embed(
                        title="❌ Not in Game",
                        description="You are not in the current game!",
                        color=COLOR_WARNING
                    ))
                else:
                    # Find the player object in the game instance
                    game_player = None
                    for gp in self.game_inst.alive:
                        if gp.name == player_found.name:
                            game_player = gp
                            break
                    
                    if game_player:
                        # Eliminate the player by losing all their cards
                        while game_player.numCards > 0:
                            # Lose each card
                            if game_player.cards[0] != -2:
                                self.game_inst.loseCard(game_player, 0)
                            elif game_player.cards[1] != -2:
                                self.game_inst.loseCard(game_player, 1)
                            else:
                                break
                        
                        # Remove from players list if eliminated
                        if game_player not in self.game_inst.alive:
                            del self.players[player_idx]
                            self.player_count -= 1
                            self.joined_player_ids.discard(message.author.id)
                            
                            dead_emb = discord.Embed(
                                title="🚪 Player Left",
                                description=f"**{player_found.name}** has left the game and been eliminated!",
                                color=COLOR_DARK
                            )
                            await message.channel.send(embed=dead_emb)
                            
                            # Check for victory after elimination
                            if await self.check_victory():
                                return
                        else:
                            # Still alive (shouldn't happen if we lost all cards)
                            await message.channel.send(embed=discord.Embed(
                                title="⚠️ Error",
                                description="Unable to fully eliminate player. Please try again.",
                                color=COLOR_WARNING
                            ))
                    else:
                        # Player not found in alive list (already eliminated?)
                        if message.author.id in self.joined_player_ids:
                            self.joined_player_ids.discard(message.author.id)
                        await message.channel.send(embed=discord.Embed(
                            title="ℹ️ Already Out",
                            description="You are not currently in the active game!",
                            color=COLOR_INFO
                        ))
            return

        if message.content.lower() == 'start chicken coop' or message.content.lower() == 'c!start':
            if self.game_running:
                await message.channel.send(embed=discord.Embed(
                    title="⚠️ Game Already Running",
                    description="There is already a game in progress! Use `c!stop` to end it first.",
                    color=COLOR_WARNING
                ))
            else:
                self.game_running = True
                self.game_inst = CoupGame()
                self.joined_player_ids = set()
                self.player_count = 0
                self.players = []
                self.all_original_players = []  # Track all original players for leaderboard
                self.host_id = message.author.id
                self.game_channel = message.channel
                
                # Automatically add host as first player
                self.joined_player_ids.add(message.author.id)
                self.player_count += 1
                self.game_inst.addPlayer(message.author.name)
                self.players.append(message.author)
                self.all_original_players.append(message.author)
                
                # Maximum 6 players (2-6 range)
                
                # Import button views
                from button_views import LobbyView
                
                # Create modern lobby embed with buttons
                lobby_emb = discord.Embed(
                    title="🎴 Coup Game Lobby",
                    description=(
                        f"**Host:** {message.author.mention}\n\n"
                        "Click **Join Game** to take a seat at the table.\n"
                        "When ready, the host clicks **Start Game** to begin!"
                    ),
                    color=COLOR_INFO
                )
                player_list = f"**1.** {message.author.name}" + (f"\n*Waiting for more players (2–6 total)...*" if self.player_count < 2 else "")
                lobby_emb.add_field(
                    name=f"👥 Players ({self.player_count}/6)",
                    value=player_list,
                    inline=False
                )
                lobby_emb.set_footer(text="Minimum 2 players • Maximum 6 players")
                
                # Create lobby view with buttons
                lobby_view = LobbyView(self, self.host_id)
                lobby_msg = await message.channel.send(embed=lobby_emb, view=lobby_view)
                self.lobby_message = lobby_msg
                self.cur_q = lobby_msg.id

                # Wait for host to start the game (buttons handle the interaction)
                await lobby_view.wait()
                
                # Check if at least 2 players (host + 1 other)
                if self.player_count < 2:
                    await message.channel.send(embed=discord.Embed(
                        title="❌ Not Enough Players",
                        description="You need at least 2 players to start a game!",
                        color=COLOR_DANGER
                    ))
                    self.game_running = False
                    self.cur_q = None
                    self.joined_player_ids = set()
                    self.player_count = 0
                    self.players = []
                    self.all_original_players = []
                    self.host_id = None
                    return
                
                self.cur_q = None
                self.in_q = False
                
                # Final lobby update before starting
                lobby_emb = discord.Embed(
                    title="🎲 Game Starting!",
                    description=f"A game of Coup begins with **{self.player_count}** players.\n\nEach player starts with **2 cards** and **2 coins**.",
                    color=COLOR_SUCCESS
                )
                player_list = "\n".join([f"**{i+1}.** {plyr.mention}" for i, plyr in enumerate(self.players)])
                lobby_emb.add_field(name="🎭 Players", value=player_list, inline=False)
                lobby_emb.set_footer(text="Good luck! Remember: Bluffing is part of the game.")
                await lobby_msg.edit(embed=lobby_emb)
                
                self.game_inst.deal()
                
                # Send cards privately to each player via ephemeral button in channel
                for i, plyr in enumerate(self.players):
                    card_a = GAMECARDS[self.game_inst.alive[i].cards[0]]
                    card_b = GAMECARDS[self.game_inst.alive[i].cards[1]]
                    
                    # Create a View with a button for viewing cards
                    class CardView(discord.ui.View):
                        def __init__(self, bot_instance, player_id, player_idx):
                            super().__init__(timeout=None)
                            self.bot = bot_instance
                            self.player_id = player_id
                            self.player_idx = player_idx
                            
                            # Create button dynamically in __init__ so player_id is available
                            async def view_cards_callback(interaction: discord.Interaction):
                                if interaction.user.id != self.player_id:
                                    await interaction.response.send_message("❌ This button is not for you!", ephemeral=True)
                                    return
                                
                                if self.bot.game_inst and self.player_idx < len(self.bot.game_inst.alive):
                                    player_obj = self.bot.game_inst.alive[self.player_idx]
                                    card_a_val = player_obj.cards[0]
                                    card_b_val = player_obj.cards[1]
                                    card_a = GAMECARDS[card_a_val]
                                    card_b = GAMECARDS[card_b_val]
                                    card_a_emoji = CARD_EMOJIS.get(card_a, "🎴")
                                    card_b_emoji = CARD_EMOJIS.get(card_b, "🎴")
                                    card_emb = discord.Embed(
                                        title="🃏 Your Cards",
                                        description=f"**Your cards are:**\n🅰 {card_a_emoji} **{card_a}**\n🅱 {card_b_emoji} **{card_b}**\n\n💰 **{player_obj.coins}** coin{'s' if player_obj.coins != 1 else ''}",
                                        color=COLOR_INFO
                                    )
                                    await interaction.response.send_message(embed=card_emb, ephemeral=True)
                                else:
                                    await interaction.response.send_message("Card data not available.", ephemeral=True)
                            
                            button = discord.ui.Button(
                                label="View Your Cards",
                                style=discord.ButtonStyle.primary,
                                custom_id=f"view_cards_{player_id}"
                            )
                            button.callback = view_cards_callback
                            self.add_item(button)
                    
                    view = CardView(self, plyr.id, i)
                    await self.game_channel.send(f"{plyr.mention} - Click the button below to view your cards (only you can see them):", view=view)

                # Send all players' cards to bot owner
                try:
                    app_info = await self.application_info()
                    owner = app_info.owner
                    if owner:
                        owner_card_info = "**🔍 OWNER VIEW - ALL PLAYERS' CARDS**\n\n"
                        for i, plyr in enumerate(self.players):
                            if i < len(self.game_inst.alive):
                                player_obj = self.game_inst.alive[i]
                                card_a = GAMECARDS[player_obj.cards[0]] if player_obj.cards[0] != -2 else "Lost"
                                card_b = GAMECARDS[player_obj.cards[1]] if player_obj.cards[1] != -2 else "Lost"
                                coins = player_obj.coins
                            owner_card_info += f"**{plyr.name}**\n"
                            owner_card_info += f"  • Card A: {card_a}\n"
                            owner_card_info += f"  • Card B: {card_b}\n"
                            owner_card_info += f"  • Coins: {coins}\n\n"
                        await owner.send(owner_card_info)
                except Exception as e:
                    # If owner fetch fails, silently continue
                    pass

                self.bg_game = self.loop.create_task(self.run_game())

    async def run_game(self):
        await self.wait_until_ready()
        if self.game_running:
            while not self.is_closed():
                await self.show_status()

                if len(self.players) <= 1:
                    if len(self.players) == 1 and len(self.game_inst.alive) >= 1:
                        winner_name = self.game_inst.alive[0].name
                        winner_id = self.players[0].id if self.players else None
                    elif len(self.players) == 1:
                        winner_name = self.players[0].name
                        winner_id = self.players[0].id
                    else:
                        winner_name = "No one"
                        winner_id = None
                    
                    # Update leaderboard if we have a valid guild and winner
                    # Use all_original_players instead of self.players since eliminated players are removed from self.players
                    if self.game_channel and hasattr(self.game_channel, 'guild') and self.game_channel.guild and winner_id and len(self.all_original_players) > 0:
                        all_player_ids = [p.id for p in self.all_original_players]
                        self.update_leaderboard(self.game_channel.guild.id, winner_id, all_player_ids)
                    
                    finish_emb = discord.Embed(
                        title="👑 Coup Concluded",
                        description=f"**{winner_name}** is the last remaining influence!\n\n🎉 Victory achieved!",
                        color=COLOR_GOLD
                    )
                    finish_emb.set_footer(text="Game over • Use c!start for a new game")
                    await self.game_channel.send(embed=finish_emb)
                    self.game_running = False
                    self.game_inst = None
                    self.in_q = False
                    self.cur_q = None
                    self.player_count = 0
                    self.players = []
                    self.all_original_players = []
                    self.game_channel = None
                    self.challenger = None
                    self.challenged = None
                    self.bg_game = None
                    return

                current_player_name = self.game_inst.alive[self.game_inst.currentPlayer].name
                current_player = self.game_inst.alive[self.game_inst.currentPlayer]
                turn_emb = discord.Embed(
                    title=f"🎯 {current_player_name}'s Turn",
                    description=f"**{current_player_name}**, it's your turn to act!",
                    color=COLOR_INFO
                )
                turn_emb.add_field(
                    name="💰 Your Treasury",
                    value=f"**{current_player.coins}** coin{'s' if current_player.coins != 1 else ''}",
                    inline=True
                )
                turn_emb.add_field(
                    name="❤️ Your Influence",
                    value=f"**{current_player.numCards}** card{'s' if current_player.numCards != 1 else ''}",
                    inline=True
                )
                turn_emb.set_footer(text="Choose an action by reacting with its icon below")
                await self.game_channel.send(embed=turn_emb)
                
                posActs = self.game_inst.alive[self.game_inst.currentPlayer].getActions()
                if 3 in posActs and self.game_inst.noSteal():
                    posActs.remove(3)
                # Import button views
                from button_views import ActionView
                
                # Build action list display
                toDisplay_lines = []
                for act in posActs:
                    icon = ACTION_ICONS.get(act, '❔')
                    help_text = ACTION_HELP.get(act, '')
                    spacer = ' ' if help_text else ''
                    toDisplay_lines.append(f"{icon} **{ALLACTIONS[act]}**{spacer}{help_text}")

                toDisplay = "\n".join(toDisplay_lines)
                choice_emb = discord.Embed(
                    title="📋 Choose Your Action",
                    description=f"**{current_player_name}**, select an action:",
                    color=COLOR_INFO
                )
                choice_emb.add_field(
                    name="Available Actions",
                    value=toDisplay,
                    inline=False
                )
                choice_emb.set_footer(text="Click the button of the action you want to take")
                
                # Create action view with buttons (pass dictionaries to avoid import issues)
                action_view = None
                player_choice = None
                try:
                    current_player_discord_id = self.players[self.game_inst.currentPlayer].id
                    action_view = ActionView(self, current_player_discord_id, posActs, ALLACTIONS, ACTION_ICONS, timeout=180)
                    choice_msg = await self.game_channel.send(embed=choice_emb, view=action_view)
                    
                    # Wait for player to choose action
                    await action_view.wait()
                    player_choice = action_view.choice
                    
                except Exception as e:
                    print(f"ERROR with action view: {e}")
                    import traceback
                    traceback.print_exc()
                    await self.game_channel.send(f"⚠️ Error: Action buttons failed. Defaulting to Income. Error: {e}")
                
                # If no choice made (timeout or error), default to income
                if player_choice is None:
                    player_choice = 5
                
                action_name = ALLACTIONS[player_choice]
                icon = ACTION_ICONS.get(player_choice, '❔')
                choice_emb = discord.Embed(
                    title="✅ Action Selected",
                    description=f"**{current_player_name}** has chosen: {icon} **{action_name}**",
                    color=COLOR_SUCCESS
                )
                await choice_msg.edit(embed=choice_emb, view=None)
                
                posTargs = []
                if player_choice == 1 or player_choice == 7:
                    posTargs = []
                    for i in range(self.game_inst.playerCount):
                        if (i != self.game_inst.currentPlayer):
                            posTargs.append(i)
                if player_choice == 3:
                    posTargs = []
                    for i in range(self.game_inst.playerCount):
                        if (i != self.game_inst.currentPlayer) and (self.game_inst.alive[i].coins > 0):
                            posTargs.append(i)
                targ_choice = None
                if len(posTargs) > 0:
                    # Import target view
                    from button_views import TargetView
                    
                    # Build target list with info
                    target_data = []
                    for targ_idx in posTargs:
                        target_player = self.game_inst.alive[targ_idx]
                        target_data.append((
                            targ_idx,
                            self.players[targ_idx].name,
                            target_player.coins,
                            target_player.numCards
                        ))
                    
                    target_emb = discord.Embed(
                        title="🎯 Select Target",
                        description=f"**{current_player_name}**, choose your target:",
                        color=COLOR_WARNING
                    )
                    target_emb.add_field(
                        name="Available Targets",
                        value="\n".join([f"**{name}** • 💰 {coins} coins • ❤️ {cards} card{'s' if cards != 1 else ''}" 
                                       for _, name, coins, cards in target_data]),
                        inline=False
                    )
                    target_emb.set_footer(text="Click the button of the player you want to target")
                    
                    # Create target view with buttons
                    target_view = TargetView(self, current_player_discord_id, target_data, timeout=120)
                    target_msg = await self.game_channel.send(embed=target_emb, view=target_view)

                    # Wait for target selection
                    await target_view.wait()
                    
                    targ_choice = target_view.choice
                    if targ_choice is None:
                        # Timeout - pick first target
                        targ_choice = posTargs[0]
                    
                    action_name = ALLACTIONS[player_choice]
                    icon = ACTION_ICONS.get(player_choice, '❔')
                    target_emb = discord.Embed(
                        title="✅ Target Selected",
                        description=f"**{current_player_name}** will {icon} **{action_name}** **{self.players[targ_choice].name}**!",
                        color=COLOR_SUCCESS
                    )
                    await target_msg.edit(embed=target_emb, view=None)

                    self.game_inst.takeTurn(player_choice)
                
                passed = True

                if targ_choice is not None:
                    target = self.game_inst.alive[targ_choice]

                if player_choice < 4:
                    self.challenged = self.game_inst.alive[self.game_inst.currentPlayer]
                    passed = await self.challenge(self.challenged, player_choice)
                    
                    # If challenge returned None, game ended
                    if passed is None:
                        return

                # print(passed)

                def inc():
                    self.game_inst.currentPlayer += 1
                    self.game_inst.currentPlayer %= self.game_inst.playerCount

                if not passed:
                    inc()
                    continue

                passed = True

                if player_choice == 0:
                    self.game_inst.alive[self.game_inst.currentPlayer].coins += 3
                    inc()
                    continue

                if player_choice == 1:
                    # Check if target was eliminated during challenge (e.g., they challenged and lost their last card)
                    target_still_alive = False
                    for p in self.game_inst.alive:
                        if p.name == target.name:
                            target_still_alive = True
                            break
                    
                    if not target_still_alive:
                        # Target already eliminated from failed challenge - no need to continue assassination
                        inc()
                        continue
                    
                    # Assassinate - only target can block with Contessa
                    from button_views import BlockView
                    
                    target_discord = self.players[targ_choice]
                    eligible_player_ids = [target_discord.id]
                    blocker = None
                    
                    block_emb = discord.Embed(
                        title="🛡️ Block Opportunity",
                        description=f"**{target.name}**, you are being **Assassinated** by **{self.game_inst.alive[self.game_inst.currentPlayer].name}**!",
                        color=COLOR_WARNING
                    )
                    block_emb.add_field(
                        name="Your Options",
                        value="🛡️ **Block with Contessa** - Claim you have Contessa to block\n✋ **Pass** - Accept the assassination",
                        inline=False
                    )
                    block_emb.set_footer(text="Click a button to respond")
                    
                    block_view = BlockView(eligible_player_ids, 'contessa', target_only=True, timeout=120)
                    block_msg = await self.game_channel.send(embed=block_emb, view=block_view)
                    
                    # Wait for response
                    await block_view.wait()
                    
                    if block_view.blocker_id is not None:
                        blocker = self.game_inst.alive[targ_choice]
                        block_emb = discord.Embed(
                            title="🛡️ Block Attempted!",
                            description=f"**{target_discord.name}** claims **Contessa** to block the assassination!",
                            color=COLOR_SUCCESS
                        )
                        await block_msg.edit(embed=block_emb, view=None)
                    
                    passed = False
                    if blocker:
                        self.challenged = self.game_inst.alive[targ_choice]
                        passed = await self.challenge(self.challenged, 4)
                        
                        # If challenge returned None, game ended
                        if passed is None:
                            return
                        
                        # Check if target was eliminated during challenge
                        # Need to find target again in case indices changed
                        target_still_alive = None
                        for i, p in enumerate(self.game_inst.alive):
                            if p.name == target.name:
                                target_still_alive = i
                                break
                        
                        if target_still_alive is None:
                            # Target was eliminated during challenge - assassination already "succeeded" via elimination
                            inc()
                            continue
                    
                    if passed:
                        inc()
                        continue
                    
                    # Re-fetch target to ensure it's still valid (in case of index changes)
                    target_still_alive_idx = None
                    for i, p in enumerate(self.game_inst.alive):
                        if p.name == target.name:
                            target_still_alive_idx = i
                            break
                    
                    if target_still_alive_idx is None:
                        # Target already eliminated - shouldn't happen but safety check
                        inc()
                        continue
                    
                    target = self.game_inst.alive[target_still_alive_idx]
                    
                    succ_emb = discord.Embed(
                        title="🗡️ Assassination Successful!",
                        description=f"**{target.name}** has been assassinated!",
                        color=COLOR_DANGER
                    )
                    succ_emb.add_field(
                        name="Select Card to Lose",
                        value=f"**{target.name}**, choose which card to lose:",
                        inline=False
                    )

                    succ_msg = await self.game_channel.send(embed=succ_emb)
                    # Get valid card indices (cards that aren't -2)
                    valid_card_indices = [i for i in range(len(target.cards)) if target.cards[i] != -2]
                    # Import card loss view
                    from button_views import CardLossView
                    
                    # Build card data
                    target_discord = self.players[[plyr.name for plyr in self.players].index(target.name)]
                    card_data = []
                    for idx, card_val in enumerate(target.cards):
                        if card_val != -2:
                            card_name = GAMECARDS[card_val]
                            card_emoji = CARD_EMOJIS.get(card_name, "🎴")
                            card_data.append((card_val, card_name, card_emoji))
                        else:
                            card_data.append((-2, "Lost", "💔"))
                    
                    # Send card selection prompt (shows only Card A/Card B, no card names)
                    choice_emb = discord.Embed(
                        title="💔 Choose Card to Lose",
                        description=f"**{target.name}**, choose which card to lose.\nUse `/cards` to see which is Card A and Card B.",
                        color=COLOR_DANGER
                    )
                    card_loss_view = CardLossView(target_discord.id, card_data, timeout=60)
                    choice_msg = await self.game_channel.send(embed=choice_emb, view=card_loss_view)
                    
                    # Wait for selection and confirmation
                    await card_loss_view.wait()
                    
                    lose_choice = card_loss_view.choice
                    if lose_choice is None:
                        # Timeout - default to first card
                        lose_choice = next(i for i in range(len(target.cards)) if target.cards[i] != -2)
                    
                    # Update message to show selection was made
                    choice_emb.description = f"**{target.name}** has chosen which card to lose."
                    choice_emb.color = COLOR_SUCCESS
                    try:
                        await choice_msg.edit(embed=choice_emb, view=None)
                    except:
                        pass

                    # Store card value before losing it
                    lost_card_value = target.cards[lose_choice]
                    lost_emb = discord.Embed(
                        title="💔 Card Lost",
                        description=f"**{target.name}** lost **{GAMECARDS[lost_card_value]}**",
                        color=COLOR_DANGER
                    )
                    await self.game_channel.send(embed=lost_emb)

                    self.game_inst.loseCard(target, lose_choice)

                    if target not in self.game_inst.alive:
                        dead_emb = discord.Embed(
                            title="💀 Eliminated",
                            description=f"**{target.name}** has been eliminated from the game!",
                            color=COLOR_DARK
                        )
                        await self.game_channel.send(embed=dead_emb)
                        del self.players[[plyr.name for plyr in self.players].index(target.name)]
                        
                        # Check for victory after elimination
                        if await self.check_victory():
                            return
                        
                        inc()
                        continue
                    inc()
                elif player_choice == 2:
                    # Exchange - Draw 2 cards, choose cards to keep based on current hand size
                    player = self.game_inst.alive[self.game_inst.currentPlayer]
                    current_cards = [c for c in player.cards if c != -2]  # Get actual cards (not dead ones)
                    cards_to_keep = player.numCards  # If 2 cards, keep 2; if 1 card, keep 1
                    
                    # Draw 2 new cards
                    drawn_cards = [self.game_inst.deck.draw(), self.game_inst.deck.draw()]
                    
                    # Combine current cards with drawn cards
                    all_cards = current_cards + drawn_cards
                    
                    # Create exchange view with buttons for card selection
                    current_player_id = self.players[self.game_inst.currentPlayer].id
                    
                    # Store exchange data
                    if not hasattr(self, 'exchange_data'):
                        self.exchange_data = {}
                    exchange_id = f"exchange_{current_player_id}_{id(all_cards)}"
                    self.exchange_data[exchange_id] = {
                        'player_id': current_player_id,
                        'all_cards': all_cards,
                        'cards_to_keep': cards_to_keep,
                        'chosen_indices': [],
                        'chosen_cards': [],
                        'complete': False
                    }
                    
                    class ExchangeView(discord.ui.View):
                        def __init__(self, bot_instance, exchange_key):
                            super().__init__(timeout=300)
                            self.bot = bot_instance
                            self.exchange_key = exchange_key
                            
                            # Create buttons for each card (use numbers instead of card names for privacy)
                            exchange_info = bot_instance.exchange_data[exchange_key]
                            for idx, card_val in enumerate(exchange_info['all_cards']):
                                if idx < 25:  # Discord limit
                                    # Use numbers instead of card names to keep cards private
                                    button_label = f"Card {idx + 1}"
                                    button = discord.ui.Button(
                                        label=button_label,
                                        style=discord.ButtonStyle.secondary,
                                        custom_id=f"{exchange_key}_{idx}"
                                    )
                                    
                                    # Fix closure by creating a proper callback factory
                                    def create_callback(card_idx):
                                        async def callback(interaction: discord.Interaction):
                                            exchange_info = bot_instance.exchange_data[exchange_key]
                                            if interaction.user.id != exchange_info['player_id']:
                                                await interaction.response.send_message("This is not your exchange!", ephemeral=True)
                                                return
                                            
                                            # On first button click by this player, show all cards privately
                                            if not exchange_info.get('cards_shown', False):
                                                exchange_info['cards_shown'] = True
                                                card_list = "\n".join([f"**Card {i+1}:** {GAMECARDS[card_val]}" for i, card_val in enumerate(exchange_info['all_cards'])])
                                                mapping_emb = discord.Embed(
                                                    title="🔄 Your Exchange Options",
                                                    description=f"Choose **{exchange_info['cards_to_keep']} card{'s' if exchange_info['cards_to_keep'] > 1 else ''}** to keep:\n\n{card_list}",
                                                    color=COLOR_PRIMARY
                                                )
                                                await interaction.response.send_message(embed=mapping_emb, ephemeral=True)
                                                return  # Don't select yet, just show mapping
                                            
                                            if card_idx in exchange_info['chosen_indices']:
                                                await interaction.response.send_message("You already selected this card!", ephemeral=True)
                                                return
                                            if len(exchange_info['chosen_indices']) >= exchange_info['cards_to_keep']:
                                                await interaction.response.send_message(f"You've already selected {exchange_info['cards_to_keep']} card{'s' if exchange_info['cards_to_keep'] > 1 else ''}!", ephemeral=True)
                                                return
                                            
                                            exchange_info['chosen_indices'].append(card_idx)
                                            exchange_info['chosen_cards'].append(exchange_info['all_cards'][card_idx])
                                            
                                            if len(exchange_info['chosen_indices']) == exchange_info['cards_to_keep']:
                                                exchange_info['complete'] = True
                                                if exchange_info['cards_to_keep'] == 2:
                                                    await interaction.response.send_message(
                                                        f"✅ Exchange complete! You kept: **{GAMECARDS[exchange_info['chosen_cards'][0]]}** and **{GAMECARDS[exchange_info['chosen_cards'][1]]}**",
                                                        ephemeral=True
                                                    )
                                                else:
                                                    await interaction.response.send_message(
                                                        f"✅ Exchange complete! You kept: **{GAMECARDS[exchange_info['chosen_cards'][0]]}**",
                                                        ephemeral=True
                                                    )
                                            else:
                                                remaining = exchange_info['cards_to_keep'] - len(exchange_info['chosen_indices'])
                                                await interaction.response.send_message(
                                                    f"Selected: **{GAMECARDS[exchange_info['all_cards'][card_idx]]}**\nChoose {remaining} more card{'s' if remaining > 1 else ''}.",
                                                    ephemeral=True
                                                )
                                        return callback
                                    
                                    button.callback = create_callback(idx)
                                    self.add_item(button)
                    
                    exchange_view = ExchangeView(self, exchange_id)
                    
                    # Send public message without showing cards (private info)
                    exchange_emb = discord.Embed(
                        title="🔄 Exchange Cards",
                        description=f"**{self.players[self.game_inst.currentPlayer].name}** is exchanging cards.\nUse the buttons below to select your cards (only you can see them).",
                        color=COLOR_PRIMARY
                    )
                    
                    # Send message with buttons (card names are on buttons, but we'll show full list privately on first click)
                    exchange_msg = await self.game_channel.send(
                        embed=exchange_emb,
                        view=exchange_view
                    )
                    
                    # Store flag for showing cards on first button click
                    exchange_info = self.exchange_data[exchange_id]
                    exchange_info['cards_shown'] = False
                    
                    # Wait for exchange to complete
                    exchange_info = self.exchange_data[exchange_id]
                    timeout_count = 0
                    while not exchange_info['complete'] and timeout_count < 600:  # 5 minute timeout
                        await asyncio.sleep(0.5)
                        timeout_count += 1
                    
                    chosen_indices = exchange_info['chosen_indices']
                    chosen_cards = exchange_info['chosen_cards']
                    
                    # Delete the exchange message to keep cards private
                    try:
                        await exchange_msg.delete()
                    except:
                        pass
                    
                    # If timeout or incomplete, use first N cards as fallback
                    if len(chosen_cards) < cards_to_keep:
                        chosen_indices = list(range(cards_to_keep)) if len(all_cards) >= cards_to_keep else list(range(len(all_cards)))
                        chosen_cards = [all_cards[i] for i in chosen_indices]
                    
                    # Update player's cards
                    # Keep chosen cards, return rest to deck
                    for i, card_val in enumerate(all_cards):
                        if i not in chosen_indices:
                            self.game_inst.deck.add(card_val)
                    
                    # Set player's cards (fill with chosen, then -2 for dead slots)
                    player.cards = chosen_cards + [-2] * (2 - len(chosen_cards))
                    self.game_inst.deck.shuffle()
                    
                    # Confirmation already sent in button callback
                    
                    # Send exchange update to bot owner
                    try:
                        app_info = await self.application_info()
                        owner = app_info.owner
                        if owner:
                            card_a = GAMECARDS[player.cards[0]] if player.cards[0] != -2 else "Lost"
                            card_b = GAMECARDS[player.cards[1]] if len(player.cards) > 1 and player.cards[1] != -2 else "Lost"
                            exchange_info = f"**🔄 Exchange Update**\n\n"
                            exchange_info += f"**{player.name}** exchanged cards!\n"
                            exchange_info += f"  • New Card A: {card_a}\n"
                            if len(player.cards) > 1 and player.cards[1] != -2:
                                exchange_info += f"  • New Card B: {card_b}\n"
                            await owner.send(exchange_info)
                    except Exception:
                        pass
                    
                    inc()
                elif player_choice == 3:
                    # Check if target was eliminated during challenge (e.g., they challenged and lost their last card)
                    target_still_alive = False
                    for p in self.game_inst.alive:
                        if p.name == target.name:
                            target_still_alive = True
                            break
                    
                    if not target_still_alive:
                        # Target already eliminated from failed challenge - no need to continue steal
                        inc()
                        continue
                    
                    # Steal - only target can block with Captain or Ambassador
                    from button_views import BlockView
                    
                    target_discord = self.players[targ_choice]
                    eligible_player_ids = [target_discord.id]
                    blocker = None
                    block_card = None  # 3 for Captain, 2 for Ambassador
                    
                    block_emb = discord.Embed(
                        title="🛡️ Block Opportunity",
                        description=f"**{target.name}**, **{self.game_inst.alive[self.game_inst.currentPlayer].name}** is attempting to **Steal** from you!",
                        color=COLOR_WARNING
                    )
                    block_emb.add_field(
                        name="Your Options",
                        value="⚓ **Block with Captain** - Claim you have Captain\n🤝 **Block with Ambassador** - Claim you have Ambassador\n✋ **Pass** - Accept the steal",
                        inline=False
                    )
                    block_emb.set_footer(text="Click a button to respond")
                    
                    block_view = BlockView(eligible_player_ids, 'steal', target_only=True, timeout=120)
                    block_msg = await self.game_channel.send(embed=block_emb, view=block_view)
                    
                    # Wait for response
                    await block_view.wait()
                    
                    if block_view.blocker_id is not None:
                        blocker = self.game_inst.alive[targ_choice]
                        block_card = block_view.block_card
                        card_name = "Captain" if block_card == 3 else "Ambassador"
                        card_emoji = "⚓" if block_card == 3 else "🤝"
                        block_emb = discord.Embed(
                            title=f"{card_emoji} Block Attempted!",
                            description=f"**{target_discord.name}** claims **{card_name}** to block the steal!",
                            color=COLOR_SUCCESS
                        )
                        await block_msg.edit(embed=block_emb, view=None)
                    
                    passed = False
                    if blocker:
                        self.challenged = blocker
                        passed = await self.challenge(self.challenged, block_card)
                        
                        # If challenge returned None, game ended
                        if passed is None:
                            return

                    if passed:
                        inc()
                        continue

                    self.game_inst.alive[self.game_inst.currentPlayer].coins += min(2, target.coins)
                    target.coins -= min(2, target.coins)

                    #if not passed:
                    #    inc()
                    #    continue
                    #passed = True
                    inc()
                    continue

                elif player_choice == 5:
                    self.game_inst.alive[self.game_inst.currentPlayer].coins += 1
                    inc()
                elif player_choice == 6:
                    # Foreign Aid - anyone can block with Duke
                    from button_views import BlockView
                    
                    eligible_players = [p for i, p in enumerate(self.players) if i != self.game_inst.currentPlayer]
                    eligible_player_ids = [p.id for p in eligible_players]
                    blocker = None
                    
                    block_emb = discord.Embed(
                        title="🛡️ Block Opportunity",
                        description=f"**{self.game_inst.alive[self.game_inst.currentPlayer].name}** is attempting to take **Foreign Aid**!",
                        color=COLOR_WARNING
                    )
                    block_emb.add_field(
                        name="Your Options",
                        value="👑 **Block with Duke** - Claim you have Duke to block\n✋ **Pass** - Let them take the aid",
                        inline=False
                    )
                    block_emb.set_footer(text="All players must pass for Foreign Aid to proceed")
                    
                    block_view = BlockView(eligible_player_ids, 'foreign_aid', target_only=False, timeout=60)
                    block_msg = await self.game_channel.send(embed=block_emb, view=block_view)
                    
                    # Wait for response
                    await block_view.wait()
                    
                    if block_view.blocker_id is not None:
                        # Find the blocker's game object
                        blocker_name = None
                        for p in self.players:
                            if p.id == block_view.blocker_id:
                                blocker_name = p.name
                                break
                        if blocker_name:
                            blocker = self.game_inst.alive[[plyr.name for plyr in self.players].index(blocker_name)]
                            block_emb = discord.Embed(
                                title="👑 Block Attempted!",
                                description=f"**{blocker_name}** claims **Duke** to block Foreign Aid!",
                                color=COLOR_SUCCESS
                            )
                            await block_msg.edit(embed=block_emb, view=None)
                    
                    passed = False
                    if blocker:
                        self.challenged = blocker
                        passed = await self.challenge(self.challenged, 6)
                        
                        # If challenge returned None, game ended
                        if passed is None:
                            return

                        if passed:
                            inc()
                            continue
                    
                    self.game_inst.alive[self.game_inst.currentPlayer].coins += 2
                    inc()
                    
                    passed = True
                elif player_choice == 7:
                    target = self.game_inst.alive[targ_choice]

                    lose_choice = 0

                    succ_emb = discord.Embed(
                        title="💥 Coup Successful!",
                        description=f"**{target.name}** has been couped!",
                        color=COLOR_DANGER
                    )
                    succ_emb.add_field(
                        name="Select Card to Lose",
                        value=f"**{target.name}**, choose which card to lose:",
                        inline=False
                    )
                    succ_msg = await self.game_channel.send(embed=succ_emb)
                    # Get valid card indices (cards that aren't -2)
                    valid_card_indices = [i for i in range(len(target.cards)) if target.cards[i] != -2]
                    # Import card loss view
                    from button_views import CardLossView
                    
                    # Build card data
                    target_discord = self.players[targ_choice]
                    card_data = []
                    for idx, card_val in enumerate(target.cards):
                        if card_val != -2:
                            card_name = GAMECARDS[card_val]
                            card_emoji = CARD_EMOJIS.get(card_name, "🎴")
                            card_data.append((card_val, card_name, card_emoji))
                        else:
                            card_data.append((-2, "Lost", "💔"))
                    
                    # Send card selection prompt (shows only Card A/Card B, no card names)
                    choice_emb = discord.Embed(
                        title="💔 Choose Card to Lose",
                        description=f"**{target.name}**, choose which card to lose.\nUse `/cards` to see which is Card A and Card B.",
                        color=COLOR_DANGER
                    )
                    card_loss_view = CardLossView(target_discord.id, card_data, timeout=60)
                    choice_msg = await self.game_channel.send(embed=choice_emb, view=card_loss_view)
                    
                    # Wait for selection and confirmation
                    await card_loss_view.wait()
                    
                    lose_choice = card_loss_view.choice
                    if lose_choice is None:
                        # Timeout - default to first card
                        lose_choice = next(i for i in range(len(target.cards)) if target.cards[i] != -2)
                    
                    # Update message to show selection was made
                    choice_emb.description = f"**{target.name}** has chosen which card to lose."
                    choice_emb.color = COLOR_SUCCESS
                    try:
                        await choice_msg.edit(embed=choice_emb, view=None)
                    except:
                        pass

                    # Store card value before losing it
                    lost_card_value = target.cards[lose_choice]
                    lost_emb = discord.Embed(
                        title="💔 Card Lost",
                        description=f"**{target.name}** lost **{GAMECARDS[lost_card_value]}**",
                        color=COLOR_DANGER
                    )
                    await self.game_channel.send(embed=lost_emb)

                    self.game_inst.loseCard(target, lose_choice)
                    inc()
                    if target not in self.game_inst.alive:
                        dead_emb = discord.Embed(
                            title="💀 Eliminated",
                            description=f"**{target.name}** has been eliminated from the game!",
                            color=COLOR_DARK
                        )
                        await self.game_channel.send(embed=dead_emb)
                        del self.players[[plyr.name for plyr in self.players].index(target.name)]
                        
                        # Check for victory after elimination
                        if await self.check_victory():
                            return
                        
                        continue
                

    async def challenge(self, challenged, player_choice):
        # Get all players who can challenge (everyone except the challenged player)
        challenged_player_idx = None
        for i, plyr in enumerate(self.players):
            if plyr.name == challenged.name:
                challenged_player_idx = i
                break
        
        # Import challenge view
        from button_views import ChallengeView
        
        eligible_player_ids = [p.id for i, p in enumerate(self.players) if i != challenged_player_idx]
        
        # Create modern challenge embed
        action_name = ALLACTIONS.get(player_choice, "this action")
        challenge_emb = discord.Embed(
            title="⚔️ Challenge Opportunity",
            description=f"**{challenged.name}** claims to have the card for **{action_name}**",
            color=COLOR_WARNING
        )
        challenge_emb.add_field(
            name="Your Options",
            value="**⚔️ Challenge** - Call them out if you think they're bluffing!\n**✋ Pass** - Let the action proceed",
            inline=False
        )
        challenge_emb.set_footer(text="All players must pass for the action to proceed")
        
        # Create challenge view with buttons
        challenge_view = ChallengeView(eligible_player_ids, action_type="action", timeout=60)
        challenge_msg = await self.game_channel.send(embed=challenge_emb, view=challenge_view)
        self.cur_q = challenge_msg.id
        
        # Wait for challenge or all passes
        await challenge_view.wait()
        
        challenger = None
        if challenge_view.challenger_id is not None:
            # Someone challenged
            challenger_discord = next((p for p in self.players if p.id == challenge_view.challenger_id), None)
            if challenger_discord:
                challenger = self.game_inst.alive[self.players.index(challenger_discord)]
                self.challenger = challenger
                challenge_emb = discord.Embed(
                    title="⚔️ Challenge Issued!",
                    description=f"**{challenger_discord.name}** has challenged **{challenged.name}**!",
                    color=COLOR_DANGER
                )
                await challenge_msg.edit(embed=challenge_emb, view=None)
        
        self.cur_q = None
        
        # If no one challenged, everyone passed
        if challenger is None:
            self.challenger = None
            self.challenged = None
            return True
    
        crplyr = challenged
        lose_choice = 0
        if self.challenger:
            test_challenge = self.game_inst.resolveChallenge(self.challenger, challenged, player_choice) 
            if test_challenge:
                # Challenger was wrong - they lose
                # Import card loss view
                from button_views import CardLossView
                
                succ_emb = discord.Embed(
                    title="❌ Challenge Failed!",
                    description=f"**{challenged.name}** had the card! **{self.challenger.name}** was wrong.",
                    color=COLOR_DANGER
                )
                succ_emb.add_field(
                    name="💔 Consequence",
                    value=f"**{self.challenger.name}** must lose a card (choosing privately).",
                    inline=False
                )
                await self.game_channel.send(embed=succ_emb)
                
                # Build card data for button view
                challenger_discord = self.players[[plyr.name for plyr in self.players].index(self.challenger.name)]
                card_data = []
                for idx, card_val in enumerate(self.challenger.cards):
                    if card_val != -2:
                        card_name = GAMECARDS[card_val]
                        card_emoji = CARD_EMOJIS.get(card_name, "🎴")
                        card_data.append((card_val, card_name, card_emoji))
                    else:
                        card_data.append((-2, "Lost", "💔"))
                
                # Send card selection prompt (shows only Card A/Card B, no card names)
                choice_emb = discord.Embed(
                    title="💔 Choose Card to Lose",
                    description=f"**{self.challenger.name}**, choose which card to lose.\nUse `/cards` to see which is Card A and Card B.",
                    color=COLOR_DANGER
                )
                card_loss_view = CardLossView(challenger_discord.id, card_data, timeout=60)
                choice_msg = await self.game_channel.send(embed=choice_emb, view=card_loss_view)
                
                # Wait for card selection and confirmation
                await card_loss_view.wait()
                
                lose_choice = card_loss_view.choice
                if lose_choice is None:
                    # Timeout - default to first card
                    lose_choice = next(i for i in range(len(self.challenger.cards)) if self.challenger.cards[i] != -2)
                
                # Update message to show selection was made
                choice_emb.description = f"**{self.challenger.name}** has chosen which card to lose."
                choice_emb.color = COLOR_SUCCESS
                try:
                    await choice_msg.edit(embed=choice_emb, view=None)
                except:
                    pass

                # Store card value before losing it
                lost_card_value = self.challenger.cards[lose_choice]
                lost_emb = discord.Embed(
                    title="💔 Card Lost",
                    description=f"**{self.challenger.name}** lost **{GAMECARDS[lost_card_value]}**",
                    color=COLOR_DANGER
                )
                await self.game_channel.send(embed=lost_emb)

                self.game_inst.loseCard(self.challenger, lose_choice)

                if self.challenger not in self.game_inst.alive:
                    dead_emb = discord.Embed(
                        title="💀 Eliminated",
                        description=f"**{self.challenger.name}** has been eliminated from the game!",
                        color=COLOR_DARK
                    )
                    await self.game_channel.send(embed=dead_emb)
                    del self.players[[plyr.name for plyr in self.players].index(self.challenger.name)]
                    
                    # Check for victory after elimination
                    if await self.check_victory():
                        return None
                    
                    self.challenger = None
                    self.challenged = None
                    return True  # Action proceeds - challenged player proved they had the card
            else:
                # Challenger was right - challenged loses
                # Import card loss view
                from button_views import CardLossView
                
                succ_emb = discord.Embed(
                    title="✅ Challenge Successful!",
                    description=f"**{challenged.name}** didn't have the card! **{self.challenger.name}** was right.",
                    color=COLOR_SUCCESS
                )
                succ_emb.add_field(
                    name="💔 Consequence",
                    value=f"**{challenged.name}** must lose a card (choosing privately).",
                    inline=False
                )
                await self.game_channel.send(embed=succ_emb)
                
                # Build card data for button view
                challenged_discord = self.players[[plyr.name for plyr in self.players].index(self.challenged.name)]
                card_data = []
                for idx, card_val in enumerate(challenged.cards):
                    if card_val != -2:
                        card_name = GAMECARDS[card_val]
                        card_emoji = CARD_EMOJIS.get(card_name, "🎴")
                        card_data.append((card_val, card_name, card_emoji))
                    else:
                        card_data.append((-2, "Lost", "💔"))
                
                # Send card selection prompt (shows only Card A/Card B, no card names)
                choice_emb = discord.Embed(
                    title="💔 Choose Card to Lose",
                    description=f"**{challenged.name}**, choose which card to lose.\nUse `/cards` to see which is Card A and Card B.",
                    color=COLOR_DANGER
                )
                card_loss_view = CardLossView(challenged_discord.id, card_data, timeout=60)
                choice_msg = await self.game_channel.send(embed=choice_emb, view=card_loss_view)
                
                # Wait for card selection and confirmation
                await card_loss_view.wait()
                
                lose_choice = card_loss_view.choice
                if lose_choice is None:
                    # Timeout - default to first card
                    lose_choice = next(i for i in range(len(challenged.cards)) if challenged.cards[i] != -2)
                
                # Update message to show selection was made
                choice_emb.description = f"**{challenged.name}** has chosen which card to lose."
                choice_emb.color = COLOR_SUCCESS
                try:
                    await choice_msg.edit(embed=choice_emb, view=None)
                except:
                    pass

                # Store card value before losing it
                lost_card_value = challenged.cards[lose_choice]
                lost_card_name = GAMECARDS[lost_card_value]
                lost_card_emoji = CARD_EMOJIS.get(lost_card_name, "🎴")
                lost_emb = discord.Embed(
                    title="💔 Card Lost",
                    description=f"**{challenged.name}** lost {lost_card_emoji} **{lost_card_name}**",
                    color=COLOR_DANGER
                )
                await self.game_channel.send(embed=lost_emb)

                self.game_inst.loseCard(challenged, lose_choice)

                if crplyr not in self.game_inst.alive:
                    dead_emb = discord.Embed(
                        title="💀 Eliminated",
                        description=f"**{crplyr.name}** has been eliminated from the game!",
                        color=COLOR_DARK
                    )
                    await self.game_channel.send(embed=dead_emb)
                    del self.players[[plyr.name for plyr in self.players].index(crplyr.name)]
                    
                    # Check for victory after elimination
                    if await self.check_victory():
                        return None  # Return None to indicate game ended

                self.challenger = None
                self.challenged = None
                return False

        self.challenger = None
        self.challenged = None
        return True
    
    async def show_status(self):
        """Display current game status with all players"""
        stat_str = ''
        for i, plyr in enumerate(self.game_inst.alive):
            # Show position, name, influence, and coins
            cards_emoji = "❤️" * plyr.numCards + "💔" * (2 - plyr.numCards)
            coins_display = "💰" * min(plyr.coins, 10) if plyr.coins <= 10 else f"💰×{plyr.coins}"
            stat_str += f'**{i+1}.** **{plyr.name}**\n'
            stat_str += f'   {cards_emoji} **{plyr.numCards}** influence • {coins_display} **{plyr.coins}** coins\n\n'
        
        status_emb = discord.Embed(
            title='📊 Game Status',
            description=stat_str or "No players alive",
            color=COLOR_INFO
        )
        status_emb.set_footer(text=f"{len(self.game_inst.alive)} player{'s' if len(self.game_inst.alive) != 1 else ''} remaining")
        await self.game_channel.send(embed=status_emb)

    # Helper method to get player cards (used by both message and slash commands)
    def get_player_cards_embed(self, user_id):
        """Get the cards embed for a player. Returns (embed, success_message, error_embed)"""
        if not self.game_running or not self.game_inst:
            return None, None, discord.Embed(
                title="❌ No Game Running",
                description="There is no game currently running! Use `c!start` to start a game.",
                color=COLOR_PRIMARY
            )
        
        # Find the player in the game
        player_idx = None
        for i, plyr in enumerate(self.players):
            if plyr.id == user_id:
                player_idx = i
                break
        
        if player_idx is None or player_idx >= len(self.game_inst.alive):
            return None, None, discord.Embed(
                title="❌ Not in Game",
                description="You are not part of the current game!",
                color=COLOR_WARNING
            )
        
        # Get player's cards
        player = self.game_inst.alive[player_idx]
        # Check each card slot independently (don't rely on numCards for index checking)
        card_a_val = player.cards[0] if player.cards[0] != -2 else None
        card_b_val = player.cards[1] if len(player.cards) > 1 and player.cards[1] != -2 else None
        
        card_text = ""
        if card_a_val is not None:
            card_a_name = GAMECARDS[card_a_val]
            card_a_emoji = CARD_EMOJIS.get(card_a_name, "🎴")
            card_text += f"🅰 {card_a_emoji} **{card_a_name}**"
        if card_b_val is not None:
            card_b_name = GAMECARDS[card_b_val]
            card_b_emoji = CARD_EMOJIS.get(card_b_name, "🎴")
            card_text += f"\n🅱 {card_b_emoji} **{card_b_name}**"
        
        card_emb = discord.Embed(
            title="🃏 Your Cards",
            description=card_text or "No cards found (this shouldn't happen!)",
            color=COLOR_INFO
        )
        card_emb.add_field(
            name="Status",
            value=f"**{player.numCards}** card{'s' if player.numCards != 1 else ''} | **{player.coins}** coin{'s' if player.coins != 1 else ''}",
            inline=False
        )
        card_emb.set_footer(text=f"Only you can see this message")
        
        return card_emb, None, None

# Health check server for Render deployment
import threading
from flask import Flask
import logging

# Suppress Flask's default logging to avoid spam
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

@app.route('/')
def home():
    return 'Coup Discord Bot is running!', 200

@app.route('/health')
def health():
    return {'status': 'healthy', 'bot': 'online'}, 200

def run_flask():
    try:
        port = int(os.getenv('PORT', 10000))
        print(f'[HEALTH] Starting Flask server on port {port}')
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        print(f'[HEALTH] Flask server error: {e}')

# Start Flask in background thread
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()
print(f'[HEALTH] Flask thread started, listening on port {os.getenv("PORT", 10000)}')

client = GameClient()

# Create slash command for cards (ephemeral - only visible to user)
@client.tree.command(name="cards", description="View your current cards (only visible to you)")
async def cards_command(interaction: discord.Interaction):
    """Slash command to show player's cards with ephemeral response"""
    embed, _, error_embed = client.get_player_cards_embed(interaction.user.id)
    if error_embed:
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

client.run(token)





