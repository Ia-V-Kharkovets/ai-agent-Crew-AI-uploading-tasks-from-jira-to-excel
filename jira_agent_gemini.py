# jira_agent_gemini.py - Агент для Jira с Google Gemini и созданием Excel-отчёта
import os
import json
import base64
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
import pandas as pd

# Загружаем настройки
load_dotenv("crewAI_Settings.env")

# =============================================
# НАСТРОЙКА JIRA
# =============================================

JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

if not all([JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
    print("❌ Ошибка: Не все настройки Jira заполнены!")
    exit(1)

auth_string = f"{JIRA_EMAIL}:{JIRA_API_TOKEN}"
auth_bytes = auth_string.encode('utf-8')
auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')

JIRA_HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Basic {auth_base64}",
    "Content-Type": "application/json"
}

# =============================================
# ПАРАМЕТРЫ ОТЧЁТА (МЕНЯЙТЕ ЗДЕСЬ!)
# =============================================

PROJECT_KEY = "KAN"                                    # ← Ключ проекта
PERIOD_DAYS = 30                                       # ← Период в днях
OUTPUT_FILE = f"jira_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"

# =============================================
# ФУНКЦИЯ ДЛЯ ПРЯМОГО ПОЛУЧЕНИЯ ДАННЫХ ИЗ JIRA
# =============================================

def get_jira_issues_direct(jql_query: str) -> list:
    """Получает задачи из Jira напрямую."""
    try:
        url = f"{JIRA_URL}/rest/api/3/search/jql"
        params = {
            "jql": jql_query,
            "maxResults": 100,
            "fields": "summary,status,assignee,created,updated,priority,description,issuetype"
        }
        response = requests.get(url, headers=JIRA_HEADERS, params=params)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('issues', [])
        else:
            print(f"❌ Ошибка API: {response.status_code}")
            print(f"   {response.text[:200]}")
            return []
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

# =============================================
# ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ЗАДАЧ ЗА ПЕРИОД
# =============================================

def get_all_kan_issues() -> list:
    """
    Получает задачи из проекта KAN за указанный период.
    Период задаётся параметром PERIOD_DAYS.
    """
    try:
        url = f"{JIRA_URL}/rest/api/3/search/jql"
        
        # ✅ Формируем JQL с периодом
        jql_query = f"project = {PROJECT_KEY} AND updated >= -{PERIOD_DAYS}d"
        
        params = {
            "jql": jql_query,
            "maxResults": 100,
            "fields": "summary,status,assignee,created,updated,priority"
        }
        response = requests.get(url, headers=JIRA_HEADERS, params=params)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('issues', [])
        else:
            print(f"❌ Ошибка API: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

# =============================================
# ФУНКЦИЯ ДЛЯ СОЗДАНИЯ EXCEL-ОТЧЁТА (С ВКЛАДКАМИ ПО СТАТУСАМ)
# =============================================

def create_excel_report(issues_data: list, filename: str) -> str:
    """Создаёт Excel-файл с отчётом по задачам, разделённым по статусам."""
    if not issues_data:
        print("⚠️ Нет данных для создания отчёта")
        return None
    
    # Подготавливаем данные
    data = []
    for issue in issues_data:
        key = issue.get('key', '')
        fields = issue.get('fields', {})
        
        assignee = fields.get('assignee', {})
        assignee_name = assignee.get('displayName', 'Не назначен') if assignee else 'Не назначен'
        
        status = fields.get('status', {}).get('name', 'Неизвестно')
        created = fields.get('created', '')
        updated = fields.get('updated', '')
        priority = fields.get('priority', {})
        priority_name = priority.get('name', 'Неизвестно') if priority else 'Неизвестно'
        issue_url = f"{JIRA_URL}/browse/{key}"
        
        data.append({
            'Ключ': key,
            'Название': fields.get('summary', ''),
            'Статус': status,
            'Исполнитель': assignee_name,
            'Приоритет': priority_name,
            'Создана': created,
            'Обновлена': updated,
            'Ссылка': issue_url
        })
    
    df = pd.DataFrame(data)
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # ========================================
        # 1. ВКЛАДКА "Все задачи" (общий список)
        # ========================================
        df.to_excel(writer, sheet_name='Все задачи', index=False)
        
        # ========================================
        # 2. ВКЛАДКИ ПО СТАТУСАМ (автоматически)
        # ========================================
        unique_statuses = df['Статус'].unique()
        
        for status in unique_statuses:
            # Фильтруем задачи по статусу
            status_df = df[df['Статус'] == status]
            
            # Создаём имя листа (обрезаем, если длинное)
            sheet_name = status[:31]  # Excel ограничение - 31 символ
            
            # Сохраняем в отдельную вкладку
            status_df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # ========================================
        # 3. ВКЛАДКА "Сводка по исполнителям"
        # ========================================
        summary = df.groupby('Исполнитель').agg({
            'Ключ': 'count',
            'Название': lambda x: ', '.join(x)
        }).reset_index()
        summary.columns = ['Исполнитель', 'Количество задач', 'Список задач']
        summary.to_excel(writer, sheet_name='Сводка', index=False)
        
        # ========================================
        # 4. ВКЛАДКА "Статистика по статусам"
        # ========================================
        status_summary = df.groupby('Статус').size().reset_index(name='Количество')
        status_summary.to_excel(writer, sheet_name='Статусы', index=False)
        
        # ========================================
        # Автоматическая подгонка ширины колонок
        # ========================================
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
    
    return os.path.abspath(filename)

# =============================================
# ИНСТРУМЕНТЫ ДЛЯ CREWAI
# =============================================

@tool
def search_jira(jql_query: str) -> str:
    """Выполняет поиск задач в Jira по JQL-запросу."""
    try:
        url = f"{JIRA_URL}/rest/api/3/search/jql"
        params = {
            "jql": jql_query,
            "maxResults": 100,
            "fields": "summary,status,assignee,created,updated,priority"
        }
        response = requests.get(url, headers=JIRA_HEADERS, params=params)
        
        if response.status_code == 200:
            data = response.json()
            return json.dumps(data, indent=2, ensure_ascii=False)
        else:
            return f"Ошибка API: {response.status_code} - {response.text[:200]}"
    except Exception as e:
        return f"Ошибка: {str(e)}"

@tool
def get_projects() -> str:
    """Получает список всех проектов в Jira."""
    try:
        url = f"{JIRA_URL}/rest/api/3/project"
        response = requests.get(url, headers=JIRA_HEADERS)
        if response.status_code == 200:
            data = response.json()
            projects = [{"key": p["key"], "name": p["name"]} for p in data]
            return json.dumps(projects, indent=2, ensure_ascii=False)
        else:
            return f"Ошибка API: {response.status_code}"
    except Exception as e:
        return f"Ошибка: {str(e)}"

@tool
def get_statuses() -> str:
    """Получает список всех статусов задач в Jira."""
    try:
        url = f"{JIRA_URL}/rest/api/3/status"
        response = requests.get(url, headers=JIRA_HEADERS)
        if response.status_code == 200:
            data = response.json()
            statuses = [{"id": s["id"], "name": s["name"]} for s in data]
            return json.dumps(statuses, indent=2, ensure_ascii=False)
        else:
            return f"Ошибка API: {response.status_code}"
    except Exception as e:
        return f"Ошибка: {str(e)}"

# =============================================
# НАСТРОЙКА GEMINI
# =============================================

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("❌ Ошибка: GOOGLE_API_KEY не найден!")
    exit(1)

try:
    gemini_llm = LLM(
        model="gemini/gemini-3.1-flash-lite",
        api_key=GOOGLE_API_KEY
    )
    print("✅ Gemini 3.1 Flash Lite настроен успешно!")
except Exception as e:
    print(f"⚠️ Ошибка настройки Gemini: {e}")
    try:
        gemini_llm = LLM(
            model="gemini/gemini-2.5-flash-lite",
            api_key=GOOGLE_API_KEY
        )
        print("✅ Gemini 2.5 Flash Lite настроен!")
    except Exception as e2:
        print(f"❌ Не удалось настроить Gemini: {e2}")
        exit(1)

# =============================================
# СОЗДАЁМ АГЕНТА
# =============================================

analyst_agent = Agent(
    role="Jira Project Analyst",
    goal="Анализировать задачи в Jira и подсчитывать статистику по исполнителям",
    backstory="Ты - опытный аналитик проектов. Твоя задача - собирать данные из Jira и готовить понятные отчёты.",
    tools=[search_jira, get_projects, get_statuses],
    llm=gemini_llm,
    verbose=True,
    allow_delegation=False
)

# =============================================
# ЗАДАЧА ДЛЯ АГЕНТА
# =============================================

task = Task(
    description=f"""
    Проанализируй все задачи в проекте {PROJECT_KEY} за последние {PERIOD_DAYS} дней.
    
    Выполни следующие шаги:
    1. Используй get_projects, чтобы убедиться, что проект {PROJECT_KEY} существует.
    2. Найди ВСЕ задачи в проекте {PROJECT_KEY}.
       Используй JQL: "project = {PROJECT_KEY}"
       
    3. Сгруппируй задачи по исполнителям и подсчитай количество задач для каждого.
    
    4. Составь итоговый отчёт.
    """,
    expected_output=f"Детальный отчёт по всем задачам в проекте {PROJECT_KEY} за последние {PERIOD_DAYS} дней",
    agent=analyst_agent
)

crew = Crew(
    agents=[analyst_agent],
    tasks=[task],
    verbose=True,
)

# =============================================
# ЗАПУСК
# =============================================

def main():
    print("\n" + "=" * 60)
    print("🚀 ЗАПУСК АГЕНТА ДЛЯ JIRA")
    print("=" * 60)
    print(f"📁 Проект: {PROJECT_KEY}")
    print(f"📅 Период: последние {PERIOD_DAYS} дней")
    print("=" * 60)
    
    # Получаем задачи из проекта за период
    print("\n📥 Получение данных из Jira для Excel-отчёта...")
    issues = get_all_kan_issues()
    
    if issues:
        print(f"✅ Найдено задач в проекте {PROJECT_KEY}: {len(issues)}")
        
        # ✅ УБИРАЕМ ФИЛЬТРАЦИЮ ПО СТАТУСАМ!
        # Теперь все задачи попадают в Excel, независимо от статуса
        
        # Создаём Excel-отчёт со ВСЕМИ задачами
        excel_file = create_excel_report(issues, OUTPUT_FILE)
        if excel_file:
            print(f"✅ Excel-отчёт создан: {excel_file}")
            
            # Показываем список найденных задач
            print("\n📋 Найденные задачи:")
            for issue in issues:
                key = issue.get('key', '')
                fields = issue.get('fields', {})
                status = fields.get('status', {}).get('name', 'Неизвестно')
                assignee = fields.get('assignee', {})
                assignee_name = assignee.get('displayName', 'Не назначен') if assignee else 'Не назначен'
                print(f"   - {key}: {status} → {assignee_name}")
    else:
        print(f"⚠️ В проекте {PROJECT_KEY} нет задач за последние {PERIOD_DAYS} дней!")
    
    # Запускаем агента
    print("\n🤖 Запуск агента...")
    try:
        result = crew.kickoff()
        print("\n" + "=" * 60)
        print("📊 ОТЧЁТ:")
        print("=" * 60)
        print(result)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Анализ завершён!")
    print(f"📁 Excel-файл: {os.path.abspath(OUTPUT_FILE)}")
    print("=" * 60)

if __name__ == "__main__":
    main()