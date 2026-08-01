# test_jira.py - Проверка подключения к Jira через scoped-токен
import os
import base64
import requests
from dotenv import load_dotenv

# Загружаем настройки из файла
load_dotenv("crewAI_Settings.env")

print("=" * 70)
print("🔍 ПРОВЕРКА ПОДКЛЮЧЕНИЯ К JIRA (SCOPED-ТОКЕН)")
print("=" * 70)

# Получаем настройки
JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
CLOUD_ID = os.getenv("CLOUD_ID", "c8611945-b92c-42e7-9b35-6eab5509257e")

print(f"🔗 Cloud ID: {CLOUD_ID}")
print(f"📧 Email: {JIRA_EMAIL}")
print(f"🔑 Token: {JIRA_API_TOKEN[:10]}..." if JIRA_API_TOKEN else "Token: Не найден")

if not all([JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
    print("\n❌ Ошибка: Не все настройки заполнены в crewAI_Settings.env")
    exit()

# Создаём заголовки для авторизации
auth_string = f"{JIRA_EMAIL}:{JIRA_API_TOKEN}"
auth_bytes = auth_string.encode('utf-8')
auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')

headers = {
    "Accept": "application/json",
    "Authorization": f"Basic {auth_base64}",
    "Content-Type": "application/json"
}

# Базовый URL для scoped-токена
JIRA_API_URL = f"https://api.atlassian.com/ex/jira/{CLOUD_ID}"

# =============================================
# 1. Проверяем подключение через получение текущего пользователя
# =============================================

print("\n1️⃣ Проверяем авторизацию...")
try:
    url = f"{JIRA_API_URL}/rest/api/3/myself"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        user_data = response.json()
        print(f"✅ Авторизация успешна!")
        print(f"👤 Пользователь: {user_data.get('displayName', 'Неизвестно')}")
        print(f"📧 Email: {user_data.get('emailAddress', 'Неизвестно')}")
    else:
        print(f"❌ Ошибка авторизации: {response.status_code}")
        print(f"Ответ: {response.text[:200]}")
        exit()
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")
    exit()

# =============================================
# 2. Получаем список проектов
# =============================================

print("\n2️⃣ Получаем список проектов...")
try:
    url = f"{JIRA_API_URL}/rest/api/3/project"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        projects = response.json()
        print(f"✅ Получено проектов: {len(projects)}")
        for p in projects[:10]:
            print(f"  - {p.get('key', 'N/A')}: {p.get('name', 'Unknown')}")
    else:
        print(f"⚠️ Ошибка получения проектов: {response.status_code}")
        print(f"   {response.text[:200]}")
except Exception as e:
    print(f"⚠️ Ошибка: {e}")

# =============================================
# 3. Получаем статусы
# =============================================

print("\n3️⃣ Получаем список статусов...")
try:
    url = f"{JIRA_API_URL}/rest/api/3/status"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        statuses = response.json()
        print(f"✅ Получено статусов: {len(statuses)}")
        done_statuses = [s['name'] for s in statuses if any(kw in s['name'].lower() for kw in ['done', 'closed', 'resolved', 'готов', 'закрыт'])]
        if done_statuses:
            print(f"📋 Статусы завершения: {', '.join(done_statuses[:10])}")
    else:
        print(f"⚠️ Ошибка получения статусов: {response.status_code}")
        print(f"   {response.text[:200]}")
except Exception as e:
    print(f"⚠️ Ошибка: {e}")

# =============================================
# 4. Поиск задач (JQL) с полями
# =============================================

print("\n4️⃣ Поиск задач в проекте KAN...")
try:
    # ✅ Добавляем параметр fields
    jql = "project = KAN ORDER BY created DESC"
    fields = "summary,status,assignee,created,updated,priority"
    url = f"{JIRA_API_URL}/rest/api/3/search/jql?jql={requests.utils.quote(jql)}&fields={fields}&maxResults=10"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        issues = data.get('issues', [])
        total = data.get('total', 0)
        print(f"✅ Найдено задач: {total}")
        print(f"📊 Показано (первые 10): {len(issues)}")
        
        if issues:
            print("\n📋 Список задач в проекте KAN:")
            for issue in issues:
                key = issue.get('key', '')
                fields_data = issue.get('fields', {})
                assignee = fields_data.get('assignee')
                assignee_name = assignee.get('displayName', 'Не назначен') if assignee else 'Не назначен'
                status = fields_data.get('status', {}).get('name', 'Неизвестно')
                summary = fields_data.get('summary', '')[:50]
                print(f"  - {key}: {summary}...")
                print(f"    Статус: {status}")
                print(f"    Исполнитель: {assignee_name}")
        else:
            print("   ℹ️ В проекте KAN нет задач")
    else:
        print(f"⚠️ Ошибка поиска: {response.status_code}")
        print(f"   {response.text[:200]}")
except Exception as e:
    print(f"⚠️ Ошибка: {e}")

# =============================================
# 5. Поиск задач по всем проектам
# =============================================

print("\n5️⃣ Поиск задач по всем проектам...")
try:
    jql = "project in (TC, KAN, LEBM, AVIP) ORDER BY created DESC"
    fields = "summary,status,assignee,created,updated,priority,project"
    url = f"{JIRA_API_URL}/rest/api/3/search/jql?jql={requests.utils.quote(jql)}&fields={fields}&maxResults=10"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        issues = data.get('issues', [])
        total = data.get('total', 0)
        print(f"✅ Найдено задач во всех проектах: {total}")
        print(f"📊 Показано (первые 10): {len(issues)}")
        
        if issues:
            print("\n📋 Задачи по проектам:")
            for issue in issues:
                key = issue.get('key', '')
                fields_data = issue.get('fields', {})
                project = fields_data.get('project', {}).get('key', 'Неизвестно')
                status = fields_data.get('status', {}).get('name', 'Неизвестно')
                summary = fields_data.get('summary', '')[:40]
                print(f"  - {key} ({project}): {summary}... → {status}")
        else:
            print("   ℹ️ В проектах нет задач")
    else:
        print(f"⚠️ Ошибка поиска: {response.status_code}")
        print(f"   {response.text[:200]}")
except Exception as e:
    print(f"⚠️ Ошибка: {e}")

print("\n" + "=" * 70)
print("✅ ПРОВЕРКА ЗАВЕРШЕНА!")
print("=" * 70)
