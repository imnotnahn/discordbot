# Discord Game & Utility Bot

A feature-rich Discord bot built with discord.py that offers a variety of board games, language learning tools, voice channel management, and AI chat capabilities.

![Discord Bot](https://i.imgur.com/JOKsECQ.png)

## Features

### Board Games
The bot includes several classic board games that can be played directly in Discord:

- **Cờ Cá Ngựa (Ludo)** - A classic race board game where players roll dice to move their pieces.
- **Cờ Tướng (Chinese Chess)** - Traditional Chinese chess with all the proper rules and piece movements.
- **Cờ Vây (Go)** - Ancient strategy board game where players aim to surround more territory.

### Voice Management
Advanced voice channel management system:

- **Auto Channel Creation** - Joining the "tạo phòng" voice channel automatically creates a custom voice channel.
- **Channel Ownership** - Full control over your created voice channels.
- **Permissions Management** - Control who can join, speak, and manage your voice channels.
- **Voice Activity Logging** - Track user activity in voice channels.

### Language Learning
Language learning tools to help users practice new languages:

- **Daily Vocabulary** - Receive daily vocabulary words in your chosen language and level.
- **Multiple Languages** - Currently supports Chinese and English.
- **Difficulty Levels** - Various proficiency levels (beginner, intermediate, advanced, HSK levels).
- **Custom Examples** - Example sentences and pronunciations for better comprehension.

### AI Integration
Interact with AI models through the bot:

- **Gemini AI Chat** - Chat with Google's Gemini AI directly in Discord.
- **Context-Aware Conversations** - The bot remembers conversation context for more natural interactions.

### Fun Commands
Entertaining commands for server engagement:

- **Gay Meter** - A humorous command to measure someone's "gayness" on a scale.

### Tactical Game
A tactical RPG-style battle system:

- **Weapon Management** - Create, upgrade and manage weapons for battles.
- **Battle System** - Engage in tactical turn-based battles.
- **Inventory System** - Manage items and equipment.
- **Unit Management** - Create and upgrade battle units.

## Technologies Used

- **Python 3.10+** - Core programming language.
- **discord.py** - Python library for Discord API integration.
- **Google Gemini API** - For AI chat capabilities.
- **asyncio** - For asynchronous operations and event loops.
- **JSON** - For data storage and configuration.
- **Logging** - Comprehensive logging system for monitoring bot activities.

## Installation and Setup

### Prerequisites
- Python 3.10 or higher
- Discord Bot Token
- Google Gemini API Key (for AI chat functionality)

### Step 1: Clone the Repository
```bash
git clone https://github.com/yourusername/botdiscord.git
cd botdiscord
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure the Bot
Create a `config.json` file based on the provided template:
```bash
cp config.template.json config.json
```

Then edit the `config.json` file with your own API keys and tokens:
```json
{
  "prefix": "!",
  "token": "YOUR_DISCORD_BOT_TOKEN",
  "clientId": "YOUR_DISCORD_CLIENT_ID",
  "spotifyClientId": "YOUR_SPOTIFY_CLIENT_ID",
  "spotifyClientSecret": "YOUR_SPOTIFY_CLIENT_SECRET",
  "geminiApiKey": "YOUR_GEMINI_API_KEY"
}
```

> **Note**: The `config.json` file contains sensitive information and is already in the `.gitignore` file. Make sure not to commit this file to any public repository.

### Step 4: Set Up Resources
Ensure the following directories exist:
- `logs/` - For activity logs
- `resources/vocabulary/` - For language learning vocabulary
- `resources/language_learners.json` - For language learning user data

### Step 5: Run the Bot
```bash
python main.py
```

## Bot Commands

### Game Commands
- `/cangua_play @player1 @player2 [@player3] [@player4]` - Start a Ludo game
- `/cangua_roll` - Roll the dice in Ludo
- `/cangua_move [piece]` - Move a piece in Ludo
- `/cangua_resign` - Resign from the current Ludo game
- `/cangua_status` - Show the status of the current Ludo game

- `/cotuong_play @player1 @player2` - Start a Chinese Chess game
- `/cotuong_move [piece] [from_x] [from_y] [to_x] [to_y]` - Move a piece in Chinese Chess
- `/cotuong_resign` - Resign from the current Chinese Chess game

- `/covay_play @player1 @player2 [size]` - Start a Go game (size can be 9, 13, or 19)
- `/covay_move [x] [y]` - Place a stone in Go
- `/covay_pass` - Pass your turn in Go
- `/covay_resign` - Resign from the current Go game

### Tactical Game Commands
- `/tactic_weapon create [name] [type] [rarity]` - Create a new weapon
- `/tactic_weapon list` - List all your weapons
- `/tactic_weapon info [weapon_id]` - Show detailed information about a weapon
- `/tactic_weapon upgrade [weapon_id]` - Upgrade a weapon
- `/tactic_weapon rename [weapon_id] [new_name]` - Rename a weapon
- `/tactic_weapon delete [weapon_id]` - Delete a weapon

- `/tactic_battle start @opponent` - Start a battle with another player
- `/tactic_battle attack [skill_id]` - Use an attack skill in battle
- `/tactic_battle defend [skill_id]` - Use a defensive skill in battle
- `/tactic_battle special [skill_id]` - Use a special skill in battle
- `/tactic_battle surrender` - Surrender the current battle
- `/tactic_battle status` - Show the current battle status

- `/tactic_inventory` - Show your inventory
- `/tactic_inventory use [item_id]` - Use an item from your inventory
- `/tactic_equip [weapon_id]` - Equip a weapon

### Voice Commands
- `/voice_kick @user` - Kick a user from your voice channel
- `/voice_limit [number]` - Set a user limit for your voice channel
- `/voice_hide` - Hide your voice channel from the server
- `/voice_show` - Make your voice channel visible to everyone
- `/voice_public` - Make your voice channel open to everyone
- `/voice_private` - Make your voice channel private
- `/voice_rename [name]` - Rename your voice channel
- `/voice_addowner @user` - Add a co-owner to your voice channel
- `/voice_removeowner @user` - Remove a co-owner from your voice channel
- `/voice_lock` - Lock your voice channel to prevent new users from joining
- `/voice_unlock` - Unlock your voice channel to allow users to join
- `/voice_transfer @user` - Transfer ownership of your voice channel
- `/voice_muteall` - Mute all users in your voice channel except you and co-owners
- `/voice_unmuteall` - Unmute all users in your voice channel
- `/voice_claim` - Claim ownership of a voice channel if the owner has left
- `/voice_info` - Show information about the current voice channel

### Language Learning Commands
- `/lang_register [language] [level]` - Register for daily language learning vocabulary
- `/lang_unregister [language] [level]` - Unregister from daily language learning vocabulary
- `/lang_list` - List your language learning registrations
- `/lang_send_now` - Send vocabulary immediately (admin only)

### AI Chat Commands
- `/chatai_clear` - Clear your chat history with the AI
- `/chatai_help` - Get help with using the Gemini AI chat feature

You can also interact with the AI by:
- Mentioning the bot: `@BotName your question here`
- Replying to the bot's messages

### Fun Commands
- `/fun_isgay @user` - Check a user's "gayness" level

## Project Structure

```
botdiscord/
├── config.json             # Configuration file
├── main.py                 # Main bot entry point
├── functions/              # Bot commands and features
│   ├── ca_ngua.py          # Ludo game implementation
│   ├── cotuong.py          # Chinese Chess implementation
│   ├── covay.py            # Go game implementation
│   ├── fun.py              # Fun commands
│   ├── gemini_chat.py      # AI chat integration
│   ├── language_learning.py  # Language learning features
│   ├── voice_activity_logger.py  # Voice activity logging
│   └── voice_manager.py    # Voice channel management
├── game_data/              # Game data storage
│   ├── inventories.json
│   ├── units.json
│   └── weapons.json
├── game_tactic/            # Tactical game implementations
│   ├── tactic_battle.py
│   └── tactic_weapons.py
├── logs/                   # Log files
│   └── voice_activity_*.log
└── resources/              # Resources for features
    ├── language_learners.json
    └── vocabulary/         # Vocabulary data for language learning
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- Discord.py for the amazing Discord API wrapper
- Google for the Gemini AI API
- Contributors and testers who helped refine the features 