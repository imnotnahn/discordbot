import discord
from discord.ext import commands
import random
import json
import os
import asyncio
from enum import Enum
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger('discord_bot')

# Enums for unit roles and rarities
class UnitRole(Enum):
    MAGE = "mage"
    TANK = "tank"
    WARRIOR = "warrior"

class UnitRarity(Enum):
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"

# Role emojis and colors
ROLE_EMOJIS = {
    UnitRole.MAGE: "🧙",
    UnitRole.TANK: "🛡️",
    UnitRole.WARRIOR: "⚔️"
}

RARITY_COLORS = {
    UnitRarity.COMMON: discord.Color.light_gray(),
    UnitRarity.RARE: discord.Color.blue(),
    UnitRarity.EPIC: discord.Color.purple(),
    UnitRarity.LEGENDARY: discord.Color.gold()
}

# Base unit stats by role
ROLE_BASE_STATS = {
    UnitRole.MAGE: {"health": 80, "damage": 40, "armor": 5, "special": "spell_power"},
    UnitRole.TANK: {"health": 150, "damage": 20, "armor": 15, "special": "armor_bonus"},
    UnitRole.WARRIOR: {"health": 100, "damage": 30, "armor": 10, "special": "critical_chance"}
}

# Rarity multipliers
RARITY_MULTIPLIERS = {
    UnitRarity.COMMON: 1.0,
    UnitRarity.RARE: 1.2,
    UnitRarity.EPIC: 1.5,
    UnitRarity.LEGENDARY: 2.0
}

# Gacha cost and daily currency
GACHA_COST = 100
DAILY_CURRENCY = 200

class Unit:
    """Represents a battle unit with stats and abilities"""
    
    def __init__(self, id: str, name: str, role: UnitRole, rarity: UnitRarity):
        self.id = id
        self.name = name
        self.role = role
        self.rarity = rarity
        self.position = 1  # Default to front row (1=front, 2=back)
        
        # Calculate stats based on role and rarity
        base_stats = ROLE_BASE_STATS[role]
        multiplier = RARITY_MULTIPLIERS[rarity]
        
        self.max_health = int(base_stats["health"] * multiplier)
        self.current_health = self.max_health
        self.damage = int(base_stats["damage"] * multiplier)
        
        # Add armor as a standard stat
        self.armor = int(base_stats.get("armor", 5) * multiplier)
        
        # Special stat based on role
        special_stat = base_stats["special"]
        if special_stat == "spell_power":
            self.spell_power = int(15 * multiplier)
        elif special_stat == "armor_bonus":  # Renamed from "armor" to "armor_bonus"
            self.armor += int(10 * multiplier)  # Additional armor for tanks
        elif special_stat == "critical_chance":
            self.critical_chance = int(10 * multiplier)
    
    def to_dict(self) -> dict:
        """Convert unit to dictionary for storage"""
        result = {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "rarity": self.rarity.value,
            "max_health": self.max_health,
            "damage": self.damage,
            "armor": self.armor,
            "position": self.position
        }
        
        # Add special attributes
        if self.role == UnitRole.MAGE:
            result["spell_power"] = getattr(self, "spell_power", 0)
        elif self.role == UnitRole.WARRIOR:
            result["critical_chance"] = getattr(self, "critical_chance", 0)
            
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "Unit":
        """Create unit from dictionary data"""
        unit = cls(
            id=data["id"],
            name=data["name"],
            role=UnitRole(data["role"]),
            rarity=UnitRarity(data["rarity"])
        )
        
        # Override calculated stats if they exist in the data
        if "max_health" in data:
            unit.max_health = data["max_health"]
        if "damage" in data:
            unit.damage = data["damage"]
        if "armor" in data:
            unit.armor = data["armor"]
        if "position" in data:
            unit.position = data["position"]
            
        # Load special attributes
        if unit.role == UnitRole.MAGE and "spell_power" in data:
            unit.spell_power = data["spell_power"]
        elif unit.role == UnitRole.WARRIOR and "critical_chance" in data:
            unit.critical_chance = data["critical_chance"]
            
        return unit
    
    def reset_health(self):
        """Reset health to maximum for new battles"""
        self.current_health = self.max_health
    
    def is_alive(self) -> bool:
        """Check if unit is still alive"""
        return self.current_health > 0
    
    def get_special_attribute(self) -> Tuple[str, int]:
        """Get the special attribute for this unit based on role"""
        if self.role == UnitRole.MAGE:
            return "Spell Power", getattr(self, "spell_power", 0)
        elif self.role == UnitRole.TANK:
            return "Armor", getattr(self, "armor", 0)
        elif self.role == UnitRole.WARRIOR:
            return "Critical Chance", getattr(self, "critical_chance", 0)
        return "None", 0
    
    # Update the attack method in Unit class
    def attack(self, target: "Unit") -> Tuple[int, bool]:
        """Attack another unit and return damage dealt and if critical"""
        damage = self.damage
        critical = False
        
        # Apply role-specific effects
        if self.role == UnitRole.MAGE:
            # Mages ignore some armor
            spell_power = getattr(self, "spell_power", 0)
            damage += spell_power
            # Mages ignore 30% of armor
            armor_ignored = int(target.armor * 0.3)
        elif self.role == UnitRole.WARRIOR:
            # Warriors have critical strike chance
            critical_chance = getattr(self, "critical_chance", 0)
            if random.randint(1, 100) <= critical_chance:
                damage = int(damage * 1.5)
                critical = True
        
        # Apply armor damage reduction
        if self.role == UnitRole.MAGE:
            damage_reduction = target.armor - armor_ignored
        else:
            damage_reduction = target.armor
        
        damage = max(1, damage - damage_reduction)  # Ensure minimum 1 damage
        
        # Apply damage
        actual_damage = min(target.current_health, damage)
        target.current_health -= actual_damage
        
        return actual_damage, critical

class PlayerInventory:
    """Manages a player's units and currency"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.units: List[Unit] = []
        self.currency = 500  # Starting currency
        self.last_daily = 0  # Timestamp for last daily claim
    
    def add_unit(self, unit: Unit):
        """Add a unit to inventory"""
        self.units.append(unit)
    
    def get_unit(self, unit_id: str) -> Optional[Unit]:
        """Get a unit by ID"""
        for unit in self.units:
            if unit.id == unit_id:
                return unit
        return None
    
    def to_dict(self) -> dict:
        """Convert inventory to dictionary for storage"""
        return {
            "user_id": self.user_id,
            "currency": self.currency,
            "last_daily": self.last_daily,
            "units": [unit.to_dict() for unit in self.units]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PlayerInventory":
        """Create inventory from dictionary data"""
        inventory = cls(user_id=data["user_id"])
        inventory.currency = data.get("currency", 500)
        inventory.last_daily = data.get("last_daily", 0)
        
        # Load units
        for unit_data in data.get("units", []):
            inventory.units.append(Unit.from_dict(unit_data))
            
        return inventory

class Battle:
    """Represents an ongoing battle between two players"""
    
    def __init__(self, player1_id: int, player2_id: int):
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.player1_units: List[Unit] = []
        self.player2_units: List[Unit] = []
        self.current_turn = player1_id
        self.winner = None
        self.turn_count = 1
        self.last_action_message = ""
    
    def add_player_units(self, player_id: int, units: List[Unit]):
        """Add units for a player to the battle"""
        # Reset health for all units
        for unit in units:
            unit.reset_health()
            
        if player_id == self.player1_id:
            self.player1_units = units.copy()
        else:
            self.player2_units = units.copy()
    
    def is_game_over(self) -> bool:
        """Check if the game is over"""
        player1_alive = any(unit.is_alive() for unit in self.player1_units)
        player2_alive = any(unit.is_alive() for unit in self.player2_units)
        
        if not player1_alive:
            self.winner = self.player2_id
            return True
        elif not player2_alive:
            self.winner = self.player1_id
            return True
        
        return False
    
    def next_turn(self):
        """Advance to the next turn"""
        self.current_turn = self.player2_id if self.current_turn == self.player1_id else self.player1_id
        self.turn_count += 1
    
    def get_player_units(self, player_id: int) -> List[Unit]:
        """Get a player's units"""
        return self.player1_units if player_id == self.player1_id else self.player2_units
    
    def get_opponent_units(self, player_id: int) -> List[Unit]:
        """Get the opponent's units"""
        return self.player2_units if player_id == self.player1_id else self.player1_units
    
    # Update the perform_attack method in Battle class
    def perform_attack(self, attacker_index: int, target_index: int) -> bool:
        """Perform an attack between units by index"""
        player_units = self.get_player_units(self.current_turn)
        opponent_units = self.get_opponent_units(self.current_turn)
        
        # Check indices
        if not (0 <= attacker_index < len(player_units)) or not (0 <= target_index < len(opponent_units)):
            return False
        
        attacker = player_units[attacker_index]
        target = opponent_units[target_index]
        
        # Check if units are alive
        if not attacker.is_alive() or not target.is_alive():
            return False
        
        # Check for row-based counterattack mechanics
        counterattack_damage = 0
        counterattack_text = ""
        
        # If attacking back row and attacker is tank or warrior
        if target.position == 2 and attacker.role in [UnitRole.TANK, UnitRole.WARRIOR]:
            # Check if there are tanks or warriors in the front row to defend
            front_line_defenders = [
                unit for unit in opponent_units 
                if unit.position == 1 and unit.is_alive() and 
                unit.role in [UnitRole.TANK, UnitRole.WARRIOR]
            ]
            
            if front_line_defenders:
                # Calculate counterattack damage based on number of defenders
                counterattack_base = int(attacker.damage * 0.25)  # 25% of attacker's damage
                counterattack_multiplier = min(len(front_line_defenders), 3)  # Cap at 3x multiplier
                counterattack_damage = counterattack_base * counterattack_multiplier
                
                # Apply armor reduction to counterattack
                counterattack_damage = max(1, counterattack_damage - attacker.armor)
                
                # Apply counterattack damage
                actual_counterattack = min(attacker.current_health, counterattack_damage)
                attacker.current_health -= actual_counterattack
                
                defenders_text = ", ".join([unit.name for unit in front_line_defenders[:2]])
                if len(front_line_defenders) > 2:
                    defenders_text += f" and {len(front_line_defenders)-2} others"
                    
                counterattack_text = f" {defenders_text} defended with a counterattack for {actual_counterattack} damage!"
        
        # Perform regular attack
        damage_dealt, was_critical = attacker.attack(target)
        
        # Update last action message
        critical_text = " (CRITICAL HIT!)" if was_critical else ""
        self.last_action_message = f"{attacker.name} attacked {target.name} for {damage_dealt} damage{critical_text}!"
        
        if counterattack_text:
            self.last_action_message += counterattack_text
        
        if not target.is_alive():
            self.last_action_message += f" {target.name} was defeated!"
        
        if counterattack_damage > 0 and not attacker.is_alive():
            self.last_action_message += f" {attacker.name} was defeated by the counterattack!"
        
        return True

class TacticalBattleGame(commands.Cog):
    """Discord cog for the Tactical Battle game with gacha mechanics"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data_folder = "./game_data"
        self.unit_database = []  # Master list of available units
        self.player_inventories: Dict[int, PlayerInventory] = {}
        self.active_battles: Dict[str, Battle] = {}
        self.pending_battles: Dict[str, tuple] = {}  # channel_id: (challenger_id, opponent_id)
        
        # Create data folder if it doesn't exist
        os.makedirs(self.data_folder, exist_ok=True)
        
        # Load data
        self.load_data()
    def remove_command(self, command_name: str):
        """Remove a command from the bot"""
        return self.bot.remove_command(command_name)
    def add_command(self, command: commands.Command):
        """Add a command to the bot"""
        return self.bot.add_command(command)
    def load_data(self):
        """Load game data from files"""
        # Load unit database
        try:
            units_file = os.path.join(self.data_folder, "units.json")
            if os.path.exists(units_file):
                with open(units_file, "r") as f:
                    units_data = json.load(f)
                    self.unit_database = [Unit.from_dict(unit) for unit in units_data]
            else:
                # Create default units if no file exists
                self.create_default_units()
        except Exception as e:
            logger.error(f"Error loading unit database: {e}")
            self.create_default_units()
        
        # Load player inventories
        try:
            inventories_file = os.path.join(self.data_folder, "inventories.json")
            if os.path.exists(inventories_file):
                with open(inventories_file, "r") as f:
                    inventories_data = json.load(f)
                    for user_id_str, inventory_data in inventories_data.items():
                        user_id = int(user_id_str)
                        self.player_inventories[user_id] = PlayerInventory.from_dict(inventory_data)
        except Exception as e:
            logger.error(f"Error loading player inventories: {e}")
    
    def save_data(self):
        """Save game data to files"""
        # Save unit database
        try:
            units_file = os.path.join(self.data_folder, "units.json")
            with open(units_file, "w") as f:
                json.dump([unit.to_dict() for unit in self.unit_database], f, indent=2)
        except Exception as e:
            logger.error(f"Error saving unit database: {e}")
        
        # Save player inventories
        try:
            inventories_file = os.path.join(self.data_folder, "inventories.json")
            inventories_data = {
                str(user_id): inventory.to_dict() 
                for user_id, inventory in self.player_inventories.items()
            }
            with open(inventories_file, "w") as f:
                json.dump(inventories_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving player inventories: {e}")
    
    def create_default_units(self):
        """Create default units for the game"""
        self.unit_database = []
        
        # Define some default units
        default_units = [
            # Common units
            ("Apprentice Mage", UnitRole.MAGE, UnitRarity.COMMON),
            ("Recruit Guard", UnitRole.TANK, UnitRarity.COMMON),
            ("Militia Soldier", UnitRole.WARRIOR, UnitRarity.COMMON),
            
            # Rare units
            ("Battle Mage", UnitRole.MAGE, UnitRarity.RARE),
            ("Royal Guard", UnitRole.TANK, UnitRarity.RARE),
            ("Veteran Swordsman", UnitRole.WARRIOR, UnitRarity.RARE),
            
            # Epic units
            ("Archmage", UnitRole.MAGE, UnitRarity.EPIC),
            ("Steel Defender", UnitRole.TANK, UnitRarity.EPIC),
            ("Elite Blademaster", UnitRole.WARRIOR, UnitRarity.EPIC),
            
            # Legendary units
            ("Grand Sorcerer", UnitRole.MAGE, UnitRarity.LEGENDARY),
            ("Immortal Guardian", UnitRole.TANK, UnitRarity.LEGENDARY),
            ("Legendary Champion", UnitRole.WARRIOR, UnitRarity.LEGENDARY),
        ]
        
        for i, (name, role, rarity) in enumerate(default_units):
            unit_id = f"unit_{i+1:03d}"
            self.unit_database.append(Unit(unit_id, name, role, rarity))
        
        # Save the default units
        self.save_data()
    
    def get_player_inventory(self, user_id: int) -> PlayerInventory:
        """Get a player's inventory, creating it if it doesn't exist"""
        if user_id not in self.player_inventories:
            self.player_inventories[user_id] = PlayerInventory(user_id)
            # Give new players some starter units
            starter_units = [unit for unit in self.unit_database if unit.rarity == UnitRarity.COMMON]
            if starter_units:
                for _ in range(3):
                    unit = random.choice(starter_units)
                    new_unit = Unit(
                        f"p{user_id}_{unit.id}_{random.randint(10000, 99999)}",
                        unit.name,
                        unit.role,
                        unit.rarity
                    )
                    self.player_inventories[user_id].add_unit(new_unit)
            self.save_data()
        return self.player_inventories[user_id]
    
    def get_battle_key(self, player1_id: int, player2_id: int, channel_id: int) -> str:
        """Generate a unique key for a battle"""
        return f"{channel_id}:{min(player1_id, player2_id)}:{max(player1_id, player2_id)}"
    
    def perform_gacha_roll(self, user_id: int) -> Unit:
        """Perform a gacha roll and add unit to player inventory"""
        inventory = self.get_player_inventory(user_id)
        
        # Check if player has enough currency
        if inventory.currency < GACHA_COST:
            return None
        
        # Deduct currency
        inventory.currency -= GACHA_COST
        
        # Determine rarity (weighted random)
        rarity_weights = [
            (UnitRarity.COMMON, 60),
            (UnitRarity.RARE, 30),
            (UnitRarity.EPIC, 9),
            (UnitRarity.LEGENDARY, 1)
        ]
        rarity = random.choices(
            [r[0] for r in rarity_weights],
            weights=[r[1] for r in rarity_weights],
            k=1
        )[0]
        
        # Select a unit of that rarity
        possible_units = [unit for unit in self.unit_database if unit.rarity == rarity]
        if not possible_units:
            # Fallback to any unit if no units of that rarity exist
            possible_units = self.unit_database
        
        if not possible_units:
            # If still no units, create a generic one
            unit_name = f"Generic {rarity.value.capitalize()} Unit"
            unit = Unit(
                f"p{user_id}_gen_{random.randint(10000, 99999)}",
                unit_name,
                random.choice(list(UnitRole)),
                rarity
            )
        else:
            template_unit = random.choice(possible_units)
            unit = Unit(
                f"p{user_id}_{template_unit.id}_{random.randint(10000, 99999)}",
                template_unit.name,
                template_unit.role,
                template_unit.rarity
            )
        
        # Add to player inventory
        inventory.add_unit(unit)
        self.save_data()
        
        return unit
    
    @commands.hybrid_command(
        name="tactic_daily",
        description="Claim your daily currency reward"
    )
    async def daily_reward(self, ctx: commands.Context):
        """Claim daily currency reward"""
        user_id = ctx.author.id
        inventory = self.get_player_inventory(user_id)
        
        # Check if already claimed today
        current_time = int(asyncio.get_running_loop().time())
        day_seconds = 24 * 60 * 60
        
        if current_time - inventory.last_daily < day_seconds:
            time_left = day_seconds - (current_time - inventory.last_daily)
            hours = time_left // 3600
            minutes = (time_left % 3600) // 60
            
            embed = discord.Embed(
                title="Daily Reward Already Claimed",
                description=f"You've already claimed your daily reward. Try again in {hours}h {minutes}m.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Grant reward
        inventory.currency += DAILY_CURRENCY
        inventory.last_daily = current_time
        self.save_data()
        
        embed = discord.Embed(
            title="Daily Reward Claimed!",
            description=f"You received {DAILY_CURRENCY} battle coins!\nYou now have {inventory.currency} battle coins.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="tactic_gacha",
        description=f"Roll the gacha to get a new unit (costs {GACHA_COST} coins)"
    )
    async def gacha_roll(self, ctx: commands.Context):
        """Roll the gacha to get a new unit"""
        user_id = ctx.author.id
        inventory = self.get_player_inventory(user_id)
        
        # Check if player has enough currency
        if inventory.currency < GACHA_COST:
            embed = discord.Embed(
                title="Not Enough Coins",
                description=f"You need {GACHA_COST} battle coins to roll. You only have {inventory.currency}.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Show rolling animation
        message = await ctx.send("🎲 Rolling gacha...")
        
        # Add some suspense
        for _ in range(3):
            await asyncio.sleep(0.7)
            await message.edit(content=message.content + ".")
        
        # Perform the roll
        unit = self.perform_gacha_roll(user_id)
        
        # Create embed based on rarity
        emoji = ROLE_EMOJIS.get(unit.role, "❓")
        color = RARITY_COLORS.get(unit.rarity, discord.Color.default())
        
        special_attr_name, special_attr_value = unit.get_special_attribute()
        
        embed = discord.Embed(
            title=f"🎉 New Unit Acquired: {unit.name} {emoji}",
            color=color
        )
        embed.add_field(name="Rarity", value=unit.rarity.value.capitalize(), inline=True)
        embed.add_field(name="Role", value=f"{emoji} {unit.role.value.capitalize()}", inline=True)
        embed.add_field(name="Health", value=str(unit.max_health), inline=True)
        embed.add_field(name="Damage", value=str(unit.damage), inline=True)
        embed.add_field(name=special_attr_name, value=str(special_attr_value), inline=True)
        
        embed.set_footer(text=f"You now have {inventory.currency} battle coins")
        
        await message.edit(content=None, embed=embed)
    
    @commands.hybrid_command(
        name="tactic_inventory",
        description="View your unit inventory"
    )
    async def show_inventory(self, ctx: commands.Context):
        """Show your unit inventory"""
        user_id = ctx.author.id
        inventory = self.get_player_inventory(user_id)
        
        if not inventory.units:
            embed = discord.Embed(
                title="Your Inventory",
                description="You don't have any units yet. Use `/gacha` to get some!",
                color=discord.Color.blue()
            )
            embed.add_field(name="Battle Coins", value=str(inventory.currency), inline=False)
            return await ctx.send(embed=embed)
        
        # Group units by rarity for better display
        units_by_rarity = {}
        for unit in inventory.units:
            if unit.rarity not in units_by_rarity:
                units_by_rarity[unit.rarity] = []
            units_by_rarity[unit.rarity].append(unit)
        
        # Sort rarities from highest to lowest
        sorted_rarities = sorted(
            units_by_rarity.keys(),
            key=lambda r: ["common", "rare", "epic", "legendary"].index(r.value),
            reverse=True
        )
        
        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Unit Inventory",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Battle Coins", 
            value=f"{inventory.currency} 💰", 
            inline=False
        )
        
        # Add units grouped by rarity
        for rarity in sorted_rarities:
            units = units_by_rarity[rarity]
            rarity_text = rarity.value.capitalize()
            unit_text = ""
            
            for i, unit in enumerate(sorted(units, key=lambda u: u.name)):
                emoji = ROLE_EMOJIS.get(unit.role, "❓")
                unit_text += f"{i+1}. {emoji} **{unit.name}** (HP: {unit.max_health}, DMG: {unit.damage})\n"
                if i >= 9:  # Show max 10 units per rarity
                    remaining = len(units) - 10
                    if remaining > 0:
                        unit_text += f"*...and {remaining} more {rarity_text} units*\n"
                    break
            
            embed.add_field(
                name=f"{rarity_text} Units ({len(units)})",
                value=unit_text or "None",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="tactic_battle",
        description="Challenge another player to a tactical battle"
    )
    async def start_battle(self, ctx: commands.Context, opponent: discord.Member):
        """Challenge another player to a battle"""
        # Check if opponent is valid
        if opponent.bot:
            return await ctx.send("You cannot challenge a bot to a battle!")
        
        if opponent.id == ctx.author.id:
            return await ctx.send("You cannot battle yourself!")
        
        # Check if either player is already in a battle
        for battle in self.active_battles.values():
            if ctx.author.id in [battle.player1_id, battle.player2_id]:
                return await ctx.send("You are already in a battle!")
            if opponent.id in [battle.player1_id, battle.player2_id]:
                return await ctx.send(f"{opponent.display_name} is already in a battle!")
        
        # Check if both players have enough units
        challenger_inventory = self.get_player_inventory(ctx.author.id)
        opponent_inventory = self.get_player_inventory(opponent.id)
        
        challenger_units = [unit for unit in challenger_inventory.units if unit.is_alive()]
        if len(challenger_units) < 5:
            return await ctx.send(f"You need at least 5 units to battle! You only have {len(challenger_units)}.")
        
        opponent_units = [unit for unit in opponent_inventory.units if unit.is_alive()]
        if len(opponent_units) < 5:
            return await ctx.send(f"{opponent.display_name} needs at least 5 units to battle! They only have {len(opponent_units)}.")
        
        # Create battle request
        battle_key = self.get_battle_key(ctx.author.id, opponent.id, ctx.channel.id)
        self.pending_battles[battle_key] = (ctx.author.id, opponent.id)
        
        # Create confirmation embed
        embed = discord.Embed(
            title="Battle Challenge!",
            description=f"{ctx.author.mention} has challenged {opponent.mention} to a tactical battle!",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="How to Accept",
            value=f"{opponent.mention}, type `/accept_battle` to accept this challenge!",
            inline=False
        )
        embed.set_footer(text="The challenge will expire in 60 seconds.")
        
        # Send challenge and set expiration
        await ctx.send(embed=embed)
        
        # Wait 60 seconds and remove if not accepted
        await asyncio.sleep(60)
        if battle_key in self.pending_battles:
            del self.pending_battles[battle_key]
            try:
                await ctx.send(f"Battle challenge from {ctx.author.mention} to {opponent.mention} has expired.")
            except:
                pass
    
    @commands.hybrid_command(
        name="tactic_acceptbattle",
        description="Accept a battle challenge"
    )
    async def accept_battle(self, ctx: commands.Context):
        """Accept a pending battle challenge"""
        user_id = ctx.author.id
        channel_id = ctx.channel.id
        
        # Find the pending battle
        found_key = None
        for key, (challenger_id, opponent_id) in self.pending_battles.items():
            if opponent_id == user_id and str(channel_id) in key:
                found_key = key
                break
        
        if not found_key:
            return await ctx.send("You don't have any pending battle challenges in this channel.")
        
        # Get player data
        challenger_id, _ = self.pending_battles[found_key]
        challenger = self.bot.get_user(challenger_id)
        
        if not challenger:
            # Safely remove using pop() instead of del to avoid KeyError
            self.pending_battles.pop(found_key, None)
            return await ctx.send("The challenger seems to have disappeared.")
        
        # Store the pending battle info and remove from pending battles immediately
        # to avoid trying to delete it again later
        battle_info = self.pending_battles.pop(found_key, None)
        if not battle_info:
            return await ctx.send("The battle challenge was already accepted or expired.")
        
        # Create battle
        battle = Battle(challenger_id, user_id)
        
        # Add units to the battle
        await ctx.send("Battle accepted! Please wait while both players select their units...")
        
        # Let both players select their units
        challenger_units = await self.select_battle_units(ctx, challenger)
        if not challenger_units:
            return await ctx.send("Battle cancelled: challenger did not select units in time.")
        
        opponent_units = await self.select_battle_units(ctx, ctx.author)
        if not opponent_units:
            return await ctx.send("Battle cancelled: opponent did not select units in time.")
        
        # Add units to battle
        battle.add_player_units(challenger_id, challenger_units)
        battle.add_player_units(user_id, opponent_units)
        
        # Start battle
        self.active_battles[found_key] = battle
        
        # Display initial battle state
        await self.display_battle_state(ctx, battle)
        
        # Ask first player for their move
        first_player = self.bot.get_user(battle.current_turn)
        await ctx.send(f"{first_player.mention}'s turn! Use `/battle_attack [your_unit] [enemy_unit]` to attack.")
    
    # Update select_battle_units method
    async def select_battle_units(self, ctx: commands.Context, player: discord.User) -> List[Unit]:
        """Let a player select their battle units and arrange formation"""
        inventory = self.get_player_inventory(player.id)
        valid_units = [unit for unit in inventory.units if unit.is_alive()]
        
        if len(valid_units) < 5:
            await ctx.send(f"{player.display_name} does not have enough units to battle.")
            return []
        
        try:
            # Create embed showing available units
            embed = discord.Embed(
                title="Select Your Battle Units",
                description=f"Select 5 units to use in your battle in {ctx.guild.name}.\nSend unit numbers separated by spaces (e.g., `1 5 8 12 15`).",
                color=discord.Color.blue()
            )
            
            # List available units
            unit_list = ""
            for i, unit in enumerate(valid_units):
                emoji = ROLE_EMOJIS.get(unit.role, "❓")
                unit_list += f"{i+1}. {emoji} **{unit.name}** ({unit.rarity.value}) - HP: {unit.max_health}, DMG: {unit.damage}, ARM: {unit.armor}\n"
                if i >= 19:  # Show max 20 units
                    unit_list += f"*...and {len(valid_units) - 20} more units*\n"
                    break
            
            embed.add_field(name="Your Units", value=unit_list, inline=False)
            embed.set_footer(text="You have 60 seconds to respond.")
            
            dm_channel = await player.create_dm()
            await dm_channel.send(embed=embed)
            
            # Wait for response
            def check(message):
                return message.author.id == player.id and message.channel == dm_channel
            
            try:
                response = await self.bot.wait_for('message', check=check, timeout=60)
                
                # Parse response
                try:
                    selected_indices = [int(idx) - 1 for idx in response.content.split()]
                    
                    # Validate selection
                    if len(selected_indices) != 5:
                        await dm_channel.send("You must select exactly 5 units. Battle cancelled.")
                        return []
                    
                    # Check if indices are valid
                    for idx in selected_indices:
                        if not (0 <= idx < len(valid_units)):
                            await dm_channel.send(f"Invalid unit number: {idx+1}. Battle cancelled.")
                            return []
                    
                    # Get selected units
                    selected_units = [valid_units[idx] for idx in selected_indices]
                    
                    # Formation selection
                    embed = discord.Embed(
                        title="Arrange Your Formation",
                        description="You have 2 rows in your formation - front (1) and back (2).\n"
                                    "For each unit, specify which row to place it in using format: `1 1 2 2 1`\n"
                                    "(where each number represents front row (1) or back row (2))",
                        color=discord.Color.blue()
                    )
                    
                    # Fix the bug in the formation selection code
                    unit_list = ""
                    for i, unit in enumerate(selected_units):
                        emoji = ROLE_EMOJIS.get(unit.role, "❓")
                        unit_list += f"{i+1}. {emoji} **{unit.name}** ({unit.role.value})\n"
                    
                    embed.add_field(name="Selected Units", value=unit_list, inline=False)
                    embed.set_footer(text="You have 60 seconds to respond.")
                    
                    await dm_channel.send(embed=embed)
                    
                    # Wait for formation response
                    formation_response = await self.bot.wait_for('message', check=check, timeout=60)
                    
                    try:
                        positions = [int(pos) for pos in formation_response.content.split()]
                        
                        # Validate positions
                        if len(positions) != 5:
                            await dm_channel.send("You must provide positions for all 5 units. Using default formation.")
                            # Default formation: tanks/warriors in front, mages in back
                            for unit in selected_units:
                                if unit.role == UnitRole.MAGE:
                                    unit.position = 2  # Back row
                                else:
                                    unit.position = 1  # Front row
                        else:
                            # Apply selected positions
                            for i, pos in enumerate(positions):
                                if pos not in [1, 2]:
                                    await dm_channel.send(f"Invalid position {pos} (must be 1 or 2). Setting to front row (1).")
                                    selected_units[i].position = 1
                                else:
                                    selected_units[i].position = pos
                                    
                        # Show final formation
                        front_row = [unit for unit in selected_units if unit.position == 1]
                        back_row = [unit for unit in selected_units if unit.position == 2]
                        
                        formation_text = "**Front Row:**\n"
                        for unit in front_row:
                            emoji = ROLE_EMOJIS.get(unit.role, "❓")
                            formation_text += f"{emoji} {unit.name} (HP: {unit.max_health}, DMG: {unit.damage}, ARM: {unit.armor})\n"
                        
                        formation_text += "\n**Back Row:**\n"
                        for unit in back_row:
                            emoji = ROLE_EMOJIS.get(unit.role, "❓")
                            formation_text += f"{emoji} {unit.name} (HP: {unit.max_health}, DMG: {unit.damage}, ARM: {unit.armor})\n"
                        
                        await dm_channel.send(embed=discord.Embed(
                            title="Formation Set",
                            description=formation_text,
                            color=discord.Color.green()
                        ))
                        
                        return selected_units
                        
                    except ValueError:
                        await dm_channel.send("Invalid positions. Using default formation.")
                        # Apply default formation
                        for unit in selected_units:
                            if unit.role == UnitRole.MAGE:
                                unit.position = 2  # Back row
                            else:
                                unit.position = 1  # Front row
                        return selected_units
                        
                except ValueError:
                    await dm_channel.send("Invalid input. Please enter unit numbers separated by spaces.")
                    return []
                    
            except asyncio.TimeoutError:
                await dm_channel.send("Time's up! Battle cancelled.")
                return []
                
        except discord.Forbidden:
            await ctx.send(f"{player.mention}, I couldn't send you a DM. Please enable DMs from server members.")
            return []
    
    # Update the display_battle_state method
    async def display_battle_state(self, ctx: commands.Context, battle: Battle):
        """Display the current state of a battle"""
        player1 = self.bot.get_user(battle.player1_id)
        player2 = self.bot.get_user(battle.player2_id)
        
        if not player1 or not player2:
            return
        
        # Determine which player is the current turn player
        current_player_id = battle.current_turn
        current_player = self.bot.get_user(current_player_id)
        other_player = player2 if current_player_id == player1.id else player1
        
        embed = discord.Embed(
            title=f"⚔️ Battle: {player1.display_name} vs {player2.display_name} ⚔️",
            description=f"**Turn {battle.turn_count}**: {current_player.mention}'s turn",
            color=discord.Color.gold()
        )
        
        # Display last action
        if battle.last_action_message:
            embed.add_field(
                name="📝 Last Action",
                value=f"```{battle.last_action_message}```",
                inline=False
            )
        
        # Get all units for each player (keeping original order)
        current_player_units = battle.player1_units if current_player_id == player1.id else battle.player2_units
        other_player_units = battle.player2_units if current_player_id == player1.id else battle.player1_units
        
        # Format YOUR units section
        your_units_text = self._format_battle_units(current_player_units, show_index=True)
        embed.add_field(
            name=f"🟢 YOUR UNITS ({current_player.display_name})",
            value=your_units_text or "No units remaining",
            inline=False
        )
        
        # Format ENEMY units section
        enemy_units_text = self._format_battle_units(other_player_units, show_index=True)
        embed.add_field(
            name=f"🔴 ENEMY UNITS ({other_player.display_name})",
            value=enemy_units_text or "No units remaining",
            inline=False
        )
        
        # Display battle commands with clear numbering explanation
        embed.add_field(
            name="⌨️ Commands",
            value=(
                "`/battle_attack [your_unit] [enemy_unit]` - Attack an enemy unit\n"
                "`/battle_surrender` - Surrender the battle\n\n"
                "**Unit numbers are shown next to each unit name**"
            ),
            inline=False
        )
        
        # Add footer with targeting help
        embed.set_footer(text="Example: /battle_attack 1 2 → Your unit #1 attacks enemy unit #2")
        
        await ctx.send(embed=embed)

    # Add helper method for better unit display
    def _format_battle_units(self, units: List[Unit], show_index: bool = True) -> str:
        """Format a player's units for battle display with continuous numbering"""
        if not units:
            return "None"
        
        # Sort units by position - front row first, then back row
        front_row = [u for u in units if u.position == 1 and u.is_alive()]
        back_row = [u for u in units if u.position == 2 and u.is_alive()]
        dead_units = [u for u in units if not u.is_alive()]
        
        unit_text = ""
        
        # Add a header for the formation layout
        unit_text += "```\n"
        unit_text += "┌───── FRONT ROW ─────┐\n"
        
        # Display front row units
        if front_row:
            for i, unit in enumerate(front_row):
                # Get actual index in the full units list
                unit_index = units.index(unit) + 1 if show_index else ""
                emoji = self._get_role_symbol(unit.role)
                health_percent = max(0, unit.current_health / unit.max_health * 100)
                health_bar = self._generate_health_bar(health_percent, 10)
                
                unit_text += f"│ #{unit_index} {emoji} {unit.name}\n"
                unit_text += f"│    HP: {unit.current_health}/{unit.max_health} {health_bar}\n"
                unit_text += f"│    DMG: {unit.damage} | ARM: {unit.armor}\n"
                if i < len(front_row) - 1:
                    unit_text += "│\n"
        else:
            unit_text += "│     No front row units     │\n"
        
        unit_text += "├───── BACK ROW ──────┐\n"
        
        # Display back row units
        if back_row:
            for i, unit in enumerate(back_row):
                # Get actual index in the full units list
                unit_index = units.index(unit) + 1 if show_index else ""
                emoji = self._get_role_symbol(unit.role)
                health_percent = max(0, unit.current_health / unit.max_health * 100)
                health_bar = self._generate_health_bar(health_percent, 10)
                
                unit_text += f"│ #{unit_index} {emoji} {unit.name}\n"
                unit_text += f"│    HP: {unit.current_health}/{unit.max_health} {health_bar}\n"
                unit_text += f"│    DMG: {unit.damage} | ARM: {unit.armor}\n"
                if i < len(back_row) - 1:
                    unit_text += "│\n"
        else:
            unit_text += "│     No back row units      │\n"
        
        # Display defeated units if any
        if dead_units:
            unit_text += "├───── DEFEATED ──────┐\n"
            dead_text = " | ".join([f"{units.index(u) + 1}. {u.name} 💀" for u in dead_units])
            unit_text += f"│ {dead_text}\n"
        
        unit_text += "└─────────────────────┘\n"
        unit_text += "```"
        
        return unit_text

    # Helper for text-based health bars
    def _generate_health_bar(self, percent: float, length: int = 10) -> str:
        """Generate a text-based health bar for battle display"""
        filled = int(length * percent / 100)
        empty = length - filled
        
        if percent > 60:
            bar = "█" * filled + "░" * empty  # Use block characters for better visibility
            return f"[{bar}]"
        elif percent > 30:
            bar = "▓" * filled + "░" * empty
            return f"[{bar}]"
        else:
            bar = "▒" * filled + "░" * empty
            return f"[{bar}]"

    # Helper for role symbols in text display
    def _get_role_symbol(self, role: UnitRole) -> str:
        """Get a text symbol for unit roles in battle display"""
        if role == UnitRole.MAGE:
            return "✨"
        elif role == UnitRole.TANK:
            return "🛡️"
        elif role == UnitRole.WARRIOR:
            return "⚔️"
        return "?"

    @commands.hybrid_command(
        name="tactic_battleattack",
        description="Attack an enemy unit in battle"
    )
    async def battle_attack(self, ctx: commands.Context, your_unit: int, enemy_unit: int):
        """Attack an enemy unit in an active battle"""
        user_id = ctx.author.id
        channel_id = ctx.channel.id
        
        # Find the active battle
        found_key = None
        for key, battle in self.active_battles.items():
            if str(channel_id) in key and user_id in [battle.player1_id, battle.player2_id]:
                found_key = key
                break
        
        if not found_key:
            return await ctx.send("You are not in an active battle in this channel.")
        
        battle = self.active_battles[found_key]
        
        # Check if it's the player's turn
        if battle.current_turn != user_id:
            current_player = self.bot.get_user(battle.current_turn)
            return await ctx.send(f"It's not your turn! Waiting for {current_player.mention} to move.")
        
        # Adjust indices to be 0-based
        your_unit_index = your_unit - 1
        enemy_unit_index = enemy_unit - 1
        
        # Perform attack
        success = battle.perform_attack(your_unit_index, enemy_unit_index)
        if not success:
            return await ctx.send("Invalid attack. Please select valid units that are still alive.")
        
        # Check if game is over
        if battle.is_game_over():
            winner = self.bot.get_user(battle.winner)
            loser_id = battle.player2_id if battle.winner == battle.player1_id else battle.player1_id
            loser = self.bot.get_user(loser_id)
            
            # Display final state
            await self.display_battle_state(ctx, battle)
            
            # Announce winner
            embed = discord.Embed(
                title="Battle Ended!",
                description=f"🎉 **{winner.mention} has won the battle against {loser.mention}!** 🎉",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            
            # Reward winner
            winner_inventory = self.get_player_inventory(battle.winner)
            reward = 200
            winner_inventory.currency += reward
            self.save_data()
            
            await ctx.send(f"{winner.mention} received {reward} battle coins as a reward!")
            
            # Remove battle
            del self.active_battles[found_key]
            return
        
        # Next turn
        battle.next_turn()
        
        # Display updated battle state
        await self.display_battle_state(ctx, battle)
        
        # Prompt next player
        next_player = self.bot.get_user(battle.current_turn)
        await ctx.send(f"{next_player.mention}'s turn! Use `/battle_attack [your_unit] [enemy_unit]` to attack.")
    
    @commands.hybrid_command(
        name="tactic_battlesurrender",
        description="Surrender an active battle"
    )
    async def battle_surrender(self, ctx: commands.Context):
        """Surrender from an active battle"""
        user_id = ctx.author.id
        channel_id = ctx.channel.id
        
        # Find the active battle
        found_key = None
        for key, battle in self.active_battles.items():
            if str(channel_id) in key and user_id in [battle.player1_id, battle.player2_id]:
                found_key = key
                break
        
        if not found_key:
            return await ctx.send("You are not in an active battle in this channel.")
        
        battle = self.active_battles[found_key]
        
        # Set winner as opponent
        battle.winner = battle.player2_id if user_id == battle.player1_id else battle.player1_id
        winner = self.bot.get_user(battle.winner)
        
        # Announce surrender
        embed = discord.Embed(
            title="Battle Surrendered",
            description=f"{ctx.author.mention} has surrendered the battle. {winner.mention} wins!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        
        # Reward winner
        winner_inventory = self.get_player_inventory(battle.winner)
        reward = 100  # Less than a full victory
        winner_inventory.currency += reward
        self.save_data()
        
        await ctx.send(f"{winner.mention} received {reward} battle coins as a reward!")
        
        # Remove battle
        del self.active_battles[found_key]

    # Update unit_info command
    @commands.hybrid_command(
        name="tactic_unitinfo",
        description="View detailed information about one of your units"
    )
    async def unit_info(self, ctx: commands.Context, unit_number: int):
        """View detailed info about one of your units"""
        inventory = self.get_player_inventory(ctx.author.id)
        
        if not inventory.units:
            return await ctx.send("You don't have any units yet. Use `/gacha` to get some!")
        
        if unit_number < 1 or unit_number > len(inventory.units):
            return await ctx.send(f"Invalid unit number. You have {len(inventory.units)} units.")
        
        unit = inventory.units[unit_number - 1]
        emoji = ROLE_EMOJIS.get(unit.role, "❓")
        color = RARITY_COLORS.get(unit.rarity, discord.Color.default())
        
        special_attr_name, special_attr_value = unit.get_special_attribute()
        
        embed = discord.Embed(
            title=f"{unit.name} {emoji}",
            description=f"**{unit.rarity.value.capitalize()} {unit.role.value.capitalize()}**",
            color=color
        )
        
        embed.add_field(name="Health", value=str(unit.max_health), inline=True)
        embed.add_field(name="Damage", value=str(unit.damage), inline=True)
        embed.add_field(name="Armor", value=str(unit.armor), inline=True)
        embed.add_field(name=special_attr_name, value=str(special_attr_value), inline=True)
        
        # Add role-specific description
        if unit.role == UnitRole.MAGE:
            embed.add_field(
                name="Role Ability",
                value="Mages deal bonus damage equal to their spell power and ignore 30% of target's armor.",
                inline=False
            )
        elif unit.role == UnitRole.TANK:
            embed.add_field(
                name="Role Ability",
                value=f"Tanks have increased armor and high health, reducing incoming damage.",
                inline=False
            )
        elif unit.role == UnitRole.WARRIOR:
            embed.add_field(
                name="Role Ability",
                value=f"Warriors have a {getattr(unit, 'critical_chance', 0)}% chance to deal 50% bonus damage.",
                inline=False
            )
        
        # Add formation mechanics explanation
        embed.add_field(
            name="Formation Mechanics",
            value=(
                "**Front Row (1):** Protects back row units. Tanks and Warriors in the front row will counterattack " 
                "when enemies attack your back row.\n\n"
                "**Back Row (2):** Protected by front row. When Tanks or Warriors attack the back row while there " 
                "are defenders in the front row, they receive counterattack damage."
            ),
            inline=False
        )
        
        embed.set_footer(text=f"Unit ID: {unit.id}")
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="tactic_leaderboard",
        description="View the battle coins leaderboard"
    )
    async def show_leaderboard(self, ctx: commands.Context):
        """Show the battle coins leaderboard"""
        # Sort players by currency
        sorted_players = sorted(
            self.player_inventories.items(),
            key=lambda x: x[1].currency,
            reverse=True
        )
        
        embed = discord.Embed(
            title="Battle Coins Leaderboard",
            color=discord.Color.gold()
        )
        
        leaderboard_text = ""
        for i, (user_id, inventory) in enumerate(sorted_players[:10], 1):
            user = self.bot.get_user(user_id)
            username = user.display_name if user else f"User {user_id}"
            
            # Add medal emoji for top 3
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = f"{i}."
                
            leaderboard_text += f"{medal} **{username}**: {inventory.currency} 💰\n"
        
        embed.description = leaderboard_text or "No players yet!"
        
        # Show the requesting user's position
        if ctx.author.id in self.player_inventories:
            user_inventory = self.player_inventories[ctx.author.id]
            user_rank = sorted_players.index((ctx.author.id, user_inventory)) + 1
            embed.set_footer(text=f"Your rank: #{user_rank} | Your coins: {user_inventory.currency} 💰")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="tactic_help",
        description="Get help with the tactical battle game"
    )
    async def tactics_help(self, ctx: commands.Context):
        """Show help information for the tactical battle game"""
        embed = discord.Embed(
            title="Tactical Battle Game Help",
            description="A turn-based tactical battle game with formations and gacha mechanics!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Getting Started",
            value=(
                "1. Collect units through the gacha system\n"
                "2. Build a formation with your best units\n"
                "3. Challenge other players to battles\n"
                "4. Win battles to earn more coins"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Core Commands",
            value=(
                "`/daily` - Get your daily battle coins\n"
                "`/gacha` - Roll for a new unit (costs 100 coins)\n"
                "`/inventory` - View your units\n"
                "`/unit_info [number]` - View details about a unit\n"
                "`/manage_formation` - View formation management info\n"
                "`/unit_position [units] [positions]` - Set unit positions\n"
                "`/battle @player` - Challenge someone to a battle\n"
                "`/accept_battle` - Accept a battle challenge\n"
                "`/leaderboard` - View the top players by coins"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Formation System",
            value=(
                "Units can be placed in two rows:\n"
                "**Front Row (1):** Units that protect the back row\n"
                "**Back Row (2):** Protected units that deal damage safely\n\n"
                "When a Tank or Warrior attacks back row units, they may receive counterattack damage!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Unit Roles",
            value=(
                "🧙 **Mages**: High damage, bonus spell power, ignore 30% armor\n"
                "🛡️ **Tanks**: High health, high armor, protect back row\n"
                "⚔️ **Warriors**: Balanced stats, chance for critical hits"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Unit Stats",
            value=(
                "**Health:** How much damage a unit can take before defeat\n"
                "**Damage:** Base damage dealt by attacks\n"
                "**Armor:** Reduces incoming damage\n"
                "**Special Stat:** Unique bonus based on unit role"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    # Add a new command for formation management
    @commands.hybrid_command(
        name="tactic_manageformation",
        description="Arrange your units into formation for future battles"
    )
    async def manage_formation(self, ctx: commands.Context):
        """Manage your unit formation for battles"""
        user_id = ctx.author.id
        inventory = self.get_player_inventory(user_id)
        
        if len(inventory.units) < 5:
            return await ctx.send("You need at least 5 units to create a formation!")
        
        # Create an embed showing all available units
        embed = discord.Embed(
            title="Formation Management",
            description="Arrange your favorite units into a formation for battles.",
            color=discord.Color.blue()
        )
        
        # List units
        unit_list = ""
        for i, unit in enumerate(inventory.units):
            emoji = ROLE_EMOJIS.get(unit.role, "❓")
            position = "Front Row" if unit.position == 1 else "Back Row"
            unit_list += f"{i+1}. {emoji} **{unit.name}** - {position}\n"
            if i >= 14:  # Show max 15 units
                unit_list += f"*...and {len(inventory.units) - 15} more units*\n"
                break
        
        embed.add_field(name="Your Units", value=unit_list, inline=False)
        embed.add_field(
            name="How to Use",
            value=(
                "To change positions:\n"
                "Use `/unit_position` with the following format:\n"
                "`/unit_position <unit numbers> <positions>`\n\n"
                "Example: `/unit_position 1 5 8 1 2 1` will set:\n"
                "- Unit 1 to front row\n"
                "- Unit 5 to back row\n"
                "- Unit 8 to front row"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="tactic_unitposition",
        description="Set units' positions in your formation"
    )
    async def unit_position(self, ctx: commands.Context, positions: str):
        """
        Set units' positions in your formation
        Format: unit1 unit2 unit3 pos1 pos2 pos3
        Example: 1 5 8 1 2 1
        """
        args = positions.split()
        if len(args) < 2 or len(args) % 2 != 0:
            return await ctx.send("Please provide unit numbers and positions (1=front, 2=back) in pairs.")
        
        user_id = ctx.author.id
        inventory = self.get_player_inventory(user_id)
        
        # Parse arguments
        units_count = len(args) // 2
        unit_indices = []
        position_values = []
        
        for i in range(units_count):
            try:
                unit_index = int(args[i]) - 1
                position = int(args[i + units_count])
                
                if not (0 <= unit_index < len(inventory.units)):
                    return await ctx.send(f"Invalid unit number: {unit_index + 1}")
                    
                if position not in [1, 2]:
                    return await ctx.send(f"Invalid position {position} (must be 1 or 2)")
                    
                unit_indices.append(unit_index)
                position_values.append(position)
            except ValueError:
                return await ctx.send("Arguments must be numbers!")
        
        # Apply changes
        changes = []
        for i, pos in zip(unit_indices, position_values):
            unit = inventory.units[i]
            old_pos = "Front" if unit.position == 1 else "Back"
            new_pos = "Front" if pos == 1 else "Back"
            
            unit.position = pos
            changes.append(f"{unit.name}: {old_pos} → {new_pos}")
        
        # Save changes
        self.save_data()
        
        # Confirm changes
        embed = discord.Embed(
            title="Formation Updated",
            description="\n".join(changes),
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(TacticalBattleGame(bot))
    logger.info("Tactical Battle Game cog loaded successfully")