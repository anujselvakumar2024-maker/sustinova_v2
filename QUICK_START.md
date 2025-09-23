# Quick Start Guide

## 1. ESP32 Setup
- Update WiFi credentials in `esp32/esp32_agrosmart_complete.ino`
- Replace `<YOUR_PC_IP>` with your computer's IP address
- Upload code to ESP32

## 2. Backend Setup
```bash
cd backend
pip install -r requirements.txt
python agrosmart_api.py
```

## 3. Frontend Setup
- Open `frontend/index.html` in web browser
- System will connect automatically

## 4. Features
- Toggle Manual ↔ Automatic modes
- AI only runs in Automatic mode
- Bottom buttons: Motor Log, Alerts, AI Chat
- Multi-language support via 🌐 icon
- Rain management with smart pause/resume

All features are now restored and working! 🌾
