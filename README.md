# 🤖 Discord Multi-Feature Bot

Một Discord bot đa chức năng với hệ thống học ngôn ngữ tiên tiến, trò chơi, AI chat, và quản lý voice channels.

## ✨ Tính Năng Chính

### 📚 Hệ Thống Học Ngôn Ngữ (Language Learning V2)
- **🔄 Sequential Learning**: Học từ vựng theo trình tự, không random
- **🏗️ Auto Channel Creation**: Tự động tạo categories, channels và roles
- **📊 Progress Tracking**: Theo dõi tiến độ học tập cá nhân
- **🎯 Quiz System**: Hệ thống quiz tương tác với điểm số
- **🏆 Leaderboard & Gamification**: Bảng xếp hạng và streak system
- **🌐 Đa ngôn ngữ**: Chinese (HSK 1-4), English (Beginner-Advanced), Japanese (JLPT N5-N1)

### 🎮 Trò Chơi
- **♟️ Cờ Tướng (Chinese Chess)**: Chơi cờ tướng với AI hoặc người khác
- **⚫ Cờ Vây (Go)**: Trò chơi cờ vây với nhiều kích thước bàn cờ
- **🎲 Cờ Cá Ngựa (Ludo)**: Trò chơi ludo 2-4 người chơi

### 🤖 AI Chat Integration
- **💬 Gemini AI**: Chat với Google Gemini AI model mới nhất
- **🧠 Context Memory**: Nhớ ngữ cảnh cuộc trò chuyện
- **⚡ Fast Response**: Phản hồi nhanh với typing indicators

### 🔊 Voice Channel Management
- **📞 Auto Voice Rooms**: Tự động tạo phòng voice riêng tư
- **🔧 Voice Controls**: Quản lý quyền hạn và cài đặt
- **📝 Activity Logging**: Ghi log hoạt động voice

### 🎪 Fun Commands
- **🌈 Gay Meter**: Command vui nhộn (có thể tắt)
- **🎲 Random Games**: Các mini-game giải trí

## 🚀 Cài Đặt

### Yêu Cầu Hệ Thống
- Python 3.8+
- discord.py 2.0+
- SQLite3
- Google Generative AI SDK

### Cài Đặt Dependencies

```bash
pip install discord.py
pip install google-generativeai
pip install sqlite3  # Thường có sẵn với Python
```

### Cấu Hình

1. **Copy config template:**
```bash
cp config.template.json config.json
```

2. **Điền thông tin vào config.json:**
```json
{
  "token": "YOUR_BOT_TOKEN_HERE",
  "prefix": "!",
  "gemini_api_key": "YOUR_GEMINI_API_KEY_HERE",
  
  "language_learning": {
    "enabled": true,
    "daily_send_time": 8,
    "words_per_day": 20,
    "auto_create_channels": true,
    "sequential_learning": true,
    "progress_tracking": true,
    "gamification": true
  },
  
  "voice_manager": {
    "enabled": true,
    "create_channel_name": "tạo phòng",
    "auto_cleanup": true,
    "cleanup_delay_seconds": 5
  },
  
  "games": {
    "cotuong_enabled": true,
    "covay_enabled": true, 
    "cangua_enabled": true
  },
  
  "fun_commands": {
    "enabled": true,
    "gay_meter_enabled": true
  },
  
  "features": {
    "gemini_chat": true,
    "auto_reactions": false,
    "welcome_messages": false
  }
}
```

3. **Chạy bot:**
```bash
python main.py
```

## 📋 Commands - Language Learning

### 🎓 Đăng Ký & Quản Lý
- `/lang_register <language> <level>` - Đăng ký học ngôn ngữ
- `/lang_unregister <language> <level>` - Hủy đăng ký
- `/lang_list` - Xem danh sách đăng ký của bạn
- `/lang_progress` - Kiểm tra tiến độ học tập

### 🎯 Học Tập & Kiểm Tra
- `/lang_quiz <language> <level> [count]` - Làm quiz từ vựng
- `/lang_leaderboard [language] [level]` - Xem bảng xếp hạng

### 👨‍💼 Admin Commands
- `/lang_send_now` - Gửi từ vựng ngay lập tức (Admin only)

### 🌐 Ngôn Ngữ Được Hỗ Trợ

**Chinese (中文):**
- `hsk1` - HSK Level 1 (150 từ cơ bản)
- `hsk2` - HSK Level 2 (300 từ)
- `hsk3` - HSK Level 3 (600 từ)
- `hsk4` - HSK Level 4 (1200 từ)

**English:**
- `beginner` - Tiếng Anh cơ bản
- `intermediate` - Tiếng Anh trung cấp
- `advanced` - Tiếng Anh nâng cao

**Japanese (日本語):**
- `jlpt_n5` - JLPT N5 (800 từ cơ bản)
- `jlpt_n4` - JLPT N4 (1500 từ)
- `jlpt_n3` - JLPT N3 (3700 từ)
- `jlpt_n2` - JLPT N2 (6000 từ)
- `jlpt_n1` - JLPT N1 (10000 từ)

## 🎮 Game Commands

### ♟️ Cờ Tướng (Chinese Chess)
- `/cotuong_play @player1 @player2` - Bắt đầu game
- `/cotuong_move <piece> <from_x> <from_y> <to_x> <to_y>` - Di chuyển quân

### ⚫ Cờ Vây (Go)  
- `/covay_play @player1 @player2 <size>` - Bắt đầu game (size: 9, 13, 19)
- `/covay_move <x> <y>` - Đặt quân
- `/pass` - Pass lượt
- `/resign_covay` - Đầu hàng

### 🎲 Cờ Cá Ngựa (Ludo)
- `/cangua_play @player1 @player2 [@player3] [@player4]` - Bắt đầu game (2-4 người)

## 💬 AI Chat Commands

- `@BotMention <message>` - Chat với AI bằng cách mention
- Reply vào tin nhắn của bot - Tiếp tục cuộc trò chuyện
- `/chatai_clear` - Xóa lịch sử chat
- `/chatai_help` - Hướng dẫn sử dụng AI chat

## 🔊 Voice Features

- Tham gia channel **"tạo phòng"** để tạo voice room riêng
- Voice channels tự động dọn dẹp khi trống
- Chủ phòng có thể quản lý quyền hạn

## 🎪 Fun Commands

- `/fun_isgay @user` - Kiểm tra "gay meter" (for fun)

## 🛠️ Tính Năng Tiên Tiến

### 📊 Progress Tracking System
- **Sequential Learning**: Học từ vựng theo thứ tự, không ngẫu nhiên
- **Personal Progress**: Mỗi người có tiến độ riêng
- **Streak System**: Hệ thống streak days để tạo động lực
- **Points & Rewards**: Hệ thống điểm và phần thưởng

### 🏗️ Auto Channel Management
- Tự động tạo categories cho từng ngôn ngữ
- Tạo channels riêng cho từng level
- Tự động tạo và phân quyền roles
- Chỉ người có role mới thấy được channel tương ứng

### 🎯 Interactive Quiz System
- Quiz đa lựa chọn tương tác
- Điểm số dựa trên performance
- Bonus points cho kết quả cao
- Timeout handling và quit option

### 🏆 Gamification Features
- Leaderboard server-wide và theo ngôn ngữ
- Streak system với rewards
- Points system khuyến khích học tập
- Achievement system (planned)

## 📁 Cấu Trúc Dự Án

```
discordbot/
├── main.py                 # Entry point chính
├── config.json            # Cấu hình bot
├── config.template.json   # Template cấu hình
├── functions/             # Các chức năng chính
│   ├── language_learning_v2.py  # Hệ thống học ngôn ngữ v2
│   ├── gemini_chat.py     # AI chat integration
│   ├── voice_manager.py   # Quản lý voice channels
│   ├── cotuong.py         # Trò chơi cờ tướng
│   ├── covay.py           # Trò chơi cờ vây
│   ├── ca_ngua.py         # Trò chơi cờ cá ngựa
│   └── fun.py             # Commands giải trí
├── game_tactic/           # Game mechanics
├── resources/             # Dữ liệu và resources
│   ├── vocabulary/        # Từ vựng các ngôn ngữ
│   ├── progress.db        # Database tiến độ học tập
│   └── language_learners.json  # Data người học
└── logs/                  # Log files
```

## 🔧 Cấu Hình Chi Tiết

### Language Learning Settings

```json
"language_learning": {
  "enabled": true,                    // Bật/tắt chức năng
  "daily_send_time": 8,              // Giờ gửi từ vựng (24h format)
  "words_per_day": 20,               // Số từ vựng mỗi ngày
  "auto_create_channels": true,       // Tự động tạo channels
  "sequential_learning": true,        // Học tuần tự (không random)
  "progress_tracking": true,          // Theo dõi tiến độ
  "gamification": true               // Hệ thống điểm và rewards
}
```

### Voice Manager Settings

```json
"voice_manager": {
  "enabled": true,                    // Bật/tắt voice manager
  "create_channel_name": "tạo phòng", // Tên channel để tạo phòng
  "auto_cleanup": true,               // Tự động dọn dẹp
  "cleanup_delay_seconds": 5          // Thời gian chờ trước khi xóa
}
```

### Games Settings

```json
"games": {
  "cotuong_enabled": true,           // Bật/tắt cờ tướng
  "covay_enabled": true,             // Bật/tắt cờ vây  
  "cangua_enabled": true             // Bật/tắt cờ cá ngựa
}
```

## 📊 Database Schema

Bot sử dụng SQLite để lưu trữ dữ liệu:

### user_progress
- Tiến độ học tập cá nhân
- Current word index, words learned
- Streak days, total points

### word_reviews  
- Lịch sử ôn tập từ vựng
- Spaced repetition data
- Retention strength

### daily_stats
- Thống kê hằng ngày
- Words studied, quizzes completed
- Points earned per day

## 🔍 Troubleshooting

### Bot không phản hồi
1. Kiểm tra token trong config.json
2. Đảm bảo bot có quyền trong server
3. Kiểm tra logs trong folder logs/

### AI Chat không hoạt động
1. Kiểm tra Gemini API key
2. Đảm bảo `gemini_chat: true` trong config
3. Kiểm tra quota API key

### Language Learning không hoạt động
1. Kiểm tra `language_learning.enabled: true`
2. Đảm bảo bot có quyền tạo channels/roles
3. Kiểm tra file vocabulary trong resources/

### Voice Manager không hoạt động
1. Kiểm tra tên channel "tạo phòng" (có thể tùy chỉnh)
2. Đảm bảo bot có quyền quản lý voice channels
3. Kiểm tra `voice_manager.enabled: true`

## 🤝 Đóng Góp

1. Fork dự án
2. Tạo feature branch: `git checkout -b feature/AmazingFeature`
3. Commit changes: `git commit -m 'Add some AmazingFeature'`
4. Push to branch: `git push origin feature/AmazingFeature`
5. Tạo Pull Request

## 📝 License

Dự án này được phân phối dưới MIT License. Xem `LICENSE` file để biết thêm chi tiết.

## 📞 Hỗ Trợ

Nếu bạn gặp vấn đề hoặc có câu hỏi:

1. Kiểm tra phần Troubleshooting ở trên
2. Xem logs trong folder logs/
3. Tạo issue trên GitHub repository
4. Join Discord server hỗ trợ (nếu có)

---

## 🎯 Roadmap

### Đã Hoàn Thành ✅
- ✅ Sequential learning system
- ✅ Auto channel/role creation  
- ✅ Progress tracking với SQLite
- ✅ Interactive quiz system
- ✅ Leaderboard và gamification
- ✅ Japanese language support
- ✅ Advanced configuration system
- ✅ Better error handling

### Đang Phát Triển 🔄
- 🔄 Spaced repetition algorithm
- 🔄 Achievement system
- 🔄 Statistics dashboard
- 🔄 Mobile-friendly interfaces

### Kế Hoạch Tương Lai 📋
- 📋 More languages (Korean, French, German)
- 📋 Voice pronunciation features
- 📋 AI-powered conversation practice
- 📋 Study groups và multiplayer learning
- 📋 Integration với external dictionaries
- 📋 Export progress reports

---

**Happy Learning! 🎓📚✨** 