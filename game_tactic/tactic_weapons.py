import discord
from discord.ext import commands
import random
import asyncio
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import logging
import json
import os

from .tactic_battle import (
    TacticalBattleGame, Unit, UnitRole, UnitRarity, 
    PlayerInventory, RARITY_MULTIPLIERS, RARITY_COLORS, ROLE_EMOJIS
)

logger = logging.getLogger('discord_bot')

# Weapon types enum
class WeaponType(Enum):
    SWORD = "sword"    # For warriors
    MACE = "mace"      # For warriors
    SHIELD = "shield"  # For tanks
    ARMOR = "armor"    # For tanks
    STAFF = "staff"    # For mages
    BOOK = "book"      # For mages

# Weapon compatibility with unit roles
WEAPON_COMPATIBILITY = {
    UnitRole.WARRIOR: [WeaponType.SWORD, WeaponType.MACE],
    UnitRole.TANK: [WeaponType.SHIELD, WeaponType.ARMOR],
    UnitRole.MAGE: [WeaponType.STAFF, WeaponType.BOOK]
}

# Weapon emojis for display
WEAPON_EMOJIS = {
    WeaponType.SWORD: "🗡️",
    WeaponType.MACE: "🔨",
    WeaponType.SHIELD: "🛡️",
    WeaponType.ARMOR: "🥋",
    WeaponType.STAFF: "🪄",
    WeaponType.BOOK: "📕"
}

# Base stats by weapon type
WEAPON_BASE_STATS = {
    WeaponType.SWORD: {"damage": 10, "critical_chance": 5},
    WeaponType.MACE: {"damage": 15, "armor": 3},
    WeaponType.SHIELD: {"armor": 15, "health": 20},
    WeaponType.ARMOR: {"health": 40, "armor": 10},
    WeaponType.STAFF: {"spell_power": 15, "damage": 5},
    WeaponType.BOOK: {"spell_power": 20, "health": 10}
}

# Weapon gacha constants
WEAPON_GACHA_COST = 75
WEAPON_NAME_PREFIXES = {
    UnitRarity.COMMON: ["Basic", "Simple", "Plain", "Crude", "Standard"],
    UnitRarity.RARE: ["Quality", "Sturdy", "Reliable", "Fine", "Improved"],
    UnitRarity.EPIC: ["Mighty", "Superior", "Exceptional", "Radiant", "Enchanted"],
    UnitRarity.LEGENDARY: ["Ancient", "Divine", "Mythical", "Celestial", "Legendary"]
}

WEAPON_NAME_SUFFIXES = {
    WeaponType.SWORD: ["Blade", "Sword", "Saber", "Katana", "Claymore", "Rapier"],
    WeaponType.MACE: ["Mace", "Hammer", "Maul", "Crusher", "Warhammer", "Flail"],
    WeaponType.SHIELD: ["Shield", "Defender", "Bulwark", "Aegis", "Protector"],
    WeaponType.ARMOR: ["Plate", "Armor", "Mail", "Cuirass", "Guardian"],
    WeaponType.STAFF: ["Staff", "Rod", "Wand", "Scepter", "Focus"],
    WeaponType.BOOK: ["Tome", "Codex", "Grimoire", "Spellbook", "Manuscript"]
}

# Special weapon names for legendary weapons
SPECIAL_WEAPON_NAMES = {
    WeaponType.SWORD: ["Excalibur", "Dragonslayer", "Soul Edge", "Frostmourne"],
    WeaponType.MACE: ["Thunderfury", "Doomhammer", "Worldbreaker", "Gorehowl"],
    WeaponType.SHIELD: ["Aegis of Valor", "Bulwark of the Ages", "Divine Protector"],
    WeaponType.ARMOR: ["Dragonscale", "Immortal Plate", "Titan's Embrace"],
    WeaponType.STAFF: ["Staff of Dominion", "Archmage's Glory", "Spellweaver"],
    WeaponType.BOOK: ["Necronomicon", "Compendium Arcana", "Book of Eternity"]
}

class Weapon:
    """Represents a weapon that can be equipped by units to enhance their stats"""
    
    def __init__(self, id: str, name: str, type: WeaponType, rarity: UnitRarity):
        self.id = id
        self.name = name
        self.type = type
        self.rarity = rarity
        self.equipped_by = None  # ID of the unit this weapon is equipped to
        
        # Calculate stats based on weapon type and rarity
        self._calculate_stats()
    
    def _calculate_stats(self):
        """Calculate weapon stats based on type and rarity"""
        base_stats = WEAPON_BASE_STATS[self.type]
        multiplier = RARITY_MULTIPLIERS[self.rarity]
        
        self.stats = {}
        for stat, value in base_stats.items():
            self.stats[stat] = int(value * multiplier)
    
    def to_dict(self) -> dict:
        """Convert weapon to dictionary for storage"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "rarity": self.rarity.value,
            "stats": self.stats,
            "equipped_by": self.equipped_by
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Weapon":
        """Create weapon from dictionary data"""
        weapon = cls(
            id=data["id"],
            name=data["name"],
            type=WeaponType(data["type"]),
            rarity=UnitRarity(data["rarity"])
        )
        
        # Override calculated stats if they exist in the data
        if "stats" in data:
            weapon.stats = data["stats"]
            
        if "equipped_by" in data:
            weapon.equipped_by = data["equipped_by"]
            
        return weapon
    
    def get_stats_text(self) -> str:
        """Get a formatted text of weapon stats"""
        stats_text = []
        for stat, value in self.stats.items():
            # Format each stat nicely
            if stat == "critical_chance":
                stats_text.append(f"+{value}% Crit")
            elif stat == "spell_power":
                stats_text.append(f"+{value} SP")
            elif stat == "health":
                stats_text.append(f"+{value} HP")
            elif stat == "damage":
                stats_text.append(f"+{value} DMG")
            elif stat == "armor":
                stats_text.append(f"+{value} ARM")
            else:
                stat_name = stat.replace("_", " ").title()
                stats_text.append(f"+{value} {stat_name}")
                
        return ", ".join(stats_text)
    
    def is_compatible_with(self, unit: Unit) -> bool:
        """Check if weapon is compatible with the given unit"""
        if unit.role not in WEAPON_COMPATIBILITY:
            return False
        return self.type in WEAPON_COMPATIBILITY[unit.role]

# Extend PlayerInventory to include weapons
def extend_player_inventory():
    """Extend PlayerInventory to handle weapons"""
    
    # Store original methods before patching
    original_init = PlayerInventory.__init__
    original_to_dict = PlayerInventory.to_dict
    original_from_dict = PlayerInventory.from_dict
    
    # Extend __init__ to include weapons list
    def new_init(self, user_id: int):
        original_init(self, user_id)
        self.weapons: List[Weapon] = []
    
    # Add weapon-related methods
    def add_weapon(self, weapon: Weapon):
        """Add a weapon to inventory"""
        self.weapons.append(weapon)

    def get_weapon(self, weapon_id: str) -> Optional[Weapon]:
        """Get a weapon by ID"""
        for weapon in self.weapons:
            if weapon.id == weapon_id:
                return weapon
        return None
    
    # Extend to_dict to include weapons
    def new_to_dict(self) -> dict:
        result = original_to_dict(self)
        result["weapons"] = [weapon.to_dict() for weapon in getattr(self, "weapons", [])]
        return result
    
    # Extend from_dict to load weapons
    @classmethod
    def new_from_dict(cls, data: dict) -> "PlayerInventory":
        inventory = original_from_dict(data)
        inventory.weapons = []
        
        # Load weapons
        for weapon_data in data.get("weapons", []):
            weapon = Weapon.from_dict(weapon_data)
            inventory.weapons.append(weapon)
            
        return inventory
    
    # Apply the extensions
    PlayerInventory.__init__ = new_init
    PlayerInventory.add_weapon = add_weapon
    PlayerInventory.get_weapon = get_weapon
    PlayerInventory.to_dict = new_to_dict
    PlayerInventory.from_dict = new_from_dict
    
    return PlayerInventory

# Patch the Unit class to add weapon support
def patch_unit_class():
    """Add weapon support to the Unit class"""
    
    # Store the original to_dict method
    original_to_dict = Unit.to_dict
    
    # Create new methods for Unit class
    def unit_to_dict(self) -> dict:
        """Extended to_dict to include weapon"""
        result = original_to_dict(self)
        
        # Add weapon ID if equipped
        if hasattr(self, "weapon") and self.weapon is not None:
            result["weapon_id"] = self.weapon.id
            
        return result
    
    def equip_weapon(self, weapon: Weapon) -> Tuple[bool, Optional[Weapon]]:
        """Equip a weapon to this unit"""
        # Check compatibility
        if not weapon.is_compatible_with(self):
            return False, None
        
        # Store old weapon if any
        old_weapon = getattr(self, "weapon", None)
        
        # Equip new weapon
        self.weapon = weapon
        weapon.equipped_by = self.id
        
        # Apply weapon stats
        self._apply_weapon_stats()
        
        return True, old_weapon
    
    def unequip_weapon(self) -> Optional[Weapon]:
        """Unequip the weapon from this unit"""
        if not hasattr(self, "weapon") or self.weapon is None:
            return None
            
        weapon = self.weapon
        
        # Store the weapon stats before removing references
        weapon_stats = weapon.stats.copy()
        
        # Remove references
        self.weapon = None
        weapon.equipped_by = None
        
        # Remove weapon stat bonuses using the stored stats
        for stat, value in weapon_stats.items():
            if stat == "health":
                self.max_health -= value
                current_health = getattr(self, "current_health", self.max_health)
                self.current_health = min(current_health - value, self.max_health)
                self.current_health = max(1, self.current_health)  # Ensure at least 1 health
            elif stat == "damage":
                self.damage -= value
                self.damage = max(1, self.damage)  # Ensure at least 1 damage
            elif stat == "armor":
                self.armor -= value
                self.armor = max(0, self.armor)  # Ensure non-negative armor
            elif stat == "spell_power" and self.role == UnitRole.MAGE:
                self.spell_power = getattr(self, "spell_power", 0) - value
                self.spell_power = max(0, self.spell_power)
            elif stat == "critical_chance" and self.role == UnitRole.WARRIOR:
                self.critical_chance = getattr(self, "critical_chance", 0) - value
                self.critical_chance = max(0, self.critical_chance)
        
        return weapon
    
    def _apply_weapon_stats(self):
        """Apply weapon stat bonuses to the unit"""
        if not hasattr(self, "weapon") or self.weapon is None:
            return
            
        weapon = self.weapon
        
        # Apply each stat from the weapon
        for stat, value in weapon.stats.items():
            if stat == "health":
                self.max_health += value
                self.current_health = getattr(self, "current_health", self.max_health)
                self.current_health += value
            elif stat == "damage":
                self.damage += value
            elif stat == "armor":
                self.armor += value
            elif stat == "spell_power" and self.role == UnitRole.MAGE:
                self.spell_power = getattr(self, "spell_power", 0) + value
            elif stat == "critical_chance" and self.role == UnitRole.WARRIOR:
                self.critical_chance = getattr(self, "critical_chance", 0) + value
    
    def _remove_weapon_stats(self):
        """Remove weapon stat bonuses from the unit"""
        if not hasattr(self, "weapon") or self.weapon is None:
            return
            
        weapon = self.weapon
        
        # Remove each stat from the weapon
        for stat, value in weapon.stats.items():
            if stat == "health":
                self.max_health -= value
                current_health = getattr(self, "current_health", self.max_health)
                self.current_health = min(current_health - value, self.max_health)
                self.current_health = max(1, self.current_health)  # Ensure at least 1 health
            elif stat == "damage":
                self.damage -= value
                self.damage = max(1, self.damage)  # Ensure at least 1 damage
            elif stat == "armor":
                self.armor -= value
                self.armor = max(0, self.armor)  # Ensure non-negative armor
            elif stat == "spell_power" and self.role == UnitRole.MAGE:
                self.spell_power = getattr(self, "spell_power", 0) - value
                self.spell_power = max(0, self.spell_power)
            elif stat == "critical_chance" and self.role == UnitRole.WARRIOR:
                self.critical_chance = getattr(self, "critical_chance", 0) - value
                self.critical_chance = max(0, self.critical_chance)
    
    def has_weapon(self) -> bool:
        """Check if unit has a weapon equipped"""
        return hasattr(self, "weapon") and self.weapon is not None
    
    def get_weapon_display(self) -> str:
        """Get a display text for the equipped weapon"""
        if not self.has_weapon():
            return "None"
            
        weapon = self.weapon
        emoji = WEAPON_EMOJIS.get(weapon.type, "🔮")
        return f"{emoji} {weapon.name} ({weapon.rarity.value.capitalize()})"
    
    # Add the methods to the Unit class
    Unit.to_dict = unit_to_dict
    Unit.equip_weapon = equip_weapon
    Unit.unequip_weapon = unequip_weapon
    Unit._apply_weapon_stats = _apply_weapon_stats
    Unit._remove_weapon_stats = _remove_weapon_stats
    Unit.has_weapon = has_weapon
    Unit.get_weapon_display = get_weapon_display
    
    return Unit

class IntegratedWeaponSystem(commands.Cog):
    """Discord cog that extends TacticalBattleGame with an integrated weapon system"""
    
    def __init__(self, bot: commands.Bot, battle_cog: TacticalBattleGame):
        self.bot = bot
        self.battle_cog = battle_cog
        
        # Extend PlayerInventory to handle weapons
        extend_player_inventory()
        
        # Add weapon features to Unit class
        patch_unit_class()
        
        # Create weapon database
        self.create_weapon_database()
        
        # Connect weapons to units
        self._reconnect_weapons()
        
        # Replace inventory command with the enhanced version
        self._replace_inventory_command()
        
    def create_weapon_database(self):
        """Create default weapons or load from file"""
        try:
            weapons_file = os.path.join(self.battle_cog.data_folder, "weapons.json")
            if os.path.exists(weapons_file):
                with open(weapons_file, "r") as f:
                    weapons_data = json.load(f)
                    for inventory in self.battle_cog.player_inventories.values():
                        inventory.weapons = []  # Clear any existing weapons
                    
                    # Process each weapon from the database
                    for weapon_data in weapons_data:
                        weapon = Weapon.from_dict(weapon_data)
                        if weapon.id.startswith("p"):
                            # Extract player ID from weapon ID
                            try:
                                # Format: p{user_id}_wpn_...
                                user_id = int(weapon.id.split("_")[0][1:])
                                if user_id in self.battle_cog.player_inventories:
                                    self.battle_cog.player_inventories[user_id].add_weapon(weapon)
                            except:
                                logger.error(f"Could not determine owner of weapon {weapon.id}")
            else:
                # Create default weapons if file doesn't exist
                self._create_default_weapons()
                
            # Save weapons after loading/creating
            self.save_weapon_data()
                
        except Exception as e:
            logger.error(f"Error loading weapon database: {e}")
            self._create_default_weapons()
    
    def _create_default_weapons(self):
        """Create default weapons for each player"""
        logger.info("Creating default weapons for players")
        
        # Add starter weapons for each player
        for user_id, inventory in self.battle_cog.player_inventories.items():
            # Give 2 basic weapons based on player's units
            inventory.weapons = []  # Clear any existing weapons
            
            # Find player's roles
            player_roles = set()
            for unit in inventory.units:
                player_roles.add(unit.role)
            
            # Give appropriate weapons for each role
            for role in player_roles:
                if role in WEAPON_COMPATIBILITY:
                    weapon_types = WEAPON_COMPATIBILITY[role]
                    weapon_type = weapon_types[0]  # Choose first compatible type
                    
                    # Create a common weapon of this type
                    weapon_name = f"{random.choice(WEAPON_NAME_PREFIXES[UnitRarity.COMMON])} {random.choice(WEAPON_NAME_SUFFIXES[weapon_type])}"
                    weapon_id = f"p{user_id}_wpn_{len(inventory.weapons):03d}_{random.randint(1000, 9999)}"
                    weapon = Weapon(weapon_id, weapon_name, weapon_type, UnitRarity.COMMON)
                    inventory.add_weapon(weapon)
    
    def save_weapon_data(self):
        """Save all weapon data"""
        try:
            # Collect all weapons from all player inventories
            all_weapons = []
            for inventory in self.battle_cog.player_inventories.values():
                all_weapons.extend(inventory.weapons)
                
            weapons_file = os.path.join(self.battle_cog.data_folder, "weapons.json")
            with open(weapons_file, "w") as f:
                json.dump([weapon.to_dict() for weapon in all_weapons], f, indent=2)
                
            # Also save player inventories
            self.battle_cog.save_data()
            
        except Exception as e:
            logger.error(f"Error saving weapon data: {e}")
    
    def _reconnect_weapons(self):
        """Reconnect weapons to units after loading data"""
        for inventory in self.battle_cog.player_inventories.values():
            # Create dict of weapon IDs to weapons
            weapon_dict = {w.id: w for w in inventory.weapons}
            
            # Check each unit for a weapon reference and reconnect
            for unit in inventory.units:
                unit_dict = unit.to_dict()
                if "weapon_id" in unit_dict and unit_dict["weapon_id"] in weapon_dict:
                    weapon = weapon_dict[unit_dict["weapon_id"]]
                    unit.weapon = weapon
                    weapon.equipped_by = unit.id
    
    def _replace_inventory_command(self):
        """Replace the inventory command with our enhanced version"""
        # Find and remove the original command
        for command in self.battle_cog.get_commands():
            if command.name == "tactic_inventory":
                self.battle_cog.remove_command("tactic_inventory")
                break
                
        # Add our enhanced version
        @commands.hybrid_command(
            name="tactic_inventory",
            description="View your units and weapons inventory"
        )
        async def show_inventory(ctx: commands.Context):
            """Show your unit and weapon inventory with enhanced visuals"""
            user_id = ctx.author.id
            inventory = self.battle_cog.get_player_inventory(user_id)
            
            # Empty inventory case
            if not inventory.units and not inventory.weapons:
                embed = discord.Embed(
                    title="📋 Your Inventory",
                    description="You don't have any items yet!",
                    color=discord.Color.blue()
                )
                embed.add_field(name="💰 Battle Coins", value=f"**{inventory.currency}**", inline=False)
                embed.add_field(
                    name="Getting Started", 
                    value="• Use `/tactic_gacha` to get units\n• Use `/tactic_weapongacha` to get weapons", 
                    inline=False
                )
                embed.set_footer(text="Return daily to claim your rewards!")
                return await ctx.send(embed=embed)

            # UNITS DISPLAY
            units_embed = discord.Embed(
                title=f"📋 {ctx.author.display_name}'s Unit Collection",
                color=discord.Color.blue()
            )
            units_embed.add_field(name="💰 Battle Coins", value=f"**{inventory.currency}**", inline=False)
            
            # Group units by rarity for better display, but keep original positions for IDs
            units_by_rarity = {}
            for unit_index, unit in enumerate(inventory.units):
                if unit.rarity not in units_by_rarity:
                    units_by_rarity[unit.rarity] = []
                # Store the unit along with its actual position in the inventory array
                units_by_rarity[unit.rarity].append((unit_index, unit))
            
            # Sort rarities from highest to lowest
            rarity_order = {
                UnitRarity.LEGENDARY: 4,
                UnitRarity.EPIC: 3, 
                UnitRarity.RARE: 2, 
                UnitRarity.COMMON: 1
            }
            sorted_rarities = sorted(units_by_rarity.keys(), key=lambda r: rarity_order.get(r, 0), reverse=True)
            
            # Rarity decoration symbols
            rarity_decorations = {
                UnitRarity.COMMON: "⚪",
                UnitRarity.RARE: "🔵",
                UnitRarity.EPIC: "🟣",
                UnitRarity.LEGENDARY: "🟡"
            }
            
            # Add units grouped by rarity with enhanced formatting and preserving actual IDs
            for rarity in sorted_rarities:
                units = sorted(units_by_rarity[rarity], key=lambda u: u[1].name)
                rarity_symbol = rarity_decorations.get(rarity, "⚪")
                rarity_text = rarity.value.capitalize()
                field_header = f"{rarity_symbol} {rarity_text} Units ({len(units)})"
                
                unit_list = []
                for unit_index, unit in units:
                    emoji = ROLE_EMOJIS.get(unit.role, "❓")
                    
                    # Check for equipped weapon
                    weapon_icon = "🔗" if unit.has_weapon() else ""
                    
                    # Format: ID. [Emoji] Name [Weapon Icon] - Health/Damage  
                    # Use original position + 1 as the displayed ID
                    unit_list.append(f"`{unit_index + 1:2d}.` {emoji} **{unit.name}** {weapon_icon} - HP:{unit.max_health} DMG:{unit.damage}")
                    
                    # Break into multiple fields if too many units
                    if len(unit_list) >= 10 and len(unit_list) < len(units):
                        units_embed.add_field(
                            name=field_header if len(unit_list) <= 10 else f"{rarity_symbol} {rarity_text} Units (cont.)",
                            value="\n".join(unit_list),
                            inline=False
                        )
                        unit_list = []
                        
                # Add remaining units
                if unit_list:
                    units_embed.add_field(
                        name=field_header,
                        value="\n".join(unit_list),
                        inline=False
                    )
                        
            # WEAPONS DISPLAY
            weapons_embed = discord.Embed(
                title=f"🔷 {ctx.author.display_name}'s Weapon Collection",
                color=discord.Color.dark_gold()
            )
            
            # Group weapons by equipped status while preserving original indices
            equipped_weapons = []
            unequipped_weapons = []
            for weapon_index, weapon in enumerate(inventory.weapons):
                if weapon.equipped_by:
                    equipped_weapons.append((weapon_index, weapon))
                else:
                    unequipped_weapons.append((weapon_index, weapon))
            
            # Show equipped weapons first - sorted by rarity
            if equipped_weapons:
                equipped_by_rarity = {}
                for weapon_index, weapon in equipped_weapons:
                    if weapon.rarity not in equipped_by_rarity:
                        equipped_by_rarity[weapon.rarity] = []
                    equipped_by_rarity[weapon.rarity].append((weapon_index, weapon))
                    
                sorted_rarities = sorted(
                    equipped_by_rarity.keys(),
                    key=lambda r: rarity_order.get(r, 0),
                    reverse=True
                )
                
                for rarity in sorted_rarities:
                    weapons = equipped_by_rarity[rarity]
                    rarity_symbol = rarity_decorations.get(rarity, "⚪")
                    weapons_text = []
                    
                    for weapon_index, weapon in weapons:
                        weapon_emoji = WEAPON_EMOJIS.get(weapon.type, "🔮")
                        # Find which unit has this weapon
                        unit_name = "Unknown"
                        for unit in inventory.units:
                            if hasattr(unit, "weapon") and unit.weapon and unit.weapon.id == weapon.id:
                                unit_name = unit.name
                                break
                                
                        # Use original position + 1 as the displayed ID
                        weapons_text.append(
                            f"`{weapon_index + 1}.` {weapon_emoji} **{weapon.name}** ({rarity.value.capitalize()})\n" +
                            f"┗━► Equipped on: *{unit_name}*\n" +
                            f"┗━► Stats: {weapon.get_stats_text()}"
                        )
                    
                    weapons_embed.add_field(
                        name=f"{rarity_symbol} Equipped {rarity.value.capitalize()} Weapons",
                        value="\n".join(weapons_text),
                        inline=False
                    )
            
            # Show unequipped weapons grouped by rarity with actual indices
            if unequipped_weapons:
                unequipped_by_rarity = {}
                for weapon_index, weapon in unequipped_weapons:
                    if weapon.rarity not in unequipped_by_rarity:
                        unequipped_by_rarity[weapon.rarity] = []
                    unequipped_by_rarity[weapon.rarity].append((weapon_index, weapon))
                    
                sorted_rarities = sorted(
                    unequipped_by_rarity.keys(),
                    key=lambda r: rarity_order.get(r, 0),
                    reverse=True
                )
                
                for rarity in sorted_rarities:
                    weapons = unequipped_by_rarity[rarity]
                    rarity_symbol = rarity_decorations.get(rarity, "⚪")
                    
                    weapons_text = []
                    for weapon_index, weapon in weapons:
                        weapon_emoji = WEAPON_EMOJIS.get(weapon.type, "🔮")
                        # Use original position + 1 as the displayed ID
                        weapons_text.append(
                            f"`{weapon_index + 1:2d}.` {weapon_emoji} **{weapon.name}** - {weapon.get_stats_text()}"
                        )
                    
                    weapons_embed.add_field(
                        name=f"{rarity_symbol} Available {rarity.value.capitalize()} Weapons ({len(weapons)})",
                        value="\n".join(weapons_text) if weapons_text else "None",
                        inline=False
                    )
            
            # Add helpful command information
            help_text = (
                "**Commands:**\n"
                "• `/tactic_equip [unit_id] [weapon_id]` - Equip a weapon\n"
                "• `/tactic_unequip [unit_id]` - Remove a weapon\n"
                "• `/tactic_unitequipment [unit_id]` - View detailed stats\n"
                "• `/tactic_weaponhelp` - View weapon system help\n"
                "• `/tactic_sell unit/weapon [id]` - Sell for coins"
            )
            
            weapons_embed.add_field(name="⚙️ Weapon Management", value=help_text, inline=False)
            weapons_embed.set_footer(text="Numbers shown are the exact IDs to use with the commands")
            
            # Send both embeds
            await ctx.send(embed=units_embed)
            await ctx.send(embed=weapons_embed)
        
        # Register the new command
        self.battle_cog.walk_commands = lambda: [show_inventory] + [cmd for cmd in self.battle_cog.get_commands() if cmd.name != "tactic_inventory"]
        self.battle_cog.show_inventory = show_inventory
        self.battle_cog.add_command(show_inventory)
    
    @commands.hybrid_command(
        name="tactic_weapongacha",
        description=f"Roll for a new weapon (costs {WEAPON_GACHA_COST} battle coins)"
    )
    async def weapon_gacha_roll(self, ctx: commands.Context):
        """Roll the gacha to get a new weapon"""
        user_id = ctx.author.id
        inventory = self.battle_cog.get_player_inventory(user_id)
        
        # Check if player has enough currency
        if inventory.currency < WEAPON_GACHA_COST:
            embed = discord.Embed(
                title="Not Enough Coins",
                description=f"You need {WEAPON_GACHA_COST} battle coins to roll. You only have {inventory.currency}.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Show rolling animation
        message = await ctx.send("🎲 Rolling weapon gacha...")
        
        # Add some suspense
        for _ in range(3):
            await asyncio.sleep(0.7)
            await message.edit(content=message.content + ".")
        
        # Perform the roll
        weapon = self.perform_weapon_gacha_roll(user_id)
        
        # Create embed based on rarity
        emoji = WEAPON_EMOJIS.get(weapon.type, "🔮")
        color = RARITY_COLORS.get(weapon.rarity, discord.Color.default())
        
        embed = discord.Embed(
            title=f"🎉 New Weapon Acquired: {weapon.name} {emoji}",
            color=color
        )
        embed.add_field(name="Type", value=f"{emoji} {weapon.type.value.capitalize()}", inline=True)
        embed.add_field(name="Rarity", value=weapon.rarity.value.capitalize(), inline=True)
        embed.add_field(name="Stats", value=weapon.get_stats_text(), inline=False)
        
        # Show which roles can use this weapon
        compatible_roles = [role for role, types in WEAPON_COMPATIBILITY.items() if weapon.type in types]
        if compatible_roles:
            roles_text = ", ".join([f"{ROLE_EMOJIS.get(role, '❓')} {role.value.capitalize()}" for role in compatible_roles])
            embed.add_field(name="Compatible Roles", value=roles_text, inline=False)
        
        embed.set_footer(text=f"You now have {inventory.currency} battle coins")
        
        await message.edit(content=None, embed=embed)
    
    def perform_weapon_gacha_roll(self, user_id: int) -> Weapon:
        """Perform a weapon gacha roll and add weapon to player inventory"""
        inventory = self.battle_cog.get_player_inventory(user_id)
        
        # Deduct currency
        inventory.currency -= WEAPON_GACHA_COST
        
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
        
        # Select a weapon type randomly
        weapon_type = random.choice(list(WeaponType))
        
        # Generate weapon name
        if rarity == UnitRarity.LEGENDARY and random.random() < 0.3:
            special_names = SPECIAL_WEAPON_NAMES.get(weapon_type, [])
            if special_names:
                name = random.choice(special_names)
            else:
                prefix = random.choice(WEAPON_NAME_PREFIXES[rarity])
                suffix = random.choice(WEAPON_NAME_SUFFIXES[weapon_type])
                name = f"{prefix} {suffix}"
        else:
            prefix = random.choice(WEAPON_NAME_PREFIXES[rarity])
            suffix = random.choice(WEAPON_NAME_SUFFIXES[weapon_type])
            name = f"{prefix} {suffix}"
        
        # Create the weapon
        weapon_id = f"p{user_id}_wpn_{len(inventory.weapons) + 1:03d}_{random.randint(1000, 9999)}"
        weapon = Weapon(weapon_id, name, weapon_type, rarity)
        
        # Add to inventory
        inventory.add_weapon(weapon)
        self.save_weapon_data()
        
        return weapon
    
    @commands.hybrid_command(
        name="tactic_equip",
        description="Equip a weapon to one of your units"
    )
    async def equip_weapon(self, ctx: commands.Context, unit_id: int, weapon_id: int):
        """Equip a weapon to a unit using the continuous numbering from inventory"""
        user_id = ctx.author.id
        inventory = self.battle_cog.get_player_inventory(user_id)
        
        # Get all unequipped weapons
        unequipped_weapons = [w for w in inventory.weapons if not w.equipped_by]
        
        # Validate unit ID
        if unit_id < 1 or unit_id > len(inventory.units):
            return await ctx.send(f"Invalid unit ID. You have {len(inventory.units)} units.")
        
        # Validate weapon ID
        if weapon_id < 1 or weapon_id > len(unequipped_weapons):
            return await ctx.send(f"Invalid weapon ID. You have {len(unequipped_weapons)} available weapons.")
        
        # Get the selected unit and weapon
        unit = inventory.units[unit_id - 1]
        weapon = unequipped_weapons[weapon_id - 1]
        
        # Check compatibility
        if not weapon.is_compatible_with(unit):
            weapon_type_name = weapon.type.value.capitalize()
            unit_role_name = unit.role.value.capitalize()
            return await ctx.send(
                f"❌ {weapon_type_name} weapons are not compatible with {unit_role_name} units."
            )
        
        # Equip weapon
        success, old_weapon = unit.equip_weapon(weapon)
        if not success:
            return await ctx.send("Failed to equip weapon.")
        
        # Save changes
        self.save_weapon_data()
        
        # Create success message
        embed = discord.Embed(
            title=f"Weapon Equipped",
            description=f"{WEAPON_EMOJIS.get(weapon.type, '🔮')} **{weapon.name}** has been equipped to {unit.name}!",
            color=discord.Color.green()
        )
        
        # If a weapon was replaced
        if old_weapon:
            embed.add_field(
                name="Replaced Weapon",
                value=f"{WEAPON_EMOJIS.get(old_weapon.type, '🔮')} **{old_weapon.name}** was unequipped.",
                inline=False
            )
        
        # Show stat changes
        embed.add_field(
            name="Stat Bonuses",
            value=weapon.get_stats_text(),
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="tactic_unequip",
        description="Unequip a weapon from one of your units"
    )
    async def unequip_weapon(self, ctx: commands.Context, unit_id: int):
        """Unequip a weapon from a unit"""
        user_id = ctx.author.id
        inventory = self.battle_cog.get_player_inventory(user_id)
        
        # Validate unit ID
        if unit_id < 1 or unit_id > len(inventory.units):
            return await ctx.send(f"Invalid unit ID. You have {len(inventory.units)} units.")
        
        unit = inventory.units[unit_id - 1]
        
        # Check if unit has weapon equipped
        if not hasattr(unit, "weapon") or not unit.weapon:
            return await ctx.send(f"{unit.name} doesn't have a weapon equipped.")
        
        # Get weapon info before unequipping
        weapon = unit.weapon
        weapon_name = weapon.name
        weapon_emoji = WEAPON_EMOJIS.get(weapon.type, "🔮")
        stats_text = weapon.get_stats_text()
        
        # Unequip weapon
        unit.unequip_weapon()
        
        # Save changes
        self.save_weapon_data()
        
        # Create success message
        embed = discord.Embed(
            title=f"Weapon Unequipped",
            description=f"{weapon_emoji} **{weapon_name}** has been unequipped from {unit.name}.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Lost Bonuses",
            value=stats_text,
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="tactic_unitequipment",
        description="View detailed equipment information for one of your units"
    )
    async def unit_equipment(self, ctx: commands.Context, unit_id: int):
        """View detailed equipment info for a unit with enhanced visuals"""
        user_id = ctx.author.id
        inventory = self.battle_cog.get_player_inventory(user_id)
        
        # Validate unit ID
        if unit_id < 1 or unit_id > len(inventory.units):
            return await ctx.send(f"Invalid unit ID. You have {len(inventory.units)} units.")
        
        unit = inventory.units[unit_id - 1]
        
        # Create embed
        emoji = ROLE_EMOJIS.get(unit.role, "❓")
        color = RARITY_COLORS.get(unit.rarity, discord.Color.default())
        
        # Rarity decoration symbols
        rarity_decorations = {
            UnitRarity.COMMON: "⚪",
            UnitRarity.RARE: "🔵",
            UnitRarity.EPIC: "🟣",
            UnitRarity.LEGENDARY: "🟡"
        }
        rarity_symbol = rarity_decorations.get(unit.rarity, "⚪")
        
        embed = discord.Embed(
            title=f"{emoji} {unit.name}",
            description=f"{rarity_symbol} **{unit.rarity.value.capitalize()} {unit.role.value.capitalize()}**",
            color=color
        )
        
        # Add a small divider
        embed.add_field(name="", value="📊 **Base Statistics**", inline=False)
        
        # Show stats with icons
        embed.add_field(name="❤️ Health", value=f"**{unit.max_health}**", inline=True)
        embed.add_field(name="⚔️ Damage", value=f"**{unit.damage}**", inline=True)
        embed.add_field(name="🛡️ Armor", value=f"**{unit.armor}**", inline=True)
        
        # Show special attribute
        special_attr_name, special_attr_value = unit.get_special_attribute()
        if "Critical" in special_attr_name:
            embed.add_field(name=f"🎯 {special_attr_name}", value=f"**{special_attr_value}%**", inline=True)
        elif "Spell Power" in special_attr_name:
            embed.add_field(name=f"✨ {special_attr_name}", value=f"**{special_attr_value}**", inline=True)
        else:
            embed.add_field(name=f"⚡ {special_attr_name}", value=f"**{special_attr_value}**", inline=True)
        
        # Add equipment section divider
        embed.add_field(name="", value="🔸 **Equipment**", inline=False)
        
        # Show equipped weapon
        if unit.has_weapon():
            weapon = unit.weapon
            weapon_emoji = WEAPON_EMOJIS.get(weapon.type, "🔮")
            rarity_symbol = rarity_decorations.get(weapon.rarity, "⚪")
            
            # Format weapon stats nicely with icons
            stats_lines = []
            for stat, value in weapon.stats.items():
                if stat == "damage":
                    stats_lines.append(f"⚔️ +{value} Damage")
                elif stat == "health":
                    stats_lines.append(f"❤️ +{value} Health")
                elif stat == "armor":
                    stats_lines.append(f"🛡️ +{value} Armor")
                elif stat == "critical_chance":
                    stats_lines.append(f"🎯 +{value}% Critical")
                elif stat == "spell_power":
                    stats_lines.append(f"✨ +{value} Spell Power")
                else:
                    stats_lines.append(f"⚡ +{value} {stat.replace('_', ' ').title()}")
            
            stats_text = "\n".join(stats_lines)
            
            embed.add_field(
                name=f"{weapon_emoji} {weapon.name}",
                value=f"{rarity_symbol} *{weapon.rarity.value.capitalize()} {weapon.type.value.capitalize()}*\n{stats_text}",
                inline=False
            )
        else:
            embed.add_field(
                name="No Weapon Equipped",
                value="Equip a weapon to enhance this unit's stats!",
                inline=False
            )
        
        # Show compatible weapon types
        if unit.role in WEAPON_COMPATIBILITY:
            compatible_types = WEAPON_COMPATIBILITY[unit.role]
            compatible_text = ", ".join([f"{WEAPON_EMOJIS.get(t, '🔮')} {t.value.capitalize()}" for t in compatible_types])
            
            embed.add_field(
                name="Compatible Weapon Types",
                value=compatible_text,
                inline=False
            )
        
        # Add tips at the bottom
        if unit.has_weapon():
            tip = f"Use `/tactic_unequip {unit_id}` to remove the weapon"
        else:
            tip = f"Use `/tactic_equip {unit_id} [weapon_id]` to equip a weapon"
        
        embed.set_footer(text=tip)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="tactic_weaponhelp",
        description="Get help with the weapon system"
    )
    async def weapon_help(self, ctx: commands.Context):
        """Show help information for the weapon system"""
        embed = discord.Embed(
            title="Weapons System Help",
            description="Enhance your units with powerful weapons to gain an advantage in battle!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Getting Started",
            value=(
                f"1. Get weapons with `/tactic_weapongacha` (costs {WEAPON_GACHA_COST} coins)\n"
                f"2. View your units and weapons with `/tactic_inventory`\n"
                f"3. Equip weapons to compatible units with `/tactic_equip`\n"
                f"4. Remove weapons with `/tactic_unequip` if needed"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Weapon Types & Compatibility",
            value=(
                f"{WEAPON_EMOJIS[WeaponType.SWORD]} **Swords** - For Warriors: +Damage, +Critical Chance\n"
                f"{WEAPON_EMOJIS[WeaponType.MACE]} **Maces** - For Warriors: +Damage, +Armor\n"
                f"{WEAPON_EMOJIS[WeaponType.SHIELD]} **Shields** - For Tanks: +Armor, +Health\n"
                f"{WEAPON_EMOJIS[WeaponType.ARMOR]} **Armor** - For Tanks: +Health, +Armor\n"
                f"{WEAPON_EMOJIS[WeaponType.STAFF]} **Staves** - For Mages: +Spell Power, +Damage\n"
                f"{WEAPON_EMOJIS[WeaponType.BOOK]} **Books** - For Mages: +Spell Power, +Health"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Commands",
            value=(
                "`/tactic_inventory` - View your units and available weapons\n"
                "`/tactic_weapongacha` - Roll for a new weapon\n"
                "`/tactic_equip [unit_id] [weapon_id]` - Equip a weapon\n"
                "`/tactic_unequip [unit_id]` - Remove a weapon\n"
                "`/tactic_unitequipment [unit_id]` - View detailed equipment info"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Numbering System",
            value=(
                "The inventory now uses continuous numbering for easier reference:\n"
                "- Units are numbered from 1 to N\n"
                "- Weapons are numbered from 1 to M\n"
                "Use these ID numbers when equipping or unequipping items."
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="tactic_sell",
        description="Sell a unit or weapon from your inventory for battle coins"
    )
    async def sell_item(self, ctx: commands.Context, item_type: str, item_id: int):
        """
        Sell a unit or weapon to gain battle coins
        Parameters:
        - item_type: "unit" or "weapon" - what you want to sell
        - item_id: ID number of the item from your inventory
        """
        user_id = ctx.author.id
        inventory = self.battle_cog.get_player_inventory(user_id)
        
        # Set up sale prices based on rarity
        sell_prices = {
            UnitRarity.COMMON: 25,
            UnitRarity.RARE: 50,
            UnitRarity.EPIC: 100,
            UnitRarity.LEGENDARY: 200
        }
        
        # Lowercase and validate item type
        item_type = item_type.lower()
        if item_type not in ["unit", "weapon"]:
            return await ctx.send("❌ Invalid item type. Please specify 'unit' or 'weapon'.")
        
        # Handle selling weapons
        if item_type == "weapon":
            # Validate weapon ID
            if item_id < 1 or item_id > len(inventory.weapons):
                return await ctx.send(f"❌ Invalid weapon ID. You have {len(inventory.weapons)} weapons.")
            
            weapon = inventory.weapons[item_id - 1]
            
            # Check if the weapon is equipped
            if weapon.equipped_by:
                return await ctx.send("❌ You can't sell an equipped weapon. Unequip it first with `/tactic_unequip`.")
            
            # Get price based on rarity
            price = sell_prices.get(weapon.rarity, 10)  # Default to 10 if rarity not found
            
            # Ask for confirmation
            embed = discord.Embed(
                title="🔶 Confirm Sale",
                description=f"Are you sure you want to sell your {weapon.rarity.value.capitalize()} weapon **{weapon.name}** for **{price}** battle coins?",
                color=discord.Color.gold()
            )
            embed.add_field(name="Stats", value=weapon.get_stats_text(), inline=False)
            embed.set_footer(text="Reply with 'yes' to confirm or 'no' to cancel (30s)")
            
            confirmation_message = await ctx.send(embed=embed)
            
            # Wait for confirmation
            try:
                def check(m):
                    return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id and m.content.lower() in ["yes", "no"]
                
                response = await self.bot.wait_for("message", check=check, timeout=30.0)
                
                if response.content.lower() == "yes":
                    # Remove the weapon
                    inventory.weapons.remove(weapon)
                    
                    # Add coins
                    inventory.currency += price
                    
                    # Save changes
                    self.save_weapon_data()
                    
                    embed = discord.Embed(
                        title="💰 Weapon Sold",
                        description=f"You sold your {weapon.rarity.value.capitalize()} weapon **{weapon.name}** for **{price}** battle coins.",
                        color=discord.Color.green()
                    )
                    embed.set_footer(text=f"You now have {inventory.currency} battle coins")
                    await confirmation_message.edit(embed=embed)
                    
                else:
                    await confirmation_message.edit(content="Sale canceled.", embed=None)
                    
            except asyncio.TimeoutError:
                await confirmation_message.edit(content="Sale timed out.", embed=None)
            
        # Handle selling units
        elif item_type == "unit":
            # Validate unit ID
            if item_id < 1 or item_id > len(inventory.units):
                return await ctx.send(f"❌ Invalid unit ID. You have {len(inventory.units)} units.")
            
            unit = inventory.units[item_id - 1]
            
            # Check if player has enough units left (minimum 3 required)
            if len(inventory.units) <= 5:
                return await ctx.send("❌ You can't sell more units! You need at least 5 units in your collection.")
            
            # Check if unit has a weapon
            if unit.has_weapon():
                return await ctx.send("❌ This unit has a weapon equipped. Unequip it first with `/tactic_unequip`.")
            
            # Get price based on rarity
            price = sell_prices.get(unit.rarity, 10)  # Default to 10 if rarity not found
            
            # Ask for confirmation
            embed = discord.Embed(
                title="🔶 Confirm Sale",
                description=f"Are you sure you want to sell your {unit.rarity.value.capitalize()} unit **{unit.name}** for **{price}** battle coins?",
                color=discord.Color.gold()
            )
            embed.add_field(name="Stats", value=f"HP: {unit.max_health} | DMG: {unit.damage} | ARM: {unit.armor}", inline=False)
            embed.set_footer(text="Reply with 'yes' to confirm or 'no' to cancel (30s)")
            
            confirmation_message = await ctx.send(embed=embed)
            
            # Wait for confirmation
            try:
                def check(m):
                    return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id and m.content.lower() in ["yes", "no"]
                
                response = await self.bot.wait_for("message", check=check, timeout=30.0)
                
                if response.content.lower() == "yes":
                    # Remove the unit
                    inventory.units.remove(unit)
                    
                    # Add coins
                    inventory.currency += price
                    
                    # Save changes
                    self.battle_cog.save_data()
                    
                    embed = discord.Embed(
                        title="💰 Unit Sold",
                        description=f"You sold your {unit.rarity.value.capitalize()} unit **{unit.name}** for **{price}** battle coins.",
                        color=discord.Color.green()
                    )
                    embed.set_footer(text=f"You now have {inventory.currency} battle coins")
                    await confirmation_message.edit(embed=embed)
                    
                else:
                    await confirmation_message.edit(content="Sale canceled.", embed=None)
                    
            except asyncio.TimeoutError:
                await confirmation_message.edit(content="Sale timed out.", embed=None)

async def setup(bot: commands.Bot):
    # Find the TacticalBattleGame cog
    battle_cog = None
    for cog in bot.cogs.values():
        if isinstance(cog, TacticalBattleGame):
            battle_cog = cog
            break
    
    if not battle_cog:
        logger.error("TacticalBattleGame cog not found! Weapon system cannot be loaded.")
        return
    
    # Add the integrated weapon system
    await bot.add_cog(IntegratedWeaponSystem(bot, battle_cog))
    logger.info("Integrated Weapon System loaded successfully")