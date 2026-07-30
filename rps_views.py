"""
Rock Paper Scissors Game Module for Discord Bot
Allows users to challenge each other to Rock, Paper, Scissors.
Sends secret DM notification to bot owner when a player makes a move.
Includes ELO Rating System and dedicated RPS Leaderboard.
"""

import discord
from discord.ui import View, Button
from typing import Optional
import json

COLOR_PRIMARY = 0x8B4513
COLOR_SUCCESS = 0x2ECC71
COLOR_DANGER = 0xE74C3C
COLOR_INFO = 0x3498DB
COLOR_WARNING = 0xF39C12
COLOR_GOLD = 0xD4AF37

EMOJIS = {
    "rock": "🪨",
    "paper": "📄",
    "scissors": "✂️"
}

BEATS = {
    "rock": "scissors",
    "paper": "rock",
    "scissors": "paper"
}

# ============================================================================
# RPS ELO & LEADERBOARD DATA SYSTEM
# ============================================================================

RPS_DATA_FILE = "rps_leaderboard.json"

def load_rps_data():
    """Load RPS leaderboard data from JSON file"""
    try:
        with open(RPS_DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_rps_data(data):
    """Save RPS leaderboard data to JSON file"""
    with open(RPS_DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_rank_tier(rating: int) -> tuple[str, str]:
    """Returns (Tier Name, Emoji Badge) based on ELO rating"""
    if rating >= 1600:
        return "Grandmaster", "👑"
    elif rating >= 1450:
        return "Master", "💎"
    elif rating >= 1300:
        return "Gold", "🥇"
    elif rating >= 1150:
        return "Silver", "🥈"
    else:
        return "Bronze", "🥉"

def calculate_elo(r1: float, r2: float, outcome: str, k: float = 32.0):
    """
    Calculate ELO Rating change for two players.
    outcome: "p1" (p1 won), "p2" (p2 won), or "tie"
    Returns (new_r1, new_r2, delta1, delta2)
    """
    if outcome == "p1":
        score1 = 1.0
    elif outcome == "p2":
        score1 = 0.0
    else:
        score1 = 0.5

    expected1 = 1.0 / (1.0 + 10.0 ** ((r2 - r1) / 400.0))
    expected2 = 1.0 - expected1
    score2 = 1.0 - score1

    delta1 = int(round(k * (score1 - expected1)))
    delta2 = int(round(k * (score2 - expected2)))

    # Ensure minimum 1 ELO point change on win/loss
    if outcome == "p1" and delta1 <= 0:
        delta1, delta2 = 1, -1
    elif outcome == "p2" and delta2 <= 0:
        delta2, delta1 = 1, -1

    new_r1 = max(100, int(r1 + delta1))
    new_r2 = max(100, int(r2 + delta2))

    return new_r1, new_r2, delta1, delta2

def update_rps_stats(guild_id: int, p1_id: int, p2_id: int, outcome: str):
    """
    Updates player stats & ratings in rps_leaderboard.json
    outcome: "p1" | "p2" | "tie"
    Returns dict with rating change details
    """
    data = load_rps_data()
    str_gid = str(guild_id)
    if str_gid not in data:
        data[str_gid] = {}

    guild_data = data[str_gid]
    str_p1, str_p2 = str(p1_id), str(p2_id)

    default_player = {
        "rating": 1200,
        "wins": 0,
        "losses": 0,
        "ties": 0,
        "streak": 0,
        "best_streak": 0
    }

    if str_p1 not in guild_data:
        guild_data[str_p1] = dict(default_player)
    if str_p2 not in guild_data:
        guild_data[str_p2] = dict(default_player)

    p1_stats = guild_data[str_p1]
    p2_stats = guild_data[str_p2]

    old_r1 = p1_stats.get("rating", 1200)
    old_r2 = p2_stats.get("rating", 1200)

    new_r1, new_r2, delta1, delta2 = calculate_elo(old_r1, old_r2, outcome)

    p1_stats["rating"] = new_r1
    p2_stats["rating"] = new_r2

    if outcome == "p1":
        p1_stats["wins"] = p1_stats.get("wins", 0) + 1
        p2_stats["losses"] = p2_stats.get("losses", 0) + 1

        p1_stats["streak"] = (p1_stats.get("streak", 0) if p1_stats.get("streak", 0) > 0 else 0) + 1
        p1_stats["best_streak"] = max(p1_stats.get("best_streak", 0), p1_stats["streak"])

        p2_stats["streak"] = (p2_stats.get("streak", 0) if p2_stats.get("streak", 0) < 0 else 0) - 1

    elif outcome == "p2":
        p2_stats["wins"] = p2_stats.get("wins", 0) + 1
        p1_stats["losses"] = p1_stats.get("losses", 0) + 1

        p2_stats["streak"] = (p2_stats.get("streak", 0) if p2_stats.get("streak", 0) > 0 else 0) + 1
        p2_stats["best_streak"] = max(p2_stats.get("best_streak", 0), p2_stats["streak"])

        p1_stats["streak"] = (p1_stats.get("streak", 0) if p1_stats.get("streak", 0) < 0 else 0) - 1

    else: # tie
        p1_stats["ties"] = p1_stats.get("ties", 0) + 1
        p2_stats["ties"] = p2_stats.get("ties", 0) + 1

    save_rps_data(data)

    return {
        "p1_old": old_r1, "p1_new": new_r1, "p1_delta": delta1,
        "p2_old": old_r2, "p2_new": new_r2, "p2_delta": delta2
    }

async def get_rps_leaderboard_embed(bot, guild_id: int):
    """Builds and returns a formatted RPS ELO Leaderboard embed"""
    data = load_rps_data()
    str_gid = str(guild_id)

    if str_gid not in data or not data[str_gid]:
        return discord.Embed(
            title="🎮 Rock Paper Scissors Leaderboard",
            description="No RPS games have been recorded in this server yet!\n\nUse `c!rps` to start the first match!",
            color=COLOR_INFO
        )

    guild_data = data[str_gid]

    # Sort key: ELO Rating (descending), then Win Rate (descending), then Wins
    def sort_key(item):
        stats = item[1]
        rating = stats.get("rating", 1200)
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        ties = stats.get("ties", 0)
        total = wins + losses + ties
        wr = (wins / total) if total > 0 else 0
        return (rating, wr, wins)

    sorted_players = sorted(guild_data.items(), key=sort_key, reverse=True)

    embed = discord.Embed(
        title="⚔️ Rock Paper Scissors Leaderboard",
        description="Server ELO Rating & Champion Standings",
        color=COLOR_GOLD
    )

    lb_text = ""
    medals = ["🥇", "🥈", "🥉"]

    for idx, (uid_str, stats) in enumerate(sorted_players[:10]):
        uid = int(uid_str)
        user = bot.get_user(uid)
        if not user:
            try:
                user = await bot.fetch_user(uid)
            except Exception:
                user = None

        username = user.display_name if user else f"User {uid_str}"
        rank_num = medals[idx] if idx < 3 else f"**{idx + 1}.**"

        rating = stats.get("rating", 1200)
        tier_name, tier_emoji = get_rank_tier(rating)
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        ties = stats.get("ties", 0)
        streak = stats.get("streak", 0)
        total = wins + losses + ties
        win_rate = (wins / total * 100) if total > 0 else 0.0

        streak_str = f"🔥 {streak} W" if streak > 0 else (f"❄️ {abs(streak)} L" if streak < 0 else "➖")

        lb_text += f"{rank_num} **{username}** • {tier_emoji} **{rating}** ELO ({tier_name})\n"
        lb_text += f"   W: **{wins}** • L: **{losses}** • T: **{ties}** • WR: **{win_rate:.1f}%** • Streak: {streak_str}\n\n"

    embed.add_field(name="Top RPS Duellists", value=lb_text or "No active players yet.", inline=False)
    embed.set_footer(text="Play RPS with c!rps or /rps to climb the rankings!")
    return embed


# ============================================================================
# RPS DISCORD VIEWS
# ============================================================================

class RPSChallengeView(View):
    """View shown when a player challenges another player to RPS"""
    def __init__(self, bot, challenger: discord.User, challenged: Optional[discord.User] = None):
        super().__init__(timeout=120)
        self.bot = bot
        self.challenger = challenger
        self.challenged = challenged
        self.accepted = False
        self.message = None

    @discord.ui.button(label="Accept Challenge ⚔️", style=discord.ButtonStyle.success, custom_id="rps_accept")
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        # If specific user challenged, only they can accept
        if self.challenged and interaction.user.id != self.challenged.id:
            await interaction.response.send_message("❌ This challenge was specifically for someone else!", ephemeral=True)
            return

        # Cannot accept own challenge
        if interaction.user.id == self.challenger.id:
            await interaction.response.send_message("❌ You cannot accept your own challenge!", ephemeral=True)
            return

        self.accepted = True
        self.challenged = interaction.user
        
        # Stop challenge view timeout
        self.stop()

        # Create active game view
        game_view = RPSGameView(self.bot, self.challenger, self.challenged)
        embed = game_view.build_game_embed()
        
        await interaction.response.edit_message(embed=embed, view=game_view)
        game_view.message = interaction.message

    @discord.ui.button(label="Decline ❌", style=discord.ButtonStyle.danger, custom_id="rps_decline")
    async def decline_button(self, interaction: discord.Interaction, button: Button):
        if self.challenged and interaction.user.id != self.challenged.id and interaction.user.id != self.challenger.id:
            await interaction.response.send_message("❌ Only the challenger or challenged player can decline/cancel!", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True

        embed = discord.Embed(
            title="🚫 Challenge Declined",
            description=f"**{interaction.user.display_name}** declined or cancelled the Rock, Paper, Scissors challenge.",
            color=COLOR_DANGER
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                embed = discord.Embed(
                    title="⏰ Challenge Expired",
                    description=f"The RPS challenge from **{self.challenger.display_name}** expired.",
                    color=COLOR_WARNING
                )
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass


class RPSGameView(View):
    """Active game view for picking Rock, Paper, or Scissors"""
    def __init__(self, bot, challenger: discord.User, challenged: discord.User):
        super().__init__(timeout=180)
        self.bot = bot
        self.challenger = challenger
        self.challenged = challenged
        self.choices = {}  # user_id -> "rock" | "paper" | "scissors"
        self.message = None

    def build_game_embed(self):
        p1_status = "✅ Choice Locked" if self.challenger.id in self.choices else "⏳ Waiting for pick..."
        p2_status = "✅ Choice Locked" if self.challenged.id in self.choices else "⏳ Waiting for pick..."

        embed = discord.Embed(
            title="⚔️ Rock, Paper, Scissors Match",
            description=(
                f"**{self.challenger.mention}** vs **{self.challenged.mention}**\n\n"
                f"Click your choice below! Your pick is kept completely secret until both players choose.\n\n"
                f"**Status:**\n"
                f"• **{self.challenger.display_name}**: {p1_status}\n"
                f"• **{self.challenged.display_name}**: {p2_status}"
            ),
            color=COLOR_INFO
        )
        embed.set_footer(text="Rock Paper Scissors • May the best move win!")
        return embed

    async def handle_choice(self, interaction: discord.Interaction, choice: str):
        user = interaction.user

        # Only participants can choose
        if user.id not in (self.challenger.id, self.challenged.id):
            await interaction.response.send_message("❌ You are not a participant in this match!", ephemeral=True)
            return

        # Check if already picked
        if user.id in self.choices:
            await interaction.response.send_message("ℹ️ You have already made your pick! Waiting for opponent...", ephemeral=True)
            return

        # Record choice
        self.choices[user.id] = choice
        choice_emoji = EMOJIS[choice]

        # Ephemeral confirmation to player
        await interaction.response.send_message(f"✅ You picked {choice_emoji} **{choice.upper()}**! Waiting for opponent...", ephemeral=True)

        # Notify owner DM
        await self.notify_owner(interaction, user, choice)

        # Check if both have picked
        if len(self.choices) == 2:
            await self.resolve_game(interaction)
        else:
            # Update embed to reflect 1 choice locked in
            embed = self.build_game_embed()
            await interaction.message.edit(embed=embed, view=self)

    async def notify_owner(self, interaction: discord.Interaction, player: discord.User, choice: str):
        """Send secret DM to bot owner with player's choice"""
        try:
            owner = await self.bot.get_owner_user()
            if owner:
                choice_emoji = EMOJIS.get(choice, "❓")
                guild_name = interaction.guild.name if interaction.guild else "Direct Message"
                channel_name = interaction.channel.name if hasattr(interaction.channel, 'name') else "DM"

                dm_embed = discord.Embed(
                    title="🤫 RPS Secret Move Alert",
                    description=(
                        f"👤 **Player:** {player.mention} (`{player.name}` | ID: `{player.id}`)\n"
                        f"🎯 **Pick:** {choice_emoji} **{choice.upper()}**\n\n"
                        f"⚔️ **Match:** {self.challenger.display_name} vs {self.challenged.display_name}\n"
                        f"🌐 **Server:** {guild_name}\n"
                        f"💬 **Channel:** #{channel_name}"
                    ),
                    color=COLOR_WARNING
                )
                await owner.send(embed=dm_embed)
        except Exception as e:
            print(f"[RPS Owner DM Error] {e}")

    async def resolve_game(self, interaction: discord.Interaction):
        p1_choice = self.choices[self.challenger.id]
        p2_choice = self.choices[self.challenged.id]

        p1_emoji = EMOJIS[p1_choice]
        p2_emoji = EMOJIS[p2_choice]

        if p1_choice == p2_choice:
            outcome = "tie"
            result_title = "🤝 It's a Tie!"
            result_desc = (
                f"Both **{self.challenger.display_name}** and **{self.challenged.display_name}** chose {p1_emoji} **{p1_choice.upper()}**!\n\n"
                f"It's a draw!"
            )
            winner_color = COLOR_INFO
        elif BEATS[p1_choice] == p2_choice:
            outcome = "p1"
            result_title = f"🏆 {self.challenger.display_name} Wins!"
            result_desc = (
                f"**{self.challenger.display_name}** chose {p1_emoji} **{p1_choice.upper()}**\n"
                f"**{self.challenged.display_name}** chose {p2_emoji} **{p2_choice.upper()}**\n\n"
                f"✨ {p1_emoji} **{p1_choice.upper()}** beats {p2_emoji} **{p2_choice.upper()}**!"
            )
            winner_color = COLOR_GOLD
        else:
            outcome = "p2"
            result_title = f"🏆 {self.challenged.display_name} Wins!"
            result_desc = (
                f"**{self.challenged.display_name}** chose {p2_emoji} **{p2_choice.upper()}**\n"
                f"**{self.challenger.display_name}** chose {p1_emoji} **{p1_choice.upper()}**\n\n"
                f"✨ {p2_emoji} **{p2_choice.upper()}** beats {p1_emoji} **{p1_choice.upper()}**!"
            )
            winner_color = COLOR_GOLD

        # Update ELO and leaderboard if played in a guild server
        elo_text = ""
        if interaction.guild:
            elo_data = update_rps_stats(interaction.guild.id, self.challenger.id, self.challenged.id, outcome)
            p1_sign = f"+{elo_data['p1_delta']}" if elo_data['p1_delta'] >= 0 else f"{elo_data['p1_delta']}"
            p2_sign = f"+{elo_data['p2_delta']}" if elo_data['p2_delta'] >= 0 else f"{elo_data['p2_delta']}"
            
            p1_tier_name, p1_tier_emoji = get_rank_tier(elo_data['p1_new'])
            p2_tier_name, p2_tier_emoji = get_rank_tier(elo_data['p2_new'])

            elo_text = (
                f"\n\n📊 **Rating Updates:**\n"
                f"• **{self.challenger.display_name}**: **{elo_data['p1_new']}** ELO ({p1_sign}) {p1_tier_emoji}\n"
                f"• **{self.challenged.display_name}**: **{elo_data['p2_new']}** ELO ({p2_sign}) {p2_tier_emoji}"
            )

        embed = discord.Embed(
            title=result_title,
            description=result_desc + elo_text,
            color=winner_color
        )
        embed.set_footer(text="Thanks for playing Rock Paper Scissors! Use c!rps or /rps to play again.")

        rematch_view = RPSRematchView(self.bot, self.challenger, self.challenged)
        await interaction.message.edit(embed=embed, view=rematch_view)
        self.stop()

    @discord.ui.button(label="Rock", style=discord.ButtonStyle.primary, emoji="🪨", custom_id="rps_rock")
    async def rock_button(self, interaction: discord.Interaction, button: Button):
        await self.handle_choice(interaction, "rock")

    @discord.ui.button(label="Paper", style=discord.ButtonStyle.primary, emoji="📄", custom_id="rps_paper")
    async def paper_button(self, interaction: discord.Interaction, button: Button):
        await self.handle_choice(interaction, "paper")

    @discord.ui.button(label="Scissors", style=discord.ButtonStyle.primary, emoji="✂️", custom_id="rps_scissors")
    async def scissors_button(self, interaction: discord.Interaction, button: Button):
        await self.handle_choice(interaction, "scissors")


class RPSRematchView(View):
    """View shown after game finishes with a Rematch button"""
    def __init__(self, bot, p1: discord.User, p2: discord.User):
        super().__init__(timeout=120)
        self.bot = bot
        self.p1 = p1
        self.p2 = p2

    @discord.ui.button(label="Play Again 🔄", style=discord.ButtonStyle.success, custom_id="rps_rematch")
    async def rematch_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in (self.p1.id, self.p2.id):
            await interaction.response.send_message("❌ Only players from the previous match can trigger a rematch!", ephemeral=True)
            return

        challenger = interaction.user
        challenged = self.p2 if challenger.id == self.p1.id else self.p1

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        challenge_view = RPSChallengeView(self.bot, challenger, challenged)
        embed = discord.Embed(
            title="🎮 Rock, Paper, Scissors Rematch!",
            description=f"**{challenger.mention}** wants a rematch against **{challenged.mention}**!\n\nClick below to accept!",
            color=COLOR_INFO
        )
        msg = await interaction.channel.send(embed=embed, view=challenge_view)
        challenge_view.message = msg
        self.stop()
