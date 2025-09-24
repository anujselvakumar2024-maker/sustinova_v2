# AgroSmart AI Backend API Server - FIXED for Connection Issues
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import datetime
import time
import threading
import requests
from typing import Dict, Any, Optional

app = Flask(__name__)
CORS(app, origins=['*'])  # Allow all origins for testing

# Global state
sensor_data: Dict[str, Any] = {
    "temperature": 25.5,
    "soil_moisture": 37.2,
    "humidity": 68,
    "water_level": 750,
    "rain_detected": False,
    "pump_running": False,
    "esp32_ip": None,
    "last_updated": datetime.datetime.now().isoformat(),
    "connection_status": "disconnected"
}

irrigation_state: Dict[str, Any] = {
    "active_irrigation": None,
    "paused_due_to_rain": None,
    "rain_start_time": None,
    "rain_end_time": None,
    "irrigation_messages": []
}

irrigation_log = []
chat_history = []
esp32_ip: Optional[str] = None

class IrrigationAI:
    def __init__(self):
        self.thresholds = {
            "soil_moisture_min": 30,
            "soil_moisture_critical": 20,
            "water_level_min": 200,
            "temperature_max": 35,
            "humidity_min": 40
        }

    def should_resume_after_rain(self, soil_moisture: float) -> tuple[bool, str]:
        if soil_moisture >= self.thresholds["soil_moisture_min"]:
            return False, f"Irrigation cancelled - sufficient moisture after rain ({soil_moisture}%)"
        else:
            return True, f"Even after rain, soil needs water. Current moisture: {soil_moisture}%"

    def analyze_irrigation_need(self, sensors: Dict[str, Any]) -> Dict[str, Any]:
        decision = {
            "should_irrigate": False,
            "duration": 0,
            "reason": "",
            "urgency": "low",
            "timestamp": datetime.datetime.now().isoformat()
        }

        if sensors.get("rain_detected", False):
            decision["reason"] = "Rain detected - irrigation not needed"
            return decision

        water_level = sensors.get("water_level", 0)
        if water_level < self.thresholds["water_level_min"]:
            decision["reason"] = f"Water level too low ({water_level}L)"
            return decision

        soil_moisture = sensors.get("soil_moisture", 100)
        temperature = sensors.get("temperature", 20)
        humidity = sensors.get("humidity", 60)

        if soil_moisture <= self.thresholds["soil_moisture_critical"]:
            decision["should_irrigate"] = True
            decision["duration"] = 15
            decision["reason"] = f"Critical irrigation needed - soil moisture: {soil_moisture}%"
            decision["urgency"] = "critical"
        elif soil_moisture <= self.thresholds["soil_moisture_min"]:
            if temperature > self.thresholds["temperature_max"] and humidity < self.thresholds["humidity_min"]:
                duration = 15
                reason = f"Extended irrigation - hot & dry (T:{temperature}°C, H:{humidity}%)"
            else:
                duration = 10
                reason = f"Moderate irrigation needed - soil moisture: {soil_moisture}%"

            decision["should_irrigate"] = True
            decision["duration"] = duration
            decision["reason"] = reason
            decision["urgency"] = "moderate"
        else:
            decision["reason"] = f"Soil conditions optimal - moisture: {soil_moisture}%"

        return decision

class FarmingChatbot:
    def __init__(self):
        self.farming_keywords = [
            'farm', 'crop', 'plant', 'grow', 'soil', 'water', 'irrigation', 'pest', 'fertilizer',
            'seed', 'harvest', 'agriculture', 'organic', 'compost', 'weather', 'season',
            'disease', 'insect', 'vegetable', 'fruit', 'grain', 'rice', 'wheat', 'corn', 'rain'
        ]

    def is_farming_related(self, message):
        return any(keyword.lower() in message.lower() for keyword in self.farming_keywords)

    def get_response(self, message, language='en'):
        if not self.is_farming_related(message):
            responses = {
                'en': "I'm your farming assistant! Ask me about irrigation, crops, soil management, pest control, or weather.",
                'hi': "मैं आपका कृषि सहायक हूँ! मुझसे सिंचाई, फसल, मिट्टी प्रबंधन, कीट नियंत्रण या मौसम के बारे में पूछें।",
                'ne': "म तपाईंको कृषि सहायक हुँ! मलाई सिंचाई, बाली, माटो व्यवस्थापन, कीट नियन्त्रण वा मौसमको बारेमा सोध्नुहोस्।"
            }
            return responses.get(language, responses['en'])

        msg = message.lower()
        if 'irrigation' in msg or 'water' in msg:
            responses = {
                'en': "For efficient irrigation: Water early morning or evening, use drip irrigation, and monitor soil moisture. Your AI system automatically manages optimal watering!",
                'hi': "कुशल सिंचाई के लिए: सुबह या शाम पानी दें, ड्रिप सिंचाई का उपयोग करें, और मिट्टी की नमी की निगरानी करें। आपका AI सिस्टम स्वचालित रूप से पानी देता है!",
                'ne': "प्रभावकारी सिंचाईका लागि: बिहान वा साँझ पानी दिनुहोस्, ड्रिप सिंचाई प्रयोग गर्नुहोस्, र माटोको चिस्यान निरीक्षण गर्नुहोस्। तपाईंको AI प्रणालीले स्वचालित रूपमा पानी दिन्छ!"
            }
        elif 'soil' in msg:
            responses = {
                'en': "Healthy soil needs good drainage, proper pH (6.0-7.0), organic matter, and regular testing. Your sensors show current soil conditions for optimal irrigation.",
                'hi': "स्वस्थ मिट्टी के लिए अच्छी जल निकासी, उचित pH (6.0-7.0), जैविक पदार्थ और नियमित परीक्षण की आवश्यकता होती है। आपके सेंसर मिट्टी की स्थिति दिखाते हैं।",
                'ne': "स्वस्थ माटोका लागि राम्रो पानी निकास, उचित pH (6.0-7.0), जैविक पदार्थ र नियमित परीक्षण चाहिन्छ। तपाईंका सेन्सरहरूले माटोको अवस्था देखाउँछन्।"
            }
        elif 'rain' in msg:
            responses = {
                'en': "Rain management is crucial! Your system automatically pauses irrigation during rain and resumes based on soil moisture levels after rain stops.",
                'hi': "बारिश प्रबंधन महत्वपूर्ण है! आपका सिस्टम बारिश के दौरान सिंचाई रोक देता है और बारिश रुकने के बाद मिट्टी की नमी के आधार पर फिर से शुरू करता है।",
                'ne': "वर्षा व्यवस्थापन महत्वपूर्ण छ! तपाईंको प्रणालीले वर्षाको समयमा सिंचाई रोक्छ र वर्षा रोकिएपछि माटोको चिस्यानको आधारमा पुनः सुरु गर्छ।"
            }
        else:
            responses = {
                'en': "Great farming question! Your AgroSmart system monitors all environmental factors for optimal crop management and irrigation decisions.",
                'hi': "बेहतरीन कृषि प्रश्न! आपका AgroSmart सिस्टम फसल प्रबंधन और सिंचाई निर्णयों के लिए सभी पर्यावरणीय कारकों की निगरानी करता है।",
                'ne': "उत्कृष्ट कृषि प्रश्न! तपाईंको AgroSmart प्रणालीले बाली व्यवस्थापन र सिंचाई निर्णयहरूका लागि सबै वातावरणीय कारकहरूको निगरानी गर्छ।"
            }

        return responses.get(language, responses['en'])

ai_engine = IrrigationAI()
chatbot = FarmingChatbot()

@app.route('/')
def home():
    return jsonify({
        "message": "AgroSmart AI API Server - Fixed Connection Issues",
        "version": "8.0.0",
        "status": "running",
        "esp32_connected": esp32_ip is not None,
        "features": ["Rain Management", "AI Irrigation", "Farming Chatbot", "Multi-language"],
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route('/api/sensors', methods=['GET'])
def get_sensors():
    response_data = sensor_data.copy()
    response_data["irrigation_state"] = irrigation_state
    response_data["esp32_connected"] = esp32_ip is not None
    return jsonify(response_data)

@app.route('/api/sensors', methods=['POST'])
def update_sensors():
    global sensor_data, esp32_ip
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data received"}), 400

        sensor_data.update(data)
        sensor_data["last_updated"] = datetime.datetime.now().isoformat()
        sensor_data["connection_status"] = "connected"

        if "esp32_ip" in data:
            esp32_ip = data["esp32_ip"]

        print(f"✅ Sensor data updated: {data}")
        return jsonify({"success": True, "data": sensor_data})
    except Exception as e:
        print(f"❌ Error updating sensors: {e}")
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/ai/analyze', methods=['GET'])
def ai_analyze():
    """AI irrigation analysis endpoint"""
    try:
        decision = ai_engine.analyze_irrigation_need(sensor_data)

        # Auto-start irrigation if AI recommends and no rain
        if (decision["should_irrigate"] and 
            not sensor_data.get("rain_detected", False) and 
            not irrigation_state["active_irrigation"]):

            success = start_esp32_irrigation(decision["duration"], "ai_automatic")
            if success:
                irrigation_state["active_irrigation"] = {
                    "type": "ai_automatic",
                    "duration": decision["duration"],
                    "start_time": datetime.datetime.now().isoformat(),
                    "reason": decision["reason"]
                }

                irrigation_log.append({
                    "timestamp": datetime.datetime.now().isoformat(),
                    "action": "ai_auto_start",
                    "duration": decision["duration"],
                    "reason": decision["reason"],
                    "soil_moisture": sensor_data.get("soil_moisture", 0)
                })

        return jsonify(decision)
    except Exception as e:
        print(f"❌ AI analysis error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/rain/alert', methods=['POST'])
def rain_alert():
    global irrigation_state
    try:
        data = request.get_json()
        current_time = datetime.datetime.now().isoformat()

        sensor_data["rain_detected"] = True
        irrigation_state["rain_start_time"] = current_time

        if irrigation_state["active_irrigation"]:
            irrigation_state["paused_due_to_rain"] = irrigation_state["active_irrigation"].copy()
            irrigation_state["active_irrigation"] = None

            irrigation_state["irrigation_messages"] = [{
                "type": "paused",
                "message": "Due to rain, irrigation has been paused",
                "timestamp": current_time
            }]

            irrigation_log.append({
                "timestamp": current_time,
                "action": "paused_due_to_rain",
                "reason": "Rain detected - irrigation paused automatically"
            })

            print(f"🌧️ Rain alert: Irrigation paused at {current_time}")

        return jsonify({"success": True, "message": "Rain alert processed"})
    except Exception as e:
        print(f"❌ Rain alert error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/rain/stopped', methods=['POST'])
def rain_stopped():
    global irrigation_state
    try:
        data = request.get_json()
        current_time = datetime.datetime.now().isoformat()

        sensor_data["rain_detected"] = False
        irrigation_state["rain_end_time"] = current_time

        if irrigation_state["paused_due_to_rain"]:
            soil_moisture = data.get("soil_moisture", sensor_data.get("soil_moisture", 50))
            should_resume, reason = ai_engine.should_resume_after_rain(soil_moisture)

            if should_resume:
                duration = max(5, irrigation_state["paused_due_to_rain"].get("duration", 10) // 2)

                if start_esp32_irrigation(duration, "resumed_after_rain"):
                    irrigation_state["active_irrigation"] = {
                        "type": "resumed_after_rain",
                        "duration": duration,
                        "start_time": current_time
                    }
                    irrigation_state["paused_due_to_rain"] = None

                    irrigation_state["irrigation_messages"] = [{
                        "type": "resumed",
                        "message": f"Timer resumed after rain - {duration} minutes remaining",
                        "timestamp": current_time
                    }]

                    print(f"☀️ Rain stopped: Irrigation resumed for {duration} minutes")
            else:
                irrigation_state["paused_due_to_rain"] = None
                irrigation_state["irrigation_messages"] = [{
                    "type": "cancelled",
                    "message": "Irrigation cancelled - sufficient moisture after rain",
                    "timestamp": current_time
                }]

                print(f"☀️ Rain stopped: Irrigation cancelled - {reason}")

        return jsonify({"success": True, "message": "Rain stopped processed"})
    except Exception as e:
        print(f"❌ Rain stopped error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/irrigation/control', methods=['POST'])
def irrigation_control():
    global irrigation_state
    try:
        data = request.get_json()
        action = data.get('action')
        duration = data.get('duration', 10)
        current_time = datetime.datetime.now().isoformat()

        print(f"🎛️ Irrigation control: {action}, duration: {duration}")

        if action == 'start':
            if sensor_data.get("rain_detected", False):
                return jsonify({"success": False, "error": "Cannot start irrigation during rain"}), 400

            if start_esp32_irrigation(duration, "manual"):
                irrigation_state["active_irrigation"] = {
                    "type": "manual",
                    "duration": duration,
                    "start_time": current_time
                }

                irrigation_log.append({
                    "timestamp": current_time,
                    "action": "manual_start",
                    "duration": duration
                })

                print(f"✅ Manual irrigation started for {duration} minutes")
                return jsonify({"success": True, "message": f"Irrigation started for {duration} minutes"})
            else:
                return jsonify({"success": False, "error": "Failed to start ESP32 pump"}), 500

        elif action == 'stop':
            if stop_esp32_irrigation():
                irrigation_state["active_irrigation"] = None
                irrigation_state["paused_due_to_rain"] = None

                irrigation_log.append({
                    "timestamp": current_time,
                    "action": "manual_stop"
                })

                print(f"🛑 Manual irrigation stopped")
                return jsonify({"success": True, "message": "Irrigation stopped"})
            else:
                return jsonify({"success": False, "error": "Failed to stop ESP32 pump"}), 500

        return jsonify({"success": False, "error": "Invalid action"}), 400
    except Exception as e:
        print(f"❌ Irrigation control error: {e}")
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/motor-log', methods=['GET'])
def motor_log():
    recent_logs = irrigation_log[-50:] if len(irrigation_log) > 50 else irrigation_log
    return jsonify({
        "logs": list(reversed(recent_logs)),
        "total": len(recent_logs),
        "esp32_connected": esp32_ip is not None
    })

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    global chat_history
    try:
        data = request.get_json()
        message = data.get('message', '')
        language = data.get('language', 'en')

        if not message:
            return jsonify({"success": False, "error": "No message provided"}), 400

        response = chatbot.get_response(message, language)

        chat_entry = {
            "user_message": message,
            "bot_response": response,
            "language": language,
            "timestamp": datetime.datetime.now().isoformat(),
            "is_farming_related": chatbot.is_farming_related(message)
        }

        chat_history.append(chat_entry)
        chat_history = chat_history[-100:]

        print(f"💬 Chat: {message[:50]}... -> {response[:50]}...")

        return jsonify({
            "success": True,
            "response": response,
            "is_farming_related": chatbot.is_farming_related(message),
            "timestamp": chat_entry["timestamp"]
        })
    except Exception as e:
        print(f"❌ Chat error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

def start_esp32_irrigation(duration_minutes: int, irrigation_type: str = "manual") -> bool:
    if not esp32_ip:
        print(f"⚠️ Cannot start irrigation - ESP32 IP not available")
        return False
    try:
        url = f"http://{esp32_ip}/pump/start"
        response = requests.post(url, json={"duration": duration_minutes}, timeout=10)
        if response.status_code == 200:
            sensor_data["pump_running"] = True
            print(f"✅ ESP32 pump started for {duration_minutes} minutes ({irrigation_type})")
            return True
        else:
            print(f"❌ ESP32 pump start failed - HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ ESP32 communication error: {e}")
        return False

def stop_esp32_irrigation() -> bool:
    if not esp32_ip:
        print(f"⚠️ Cannot stop irrigation - ESP32 IP not available")
        return False
    try:
        url = f"http://{esp32_ip}/pump/stop"
        response = requests.post(url, timeout=10)
        if response.status_code == 200:
            sensor_data["pump_running"] = False
            print(f"✅ ESP32 pump stopped")
            return True
        else:
            print(f"❌ ESP32 pump stop failed - HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ ESP32 communication error: {e}")
        return False

if __name__ == '__main__':
    print("🚀 AgroSmart AI API Server - Fixed Connection Issues")
    print("📡 Server will start on: http://0.0.0.0:5000")
    print("🌧️ Rain Management: Active")
    print("🤖 AI Engine: Ready")
    print("💬 Farming Chatbot: Ready")
    print("📊 Motor Logging: Active")
    print("🔧 CORS: Enabled for all origins")
    print("")
    print("Local access: http://localhost:5000")
    print("Network access: http://<YOUR_IP>:5000")
    print("")

    # Critical fix: Ensure proper binding
    app.run(host='0.0.0.0', port=5000, debug=False)
