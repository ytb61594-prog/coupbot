"""
Rock Paper Scissors Game Module for Discord Bot
Allows users to challenge each other to Rock, Paper, Scissors.
Sends secret DM notification to bot owner when a player makes a move.
"""

import discord
from discord.ui import View, Button
from typing import Optional

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
            result_title = "🤝 It's a Tie!"
            result_desc = (
                f"Both **{self.challenger.display_name}** and **{self.challenged.display_name}** chose {p1_emoji} **{p1_choice.upper()}**!\n\n"
                f"It's a draw!"
            )
            winner_color = COLOR_INFO
        elif BEATS[p1_choice] == p2_choice:
            result_title = f"🏆 {self.challenger.display_name} Wins!"
            result_desc = (
                f"**{self.challenger.display_name}** chose {p1_emoji} **{p1_choice.upper()}**\n"
                f"**{self.challenged.display_name}** chose {p2_emoji} **{p2_choice.upper()}**\n\n"
                f"✨ {p1_emoji} **{p1_choice.upper()}** beats {p2_emoji} **{p2_choice.upper()}**!"
            )
            winner_color = COLOR_GOLD
        else:
            result_title = f"🏆 {self.challenged.display_name} Wins!"
            result_desc = (
                f"**{self.challenged.display_name}** chose {p2_emoji} **{p2_choice.upper()}**\n"
                f"**{self.challenger.display_name}** chose {p1_emoji} **{p1_choice.upper()}**\n\n"
                f"✨ {p2_emoji} **{p2_choice.upper()}** beats {p1_emoji} **{p1_choice.upper()}**!"
            )
            winner_color = COLOR_GOLD

        embed = discord.Embed(
            title=result_title,
            description=result_desc,
            color=winner_color
        )
        embed.set_footer(text="Thanks for playing Rock Paper Scissors! Use c!rps to play again.")

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
