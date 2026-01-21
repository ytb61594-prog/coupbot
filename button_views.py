"""
Discord UI Button Views for Coup Bot
All button-based interactions for a modern, polished experience
"""

import discord
from discord.ui import Button, View, Select
from typing import Optional, List, Callable
import asyncio

# ============================================================================
# LOBBY VIEW - Join and Start Game
# ============================================================================

class LobbyView(View):
    """Lobby with Join and Start buttons"""
    
    def __init__(self, bot_instance, host_id: int):
        super().__init__(timeout=None)  # No timeout for lobby
        self.bot = bot_instance
        self.host_id = host_id
        self.started = False
        
    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.success, emoji="✅", custom_id="lobby_join")
    async def join_button(self, interaction: discord.Interaction, button: Button):
        """Player joins the game"""
        if self.started:
            await interaction.response.send_message("❌ Game has already started!", ephemeral=True)
            return
            
        user = interaction.user
        
        # Check if already in game
        if user in self.bot.players:
            await interaction.response.send_message("ℹ️ You're already in the game!", ephemeral=True)
            return
        
        # Check max players
        if len(self.bot.players) >= 6:
            await interaction.response.send_message("❌ Game is full (6 players max)!", ephemeral=True)
            return
        
        # Add player to bot's player list and game instance
        self.bot.players.append(user)
        self.bot.player_count += 1
        self.bot.game_inst.addPlayer(user.name)
        self.bot.all_original_players.append(user)
        self.bot.joined_player_ids.add(user.id)
        
        # Update lobby embed
        player_list = "\n".join([f"**{i+1}.** {p.mention}" for i, p in enumerate(self.bot.players)])
        
        embed = interaction.message.embeds[0]
        embed.clear_fields()
        embed.add_field(
            name=f"🎭 Players ({len(self.bot.players)}/6)",
            value=player_list,
            inline=False
        )
        embed.set_footer(text=f"Waiting for host to start • {len(self.bot.players)} player{'s' if len(self.bot.players) != 1 else ''} joined")
        
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ {user.mention} joined the game!", ephemeral=False)
    
    @discord.ui.button(label="Start Game", style=discord.ButtonStyle.primary, emoji="▶️", custom_id="lobby_start")
    async def start_button(self, interaction: discord.Interaction, button: Button):
        """Host starts the game"""
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("❌ Only the host can start the game!", ephemeral=True)
            return
        
        if len(self.bot.players) < 2:
            await interaction.response.send_message("❌ Need at least 2 players to start!", ephemeral=True)
            return
        
        self.started = True
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        # Update embed
        embed = interaction.message.embeds[0]
        embed.title = "🎲 Game Starting!"
        embed.color = 0x2ECC71  # COLOR_SUCCESS
        embed.set_footer(text="Game is starting • Good luck!")
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Signal bot to start game
        self.stop()

# ============================================================================
# ACTION SELECTION VIEW - Choose Your Action
# ============================================================================

class ActionView(View):
    """View for selecting actions during a turn"""
    
    def __init__(self, bot_instance, player_id: int, available_actions: List[int], action_names: dict, action_icons: dict, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.bot = bot_instance
        self.player_id = player_id
        self.choice = None
        
        # Use passed dictionaries instead of importing
        ALLACTIONS = action_names
        ACTION_ICONS = action_icons
        
        # Create buttons for each available action
        for action_num in available_actions:
            action_name = ALLACTIONS.get(action_num, "Unknown")
            action_icon = ACTION_ICONS.get(action_num, "❔")
            
            # Determine button style based on action type
            if action_num == 6:  # Coup
                style = discord.ButtonStyle.danger
            elif action_num in [1, 4]:  # Tax, Steal
                style = discord.ButtonStyle.success
            elif action_num in [2, 5]:  # Assassinate, Exchange
                style = discord.ButtonStyle.primary
            else:  # Income, Foreign Aid
                style = discord.ButtonStyle.secondary
            
            button = Button(
                label=action_name,
                emoji=action_icon,
                style=style,
                custom_id=f"action_{action_num}"
            )
            button.callback = self.make_action_callback(action_num)
            self.add_item(button)
    
    def make_action_callback(self, action_num: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player_id:
                await interaction.response.send_message("❌ This is not your turn!", ephemeral=True)
                return
            
            self.choice = action_num
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(view=self)
            self.stop()
        
        return callback
    
    async def on_timeout(self):
        # Disable all buttons on timeout
        for item in self.children:
            item.disabled = True

# ============================================================================
# TARGET SELECTION VIEW - Choose Your Target
# ============================================================================

class TargetView(View):
    """View for selecting a target player"""
    
    def __init__(self, bot_instance, player_id: int, targets: List[tuple], timeout: float = 120):
        super().__init__(timeout=timeout)
        self.bot = bot_instance
        self.player_id = player_id
        self.choice = None
        
        # Create buttons for each target
        for idx, (target_idx, target_name, target_coins, target_cards) in enumerate(targets):
            button = Button(
                label=f"{target_name} • 💰{target_coins} • ❤️{target_cards}",
                style=discord.ButtonStyle.secondary,
                custom_id=f"target_{target_idx}",
                row=idx // 5  # Discord allows max 5 buttons per row
            )
            button.callback = self.make_target_callback(target_idx)
            self.add_item(button)
    
    def make_target_callback(self, target_idx: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player_id:
                await interaction.response.send_message("❌ This is not your choice!", ephemeral=True)
                return
            
            self.choice = target_idx
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(view=self)
            self.stop()
        
        return callback
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

# ============================================================================
# CHALLENGE/BLOCK VIEW - Challenge or Pass
# ============================================================================

class ChallengeView(View):
    """View for challenging or passing on an action"""
    
    def __init__(self, eligible_players: List[int], action_type: str = "action", timeout: float = 60):
        super().__init__(timeout=timeout)
        self.eligible_players = eligible_players
        self.action_type = action_type  # "action" or "block"
        self.challenger_id = None
        self.passed_players = set()
        
    @discord.ui.button(label="Challenge!", style=discord.ButtonStyle.danger, emoji="⚔️", custom_id="challenge")
    async def challenge_button(self, interaction: discord.Interaction, button: Button):
        """Player challenges the action/block"""
        if interaction.user.id not in self.eligible_players:
            await interaction.response.send_message("❌ You cannot challenge this!", ephemeral=True)
            return
        
        if interaction.user.id in self.passed_players:
            await interaction.response.send_message("❌ You already passed!", ephemeral=True)
            return
        
        if self.challenger_id is not None:
            await interaction.response.send_message("❌ Someone already challenged!", ephemeral=True)
            return
        
        self.challenger_id = interaction.user.id
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"⚔️ **{interaction.user.mention} challenges!**")
        self.stop()
    
    @discord.ui.button(label="Pass", style=discord.ButtonStyle.secondary, emoji="✋", custom_id="pass")
    async def pass_button(self, interaction: discord.Interaction, button: Button):
        """Player passes on challenging"""
        if interaction.user.id not in self.eligible_players:
            await interaction.response.send_message("❌ You are not involved in this!", ephemeral=True)
            return
        
        if interaction.user.id in self.passed_players:
            await interaction.response.send_message("ℹ️ You already passed!", ephemeral=True)
            return
        
        self.passed_players.add(interaction.user.id)
        
        await interaction.response.send_message(f"✋ You passed on challenging.", ephemeral=True)
        
        # Check if all players passed
        if len(self.passed_players) >= len(self.eligible_players):
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.message.edit(view=self)
            self.stop()
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

# ============================================================================
# CARD LOSS SELECTION VIEW - Choose Which Card to Lose
# ============================================================================

class CardLossView(View):
    """View for selecting which card to lose - shows only Card A/B labels"""
    
    def __init__(self, player_id: int, cards: List[tuple], timeout: float = 60):
        super().__init__(timeout=timeout)
        self.player_id = player_id
        self.choice = None
        self.cards = cards  # Store cards for confirmation
        self.confirmed = False
        
        # Create buttons for each card - ONLY show Card A/Card B labels
        labels = ['Card A', 'Card B']
        label_emojis = ['🅰', '🅱']
        for idx, (card_value, card_name, card_emoji) in enumerate(cards):
            if card_value != -2:  # Only show alive cards
                button = Button(
                    label=labels[idx],
                    emoji=label_emojis[idx],
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"lose_card_{idx}"
                )
                button.callback = self.make_loss_callback(idx, card_name, card_emoji)
                self.add_item(button)
    
    def make_loss_callback(self, card_idx: int, card_name: str, card_emoji: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.player_id:
                await interaction.response.send_message("❌ This is not your choice!", ephemeral=True)
                return
            
            # Show ephemeral confirmation with actual card name (only player sees this)
            label = "Card A" if card_idx == 0 else "Card B"
            confirm_view = ConfirmCardLossView(self, card_idx)
            
            await interaction.response.send_message(
                f"⚠️ **Are you sure you want to lose {label} ({card_emoji} {card_name})?**",
                view=confirm_view,
                ephemeral=True
            )
        
        return callback
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

# Confirmation view for card loss
class ConfirmCardLossView(View):
    """Confirmation buttons for card loss (ephemeral)"""
    
    def __init__(self, parent_view: CardLossView, card_idx: int):
        super().__init__(timeout=30)
        self.parent_view = parent_view
        self.card_idx = card_idx
    
    @discord.ui.button(label="Yes, Lose This Card", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.parent_view.player_id:
            await interaction.response.send_message("❌ This is not your choice!", ephemeral=True)
            return
        
        # Confirm the choice
        self.parent_view.choice = self.card_idx
        self.parent_view.confirmed = True
        
        # Disable all buttons in both views
        for item in self.children:
            item.disabled = True
        for item in self.parent_view.children:
            item.disabled = True
        
        await interaction.response.edit_message(content="✅ **Card loss confirmed.**", view=self)
        self.parent_view.stop()
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.parent_view.player_id:
            await interaction.response.send_message("❌ This is not your choice!", ephemeral=True)
            return
        
        # Cancel - let them choose again
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(content="❌ **Cancelled.** Click another card to choose.", view=self)
        self.stop()
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

# ============================================================================
# EXCHANGE SELECTION VIEW - Choose Cards to Keep (Already exists in bot.py)
# ============================================================================
# The ExchangeView already exists in bot.py and works well with buttons
# We'll keep that implementation

# ============================================================================
# BLOCK VIEW - Block or Pass on Actions (Button-based)
# ============================================================================

class BlockView(View):
    """View for blocking actions - replaces reaction-based blocking"""
    
    def __init__(self, eligible_player_ids: List[int], block_type: str, target_only: bool = False, timeout: float = 60):
        """
        eligible_player_ids: List of Discord user IDs who can block
        block_type: 'contessa' (assassination), 'steal' (captain/ambassador), 'foreign_aid' (duke)
        target_only: If True, only the target can block (for assassination/steal)
        """
        super().__init__(timeout=timeout)
        self.eligible_player_ids = eligible_player_ids
        self.block_type = block_type
        self.target_only = target_only
        self.blocker_id = None
        self.block_card = None  # For steal: 3=Captain, 2=Ambassador
        self.passed_players = set()
        
        # Create buttons based on block type
        if block_type == 'contessa':
            # Assassination - block with Contessa
            block_btn = Button(
                label="Block with Contessa",
                emoji="🛡️",
                style=discord.ButtonStyle.danger,
                custom_id="block_contessa"
            )
            block_btn.callback = self.make_block_callback(4)  # Contessa card
            self.add_item(block_btn)
            
        elif block_type == 'steal':
            # Steal - block with Captain or Ambassador
            captain_btn = Button(
                label="Block with Captain",
                emoji="⚓",
                style=discord.ButtonStyle.primary,
                custom_id="block_captain"
            )
            captain_btn.callback = self.make_block_callback(3)  # Captain card
            self.add_item(captain_btn)
            
            ambassador_btn = Button(
                label="Block with Ambassador",
                emoji="🤝",
                style=discord.ButtonStyle.primary,
                custom_id="block_ambassador"
            )
            ambassador_btn.callback = self.make_block_callback(2)  # Ambassador card
            self.add_item(ambassador_btn)
            
        elif block_type == 'foreign_aid':
            # Foreign Aid - block with Duke
            block_btn = Button(
                label="Block with Duke",
                emoji="👑",
                style=discord.ButtonStyle.danger,
                custom_id="block_duke"
            )
            block_btn.callback = self.make_block_callback(0)  # Duke card
            self.add_item(block_btn)
        
        # Pass button (always present)
        pass_btn = Button(
            label="Pass",
            emoji="✋",
            style=discord.ButtonStyle.secondary,
            custom_id="block_pass"
        )
        pass_btn.callback = self.pass_callback
        self.add_item(pass_btn)
    
    def make_block_callback(self, card_value: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id not in self.eligible_player_ids:
                await interaction.response.send_message("❌ You cannot block this action!", ephemeral=True)
                return
            
            if self.blocker_id is not None:
                await interaction.response.send_message("❌ Someone already blocked!", ephemeral=True)
                return
            
            if interaction.user.id in self.passed_players:
                await interaction.response.send_message("❌ You already passed!", ephemeral=True)
                return
            
            self.blocker_id = interaction.user.id
            self.block_card = card_value
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(view=self)
            
            # Get card name for display
            card_names = {0: "Duke", 2: "Ambassador", 3: "Captain", 4: "Contessa"}
            card_name = card_names.get(card_value, "Unknown")
            
            await interaction.followup.send(f"🛡️ **{interaction.user.name}** blocks with **{card_name}**!")
            self.stop()
        
        return callback
    
    async def pass_callback(self, interaction: discord.Interaction):
        if interaction.user.id not in self.eligible_player_ids:
            await interaction.response.send_message("❌ You are not involved in this action!", ephemeral=True)
            return
        
        if interaction.user.id in self.passed_players:
            await interaction.response.send_message("ℹ️ You already passed!", ephemeral=True)
            return
        
        if self.blocker_id is not None:
            await interaction.response.send_message("❌ Someone already blocked!", ephemeral=True)
            return
        
        self.passed_players.add(interaction.user.id)
        
        await interaction.response.send_message(f"✋ You passed on blocking.", ephemeral=True)
        
        # Check if all eligible players have passed
        if len(self.passed_players) >= len(self.eligible_player_ids):
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            try:
                await interaction.message.edit(view=self)
            except:
                pass
            self.stop()
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

# ============================================================================
# OWNER CARD SWAP VIEW - Secret card swapping for bot owner
# ============================================================================

class OwnerCardSwapView(View):
    """View for bot owner to secretly swap their cards during a game"""
    
    def __init__(self, bot_instance, player_obj, owner_id: int, current_cards: List[tuple], available_cards: List[int], timeout: float = 120):
        super().__init__(timeout=timeout)
        self.bot = bot_instance
        self.player_obj = player_obj
        self.owner_id = owner_id
        self.current_cards = current_cards  # [(index, card_val, card_name), ...]
        self.available_cards = available_cards  # [count_duke, count_assassin, count_ambassador, count_captain, count_contessa]
        self.selected_cards = []  # Will store the 2 new card values
        self.selection_step = 0  # 0 = first card, 1 = second card
        
        # Card names and emojis
        self.CARD_NAMES = ["Duke", "Assassin", "Ambassador", "Captain", "Contessa"]
        self.CARD_EMOJIS = {"Duke": "👑", "Assassin": "🗡️", "Ambassador": "🤝", "Captain": "⚓", "Contessa": "🛡️"}
        self.CARD_DESCRIPTIONS = [
            "Tax (3 coins), blocks Foreign Aid",
            "Assassinate (3 coins)",
            "Exchange cards, blocks Steal",
            "Steal (2 coins), blocks Steal",
            "Blocks Assassination"
        ]
        
        # Build options list - only include cards that are available in the deck
        options = []
        card_emojis = ["👑", "🗡️", "🤝", "⚓", "🛡️"]
        
        for i in range(5):
            if available_cards[i] > 0:  # Only add if cards are available in deck
                options.append(
                    discord.SelectOption(
                        label=f"{self.CARD_NAMES[i]} ({available_cards[i]} available)",
                        description=self.CARD_DESCRIPTIONS[i],
                        emoji=card_emojis[i],
                        value=str(i)
                    )
                )
        
        # If no cards available, add a placeholder
        if not options:
            options.append(
                discord.SelectOption(
                    label="No cards available in deck",
                    description="All cards are in play",
                    value="-1"
                )
            )
        
        # Create dropdown for selecting cards
        self.card_select = Select(
            placeholder=f"Choose your {'first' if self.selection_step == 0 else 'second'} card...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="owner_card_select"
        )
        self.card_select.callback = self.card_selected
        self.add_item(self.card_select)
        
        # Cancel button
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
        cancel_btn.callback = self.cancel_swap
        self.add_item(cancel_btn)
    
    async def card_selected(self, interaction: discord.Interaction):
        """Handle card selection from dropdown"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This is not for you!", ephemeral=True)
            return
        
        selected_value = int(self.card_select.values[0])
        
        # Check for invalid selection
        if selected_value == -1:
            await interaction.response.send_message("❌ No cards available in deck!", ephemeral=True)
            return
        
        self.selected_cards.append(selected_value)
        
        if self.selection_step == 0:
            # First card selected, ask for second card
            self.selection_step = 1
            
            # Update available cards (decrease the count for the selected card)
            updated_availability = self.available_cards.copy()
            updated_availability[selected_value] -= 1
            
            # Rebuild dropdown options for second card
            options = []
            card_emojis = ["👑", "🗡️", "🤝", "⚓", "🛡️"]
            
            for i in range(5):
                if updated_availability[i] > 0:  # Only add if cards are still available
                    options.append(
                        discord.SelectOption(
                            label=f"{self.CARD_NAMES[i]} ({updated_availability[i]} available)",
                            description=self.CARD_DESCRIPTIONS[i],
                            emoji=card_emojis[i],
                            value=str(i)
                        )
                    )
            
            # If no cards available for second selection
            if not options:
                await interaction.response.send_message("❌ No more cards available in deck for second card!", ephemeral=True)
                self.stop()
                return
            
            # Update the dropdown with new options
            self.card_select.options = options
            self.card_select.placeholder = "Choose your second card..."
            
            # Update embed to show progress
            first_card_name = self.CARD_NAMES[selected_value]
            first_card_emoji = self.CARD_EMOJIS[first_card_name]
            
            embed = discord.Embed(
                title="🔧 Owner Card Swap",
                description=f"**First card selected:** {first_card_emoji} **{first_card_name}**\n\n**Now select your second card:**",
                color=0xF39C12  # COLOR_WARNING
            )
            embed.set_footer(text="This action is completely private • No one else will see this")
            
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            # Second card selected, perform the swap
            await self.perform_swap(interaction)
    
    async def perform_swap(self, interaction: discord.Interaction):
        """Execute the card swap"""
        # Return old cards to deck (only non-dead cards)
        old_cards = []
        for idx, card_val in enumerate(self.player_obj.cards):
            if card_val != -2:
                old_cards.append(card_val)
        
        # Add old cards back to deck
        if len(old_cards) == 2:
            self.bot.game_inst.deck.add(old_cards[0], old_cards[1])
        elif len(old_cards) == 1:
            self.bot.game_inst.deck.add(old_cards[0])
        
        # Assign new cards to player
        new_card_positions = []
        for idx, card_val in enumerate(self.player_obj.cards):
            if card_val != -2:
                new_card_positions.append(idx)
        
        # Assign the selected cards to the available positions
        for i, pos in enumerate(new_card_positions):
            if i < len(self.selected_cards):
                self.player_obj.cards[pos] = self.selected_cards[i]
        
        # Build confirmation message
        card1_name = self.CARD_NAMES[self.selected_cards[0]]
        card2_name = self.CARD_NAMES[self.selected_cards[1]]
        card1_emoji = self.CARD_EMOJIS[card1_name]
        card2_emoji = self.CARD_EMOJIS[card2_name]
        
        success_embed = discord.Embed(
            title="✅ Cards Swapped Successfully",
            description=f"**Your new cards are:**\n🅰 {card1_emoji} **{card1_name}**\n🅱 {card2_emoji} **{card2_name}**\n\n*Old cards have been returned to the deck.*",
            color=0x2ECC71  # COLOR_SUCCESS
        )
        success_embed.set_footer(text="Swap complete • No public notification sent")
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=success_embed, view=self)
        self.stop()
    
    async def cancel_swap(self, interaction: discord.Interaction):
        """Cancel the swap operation"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This is not for you!", ephemeral=True)
            return
        
        cancel_embed = discord.Embed(
            title="❌ Swap Cancelled",
            description="Card swap has been cancelled. Your cards remain unchanged.",
            color=0xE74C3C  # COLOR_DANGER
        )
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=cancel_embed, view=self)
        self.stop()
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def wait_for_view_response(view: View, timeout: Optional[float] = None) -> Optional[any]:
    """Wait for a view to complete and return the choice"""
    try:
        await asyncio.wait_for(view.wait(), timeout=timeout)
        return view.choice if hasattr(view, 'choice') else None
    except asyncio.TimeoutError:
        return None
