# -*- coding: utf-8 -*-
import streamlit as st
import requests
import os
import platform
import json
import datetime
from streamlit_local_storage import LocalStorage # Используем его напрямую
from duckduckgo_search import DDGS
import traceback
import re
import logging
from html import unescape
from typing import List, Dict, Optional, Any, Tuple, Generator

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Ключ API из секретов Streamlit ---
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY")

# --- Константы ---
# API и модели (ВОЗВРАЩЕНЫ К ВАШЕМУ ОРИГИНАЛУ)
OPENROUTER_API_URL: str = "https://openrouter.ai/api/v1/chat/completions"
MODES: Dict[str, str] = {
    "Стандарт (V3)": "deepseek/deepseek-chat-v3-0324:free",
    "DeepThink (R1)": "deepseek/deepseek-r1:free",
}
DEFAULT_MODE: str = "Стандарт (V3)" # Возвращен дефолтный режим

# Локальное хранилище
LOCAL_STORAGE_KEY: str = "multi_chat_storage_v20" # Снова сменил ключ для чистого старта
DEFAULT_CHAT_NAME: str = "Новый чат"

# Веб-поиск
MAX_SEARCH_RESULTS_PER_QUERY: int = 3
MAX_QUERIES_TO_GENERATE: int = 2
MAX_SNIPPET_LENGTH: int = 250
# Используем более простую модель для генерации запросов, чтобы снизить вероятность ошибок
SEARCH_QUERY_GENERATION_MODEL: str = "deepseek/deepseek-chat-v3-0324:free"

# Сеть и тайм-ауты
REQUEST_TIMEOUT: int = 30
STREAM_TIMEOUT: int = 180

# Заголовки для API
# **ВАЖНО:** Замените на URL вашего приложения, если деплоите, или оставьте localhost
HTTP_REFERER: str = st.secrets.get("APP_URL", "http://localhost:8501")
APP_TITLE: str = "Streamlit Chat AI (Fixed)"
HEADERS: Dict[str, str] = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": HTTP_REFERER,
    "X-Title": APP_TITLE
}

# --- Настройка страницы Streamlit ---
st.set_page_config(
    page_title="Чат ИИ (Исправлено)", # Изменено название
    page_icon="💡", # Возвращена иконка
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Упрощенный и исправленный CSS ---
# Убраны многие агрессивные стили, которые могли конфликтовать с Streamlit
st.markdown("""
<style>
    /* Общие отступы */
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 5rem; /* Место для поля ввода */
        padding-left: 1.5rem;
        padding-right: 1.5rem;
    }

    /* Стилизация сообщений чата (минимальная) */
    [data-testid="stChatMessage"] {
        /* background-color: rgba(0, 0, 0, 0.03); убрано для совместимости с темами */
        border-radius: 0.5rem;
        padding: 0.7rem 1rem !important;
        margin-bottom: 1rem !important;
        border: 1px solid rgba(0, 0, 0, 0.08); /* Тонкая граница */
    }
    [data-testid="stChatMessage"] > div { /* Контейнер аватара и контента */
        gap: 0.75rem;
    }
    [data-testid="stChatMessage"] .stChatMessageContent p {
        line-height: 1.6;
    }

    /* Сайдбар */
    [data-testid="stSidebar"] {
        padding: 1.5rem 1rem;
        /* background-color: #f8f9fa; Убрано, чтобы не конфликтовать с темой */
    }
    [data-testid="stSidebar"] h2 { /* Заголовок Управление чатами */
        text-align: center;
        margin-bottom: 1.5rem;
        font-size: 1.3rem;
    }
     [data-testid="stSidebar"] h5 { /* Заголовок Режим ИИ */
        margin-top: 1rem;
        margin-bottom: 0.5rem;
        font-size: 1.1rem;
    }
    /* Кнопки в сайдбаре (осторожно) */
    [data-testid="stSidebar"] .stButton button {
        width: 100%;
        margin-bottom: 0.6rem;
        border-radius: 0.3rem;
        font-weight: 500;
        /* Не переопределяем фон/цвет, чтобы работали стандартные типы кнопок */
    }
    /* Кнопка удаления - используем стандартный secondary тип Streamlit */
    /* Дополнительные стили для нее убраны, чтобы не ломать */

    /* Виджеты в сайдбаре (очень осторожно) */
    [data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"],
    [data-testid="stSidebar"] [data-testid="stToggle"] label[data-baseweb="checkbox"] > div:first-child { /* Целимся точнее в лейбл toggle */
        font-size: 1rem; /* Стандартный размер */
        font-weight: 600;
        margin-bottom: 0.4rem;
        display: block; /* Убедимся, что лейбл занимает всю ширину */
    }
     [data-testid="stSidebar"] [data-testid="stToggle"] {
         margin-top: 1rem; /* Добавим отступ сверху для toggle */
     }

    /* Поле ввода - УБРАНО position: fixed, т.к. оно часто вызывает проблемы */
    [data-testid="stChatInput"] {
      /* background-color: #ffffff; */ /* Убрано для совместимости с темами */
      border-top: 1px solid rgba(0, 0, 0, 0.1); /* Граница сверху */
      padding: 1rem 1.5rem;
      /* position: fixed; */ /* УБРАНО */
      /* bottom: 0; */
      /* left: 0; */
      /* right: 0; */
      /* z-index: 100; */
      /* box-shadow: 0 -2px 5px rgba(0,0,0,0.05); */ /* Убрана тень */
    }

    /* Стили для markdown внутри сообщений (оставлены) */
    .stChatMessageContent code {
        background-color: rgba(0,0,0,0.06);
        padding: 0.2em 0.4em;
        border-radius: 3px;
        font-size: 85%;
    }
    .stChatMessageContent pre code {
        background-color: #f1f3f5;
        border: 1px solid #dee2e6;
        display: block;
        padding: 0.5rem 0.7rem;
        overflow-x: auto;
    }
    .stChatMessageContent blockquote {
        border-left: 3px solid #adb5bd;
        padding-left: 1rem;
        margin-left: 0;
        color: #6c757d;
    }
</style>
""", unsafe_allow_html=True)

# --- Проверка API ключа ---
if not OPENROUTER_API_KEY:
    st.error("⛔ Ключ API OpenRouter (`OPENROUTER_API_KEY`) не найден в секретах Streamlit!", icon="🚨")
    logger.critical("Ключ API OpenRouter не найден.")
    st.stop()

# --- Инициализация LocalStorage ---
try:
    localS = LocalStorage()
    logger.info("LocalStorage инициализирован успешно.")
except Exception as e:
    logger.error(f"Критическая ошибка инициализации LocalStorage: {e}", exc_info=True)
    st.error("Не удалось инициализировать локальное хранилище. История чатов не будет сохраняться между сессиями.", icon="🚨")
    localS = None

# --- Функции для работы с чатами (без изменений) ---
def load_all_chats() -> Tuple[Dict[str, List[Dict[str, str]]], Optional[str]]:
    """Загружает все чаты и имя активного чата из LocalStorage."""
    default_chats: Dict[str, List[Dict[str, str]]] = {f"{DEFAULT_CHAT_NAME} 1": []}
    default_active: str = f"{DEFAULT_CHAT_NAME} 1"
    initial_search_state: bool = False

    if "web_search_enabled" not in st.session_state:
        st.session_state.web_search_enabled = initial_search_state

    if not localS:
        logger.warning("LocalStorage недоступен, возврат чатов по умолчанию.")
        return default_chats, default_active

    data_str = localS.getItem(LOCAL_STORAGE_KEY)
    if not data_str:
        logger.info("Данные в LocalStorage не найдены, возврат чатов по умолчанию.")
        return default_chats, default_active

    try:
        data = json.loads(data_str)
        if isinstance(data, dict) and "chats" in data and "active_chat" in data and isinstance(data["chats"], dict):
            loaded_chats: Dict[str, List[Dict[str, str]]] = {}
            active_chat_name: Optional[str] = data["active_chat"]

            for name, history in data["chats"].items():
                if isinstance(history, list):
                    valid_history = [
                        msg for msg in history
                        if isinstance(msg, dict) and msg.get("role") in ["user", "assistant"] and isinstance(msg.get("content"), str)
                    ]
                    loaded_chats[name] = valid_history
                else:
                    logger.warning(f"История чата '{name}' имеет неверный формат, пропускается.")

            if not loaded_chats:
                logger.warning("После очистки не осталось валидных чатов, возврат к дефолтным.")
                st.session_state.web_search_enabled = initial_search_state
                return default_chats, default_active

            if active_chat_name not in loaded_chats:
                fallback_active = list(loaded_chats.keys())[0]
                logger.warning(f"Активный чат '{active_chat_name}' не найден, выбран первый: '{fallback_active}'.")
                active_chat_name = fallback_active

            st.session_state.web_search_enabled = data.get("web_search_enabled", initial_search_state)
            logger.info(f"Чаты загружены. Активный: '{active_chat_name}'. Поиск: {st.session_state.web_search_enabled}.")
            return loaded_chats, active_chat_name
        else:
            logger.warning("Структура данных в LocalStorage некорректна, возврат к дефолтным.")
            st.session_state.web_search_enabled = initial_search_state
            return default_chats, default_active
    except Exception as e:
        logger.error(f"Ошибка загрузки чатов: {e}. Возврат к дефолтным.", exc_info=True)
        st.session_state.web_search_enabled = initial_search_state
        return default_chats, default_active


def save_all_chats(chats_dict: Dict[str, List[Dict[str, str]]], active_chat_name: Optional[str], web_search_state: bool) -> bool:
    """Сохраняет все чаты, имя активного чата и состояние веб-поиска в LocalStorage."""
    if not localS:
        logger.warning("LocalStorage недоступен, сохранение невозможно.")
        return False
    if not isinstance(chats_dict, dict):
        logger.error("Попытка сохранить чаты неверного формата (не словарь).")
        return False

    cleaned_chats: Dict[str, List[Dict[str, str]]] = {}
    for name, history in chats_dict.items():
        if isinstance(history, list):
            cleaned_chats[name] = [
                msg for msg in history
                if isinstance(msg, dict) and msg.get("role") in ["user", "assistant"] and isinstance(msg.get("content"), str)
            ]

    if not cleaned_chats:
        active_chat_name = None
    elif active_chat_name not in cleaned_chats:
        fallback_active = list(cleaned_chats.keys())[0] if cleaned_chats else None
        logger.warning(f"Активный чат '{active_chat_name}' для сохранения не найден, выбран: {fallback_active}")
        active_chat_name = fallback_active

    data_to_save: Dict[str, Any] = {
        "chats": cleaned_chats,
        "active_chat": active_chat_name,
        "web_search_enabled": web_search_state
    }

    try:
        localS.setItem(LOCAL_STORAGE_KEY, json.dumps(data_to_save))
        logger.info(f"Чаты сохранены. Активный: '{active_chat_name}', Поиск: {web_search_state}.")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения чатов в LocalStorage: {e}", exc_info=True)
        st.toast("Ошибка сохранения состояния чата!", icon="🚨")
        return False

def generate_new_chat_name(existing_names: List[str]) -> str:
    """Генерирует уникальное имя для нового чата."""
    i = 1
    base_name = DEFAULT_CHAT_NAME
    while f"{base_name} {i}" in existing_names:
        i += 1
    return f"{base_name} {i}"

# --- Функции поиска и генерации запросов (без изменений) ---
def generate_search_queries(user_prompt: str) -> List[str]:
    """Генерирует поисковые запросы (вопросы) на основе промпта пользователя с помощью LLM."""
    current_date_str = datetime.datetime.now().strftime('%d %B %Y')
    generation_prompt = f"""Проанализируй следующий запрос пользователя. Твоя задача - сгенерировать до {MAX_QUERIES_TO_GENERATE} высококачественных, **полноценных поисковых вопросов на русском языке**. Эти вопросы должны помочь найти самую релевантную и актуальную информацию по теме.

**Требования к вопросам:**
- Формулируй естественные вопросы или описательные фразы, как если бы спрашивал человек.
- **Избегай простых ключевых слов.**
- Учитывай возможную потребность в свежей информации (сегодня {current_date_str}).
- Вопросы должны быть напрямую связаны с основной темой запроса пользователя.

**Примеры хороших вопросов:**
- Каковы последние достижения в [область]?
- Как работает [технология] простыми словами?
- Сравнение [продукт А] и [продукт Б] в {datetime.datetime.now().year} году: плюсы и минусы.
- Последние новости о [событие/компания].
- Лучшие практики для [задача].

**Вывод:**
Выведи только сгенерированные вопросы, каждый на новой строке. Без нумерации, маркеров или кавычек.

**Запрос пользователя:**
"{user_prompt}"

**Поисковые вопросы:**"""

    payload = {
        "model": SEARCH_QUERY_GENERATION_MODEL, # Используем указанную модель
        "messages": [{"role": "user", "content": generation_prompt}],
        "max_tokens": 150,
        "temperature": 0.5,
        "stop": ["\n\n"],
    }
    generated_queries: List[str] = []

    try:
        logger.info(f"Генерация поисковых ВОПРОСОВ для: '{user_prompt[:50]}...'")
        response = requests.post(OPENROUTER_API_URL, headers=HEADERS, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        raw_queries_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if raw_queries_text:
            potential_queries = raw_queries_text.strip().split('\n')
            generated_queries = [
                re.sub(r"^\s*[\d\.\-\*]+\s*", "", q.strip()).strip('" ')
                for q in potential_queries if q.strip() and len(q.strip()) > 5
            ]
            logger.info(f"  Сгенерировано {len(generated_queries)} вопросов: {generated_queries}")
        else:
            logger.warning("  API не вернуло текст для генерации вопросов.")

    except requests.exceptions.Timeout:
        logger.error("  Ошибка генерации вопросов: Таймаут.")
        st.toast("Таймаут при подборе поисковых вопросов.", icon="⏱️")
    except requests.exceptions.RequestException as e:
        logger.error(f"  Ошибка сети при генерации вопросов: {e}")
        st.toast(f"Ошибка сети при подборе вопросов: {e}", icon="🚨")
    except Exception as e:
        logger.error(f"  Неизвестная ошибка при генерации вопросов: {e}", exc_info=True)
        st.toast("Не удалось подобрать поисковые вопросы.", icon="❓")

    return generated_queries[:MAX_QUERIES_TO_GENERATE]

def clean_html(raw_html: Optional[str]) -> str:
    """Удаляет HTML теги и декодирует HTML сущности."""
    if not isinstance(raw_html, str): return ""
    cleanr = re.compile('<.*?>'); cleantext = re.sub(cleanr, '', raw_html)
    cleantext = unescape(cleantext); cleantext = re.sub(r'\s+', ' ', cleantext).strip()
    return cleantext

def perform_web_search(queries: List[str]) -> Tuple[str, bool]:
    """Выполняет веб-поиск по списку запросов с помощью DuckDuckGo Search."""
    all_results_text: str = ""
    search_errors: List[str] = []
    search_performed_successfully: bool = False

    if not queries:
        logger.warning("Нет запросов для веб-поиска.")
        return "Веб-поиск не выполнялся (нет запросов).", False

    logger.info(f"Начинаю веб-поиск по {len(queries)} запросам...")
    aggregated_results: List[Dict[str, str]] = []

    try:
        with DDGS(timeout=REQUEST_TIMEOUT) as ddgs:
            for idx, query in enumerate(queries, 1):
                query_log = f"'{query[:60]}...'" if len(query) > 60 else f"'{query}'"
                logger.info(f"  [Поиск {idx}/{len(queries)}] Запрос: {query_log}")
                try:
                    search_results = list(ddgs.text(query, max_results=MAX_SEARCH_RESULTS_PER_QUERY))
                    for result in search_results:
                        result['title'] = clean_html(result.get('title', 'Без заголовка'))
                        result['body'] = clean_html(result.get('body', ''))
                    aggregated_results.extend(search_results)
                    logger.info(f"    Найдено {len(search_results)} для {query_log}.")
                except Exception as e:
                    logger.error(f"    Ошибка поиска по запросу {query_log}: {e}", exc_info=False) # Убрал exc_info для краткости лога
                    search_errors.append(query_log)

        if search_errors: st.toast(f"Проблемы при поиске: {', '.join(search_errors)}", icon="🕸️")

        if aggregated_results:
            unique_results_dict: Dict[str, Dict[str, str]] = {}
            for res in aggregated_results:
                body = res.get('body')
                if body and body not in unique_results_dict: unique_results_dict[body] = res
            unique_results = list(unique_results_dict.values())
            logger.info(f"Всего найдено: {len(aggregated_results)}, Уникальных: {len(unique_results)}")

            if unique_results:
                result_lines = [f"Источник {i}: {res.get('title', 'Без заголовка')}\nСниппет: {(res.get('body', '')[:MAX_SNIPPET_LENGTH] + '...') if len(res.get('body', '')) > MAX_SNIPPET_LENGTH else res.get('body', '')}" for i, res in enumerate(unique_results, 1)]
                all_results_text = "\n\n".join(result_lines)
                search_performed_successfully = True
                logger.info("Веб-поиск завершен успешно, результаты отформатированы.")
            else: all_results_text = "Веб-поиск не дал уникальных текстовых результатов."; logger.info(all_results_text)
        else: all_results_text = "Веб-поиск не вернул результатов."; logger.info(all_results_text)
        return all_results_text.strip(), search_performed_successfully

    except Exception as e:
        logger.error(f"Критическая ошибка во время веб-поиска: {e}", exc_info=True)
        st.error(f"Критическая ошибка веб-поиска: {e}", icon="🕸️")
        return f"Критическая ошибка веб-поиска: {e}", False

# --- Функция стриминга ответа ИИ (без изменений) ---
def stream_ai_response(model_id: str, chat_history: List[Dict[str, str]]) -> Generator[Optional[str], None, None]:
    """Отправляет запрос к API и возвращает генератор для стриминга ответа."""
    if not isinstance(chat_history, list) or not chat_history:
        logger.error("Неверный формат истории чата для стриминга.")
        yield None; return

    payload = {"model": model_id, "messages": chat_history, "stream": True}
    stream_successful: bool = False; response = None
    try:
        logger.info(f"Запрос стриминга к модели: {model_id}")
        response = requests.post(OPENROUTER_API_URL, headers=HEADERS, json=payload, stream=True, timeout=(REQUEST_TIMEOUT, STREAM_TIMEOUT))
        response.raise_for_status()
        logger.info("Стриминг начат успешно.")
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    try:
                        json_data_str = decoded_line[len("data: "):].strip()
                        if json_data_str == "[DONE]": logger.info("Стриминг [DONE]."); break
                        if json_data_str:
                            chunk = json.loads(json_data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            delta_content = delta.get("content")
                            if delta_content: stream_successful = True; yield delta_content
                    except json.JSONDecodeError: logger.warning(f"Ошибка JSON чанка: '{json_data_str}'"); continue
                    except Exception as e: logger.error(f"Ошибка обработки чанка: {e}", exc_info=True); continue
        if not stream_successful: logger.warning("Стрим завершился без контента.")
    except requests.exceptions.Timeout as e: logger.error(f"Ошибка стриминга: Таймаут ({STREAM_TIMEOUT}s). {e}"); yield None
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети/API стриминга: {e}")
        error_details = "Нет деталей ответа.";
        if response is not None:
            try: error_details = response.text[:500]
            except Exception: pass
        logger.error(f"  Детали: {error_details}"); yield None
    except Exception as e: logger.error(f"Неизвестная ошибка стриминга: {e}", exc_info=True); yield None
    finally:
        if response is not None:
            try: response.close(); logger.debug("Соединение стриминга закрыто.")
            except Exception: pass

# --- Инициализация состояния Streamlit (без изменений) ---
if "all_chats" not in st.session_state or "active_chat" not in st.session_state:
    logger.info("Первичная инициализация состояния сессии (чаты).")
    st.session_state.all_chats, st.session_state.active_chat = load_all_chats()
else: logger.debug("Состояние сессии (чаты) уже инициализировано.")
if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = DEFAULT_MODE
    logger.info(f"Инициализация режима по умолчанию: {DEFAULT_MODE}")
if "web_search_enabled" not in st.session_state:
     st.session_state.web_search_enabled = False
     logger.warning("web_search_enabled не был установлен, установлен в False.")

# --- Проверка и корректировка активного чата (без изменений) ---
if not isinstance(st.session_state.get("all_chats"), dict):
     logger.error("Критическая ошибка: st.session_state.all_chats не словарь. Сброс.")
     st.session_state.all_chats, st.session_state.active_chat = load_all_chats()
active_chat_name = st.session_state.get("active_chat")
all_chats_keys = list(st.session_state.all_chats.keys())
if active_chat_name not in all_chats_keys:
    logger.warning(f"Активный чат '{active_chat_name}' не найден. Список: {all_chats_keys}.")
    if all_chats_keys: st.session_state.active_chat = all_chats_keys[0]
    else:
        new_name = generate_new_chat_name([])
        st.session_state.all_chats = {new_name: []}; st.session_state.active_chat = new_name
        logger.info(f"Создан новый чат: '{new_name}'")
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
    st.rerun()

# --- Сайдбар (исправлены виджеты) ---
with st.sidebar:
    st.markdown("## 💬 Управление чатами")
    chat_names = list(st.session_state.all_chats.keys())

    # Выбор активного чата
    try: active_chat_index = chat_names.index(st.session_state.active_chat)
    except ValueError:
        logger.warning(f"Активный чат '{st.session_state.active_chat}' не найден в {chat_names}. Выбран первый.")
        active_chat_index = 0
        if chat_names: st.session_state.active_chat = chat_names[0]
        else: logger.error("Критическая ошибка: Нет чатов для выбора."); st.error("Ошибка: Нет чатов."); st.stop()

    # Radio должен теперь отображаться корректно
    selected_chat = st.radio(
        "Выберите чат:", # Лейбл теперь виден, т.к. стили упрощены
        options=chat_names,
        index=active_chat_index,
        key="chat_selector"
        # label_visibility="collapsed" # Убрано, т.к. могло вызывать проблемы со стилями
    )

    if selected_chat is not None and selected_chat != st.session_state.active_chat:
        st.session_state.active_chat = selected_chat
        logger.info(f"Выбран чат: {selected_chat}")
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
        st.rerun()

    # Кнопки управления чатами
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Новый", key="new_chat_button", help="Создать новый пустой чат", use_container_width=True):
            new_name = generate_new_chat_name(chat_names)
            st.session_state.all_chats[new_name] = []
            st.session_state.active_chat = new_name
            logger.info(f"Создан чат: {new_name}")
            save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
            st.rerun()
    with col2:
        if chat_names:
             # Используем стандартный secondary тип для кнопки удаления
            if st.button("🗑️ Удалить", key="delete_chat_button", type="secondary", help="Удалить текущий чат", use_container_width=True):
                chat_to_delete = st.session_state.active_chat
                logger.info(f"Удаление чата: {chat_to_delete}")
                if chat_to_delete in st.session_state.all_chats:
                    del st.session_state.all_chats[chat_to_delete]
                    logger.info(f"Чат '{chat_to_delete}' удален.")
                    remaining_chats = list(st.session_state.all_chats.keys())
                    if remaining_chats: st.session_state.active_chat = remaining_chats[0]
                    else:
                        new_name = generate_new_chat_name([])
                        st.session_state.all_chats = {new_name: []}; st.session_state.active_chat = new_name
                        logger.info("Создан новый чат после удаления последнего.")
                    save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
                    st.toast(f"Чат '{chat_to_delete}' удален.", icon="🗑️")
                    st.rerun()
                else: logger.warning(f"Попытка удалить несуществующий чат: {chat_to_delete}"); st.toast("Ошибка: Чат не найден.", icon="❓")

    st.divider()

    # Переключатель веб-поиска (должен отображаться корректно)
    search_toggled = st.toggle(
        "🌐 Веб-поиск",
        value=st.session_state.web_search_enabled,
        key="web_search_toggle",
        help="Использовать поиск в интернете для актуальных ответов"
    )
    if search_toggled != st.session_state.web_search_enabled:
        st.session_state.web_search_enabled = search_toggled
        logger.info(f"Веб-поиск изменен на: {search_toggled}")
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)

    st.divider()

    # Выбор режима (модели) (должен отображаться корректно)
    st.markdown("##### 🧠 Режим ИИ")
    mode_options = list(MODES.keys())
    try: current_mode_index = mode_options.index(st.session_state.selected_mode)
    except ValueError:
        logger.warning(f"Режим '{st.session_state.selected_mode}' не найден. Сброс на {DEFAULT_MODE}.")
        st.session_state.selected_mode = DEFAULT_MODE
        current_mode_index = mode_options.index(DEFAULT_MODE)

    selected_mode_radio = st.radio(
        "Выберите модель:", # Лейбл виден
        options=mode_options,
        index=current_mode_index,
        key="mode_selector"
        # label_visibility="collapsed" # Убрано
    )
    if selected_mode_radio is not None and selected_mode_radio != st.session_state.selected_mode:
        st.session_state.selected_mode = selected_mode_radio
        logger.info(f"Выбран режим: {selected_mode_radio}")

# --- Основная область: Чат (без изменений в логике) ---
current_active_chat_name = st.session_state.active_chat
current_mode_name = st.session_state.selected_mode
current_model_id = MODES.get(current_mode_name, MODES[DEFAULT_MODE])

st.markdown(f"### Чат: {current_active_chat_name} <span style='font-size: 0.7em; color: grey;'>({current_mode_name.strip()})</span>", unsafe_allow_html=True)

chat_container = st.container()
with chat_container:
    if current_active_chat_name in st.session_state.all_chats:
        chat_history = st.session_state.all_chats[current_active_chat_name]
        for i, message in enumerate(chat_history):
            role = message.get("role"); content = message.get("content")
            avatar = "🧑‍💻" if role == "user" else "💡" # Возвращен ваш вариант аватара ИИ
            if role and content:
                with st.chat_message(role, avatar=avatar):
                    st.markdown(content, unsafe_allow_html=True)
            else: logger.warning(f"Пропущено некорректное сообщение: {message}")
    else: st.warning(f"Чат '{current_active_chat_name}' не найден."); logger.error(f"Попытка отобразить историю несуществующего чата: {current_active_chat_name}")

# --- Поле ввода пользователя (без изменений в логике) ---
prompt = st.chat_input(f"Спросите {current_mode_name.strip()}...")
if prompt:
    if current_active_chat_name in st.session_state.all_chats:
        logger.info(f"Новый промпт в '{current_active_chat_name}'.")
        user_message: Dict[str, str] = {"role": "user", "content": prompt}
        st.session_state.all_chats[current_active_chat_name].append(user_message)
        save_all_chats(st.session_state.all_chats, current_active_chat_name, st.session_state.web_search_enabled)
        st.rerun()
    else:
        st.error("Ошибка: Чат не найден.", icon="❌")
        logger.error(f"Ошибка добавления сообщения: чат '{current_active_chat_name}' не найден.")

# --- Логика генерации и стриминга ответа ИИ (без изменений в логике) ---
if current_active_chat_name in st.session_state.all_chats:
    current_chat_history = st.session_state.all_chats[current_active_chat_name]
    if current_chat_history and current_chat_history[-1]["role"] == "user":
        last_user_prompt = current_chat_history[-1]["content"]
        logger.info(f"\n--- Начало обработки ответа ИИ для '{current_active_chat_name}' ---")
        logger.info(f"Промпт: '{last_user_prompt[:100]}...' | Поиск: {'ВКЛ' if st.session_state.web_search_enabled else 'ВЫКЛ'}")
        context_for_ai: List[Dict[str, str]] = list(current_chat_history)
        system_prompt_content: Optional[str] = None
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")

        # --- Веб-поиск ---
        if st.session_state.web_search_enabled:
            logger.info(">>> Веб-поиск активирован.")
            search_results_str: str = "Поиск не выполнялся."; search_performed_successfully: bool = False; generated_queries: List[str] = []
            try:
                with st.spinner("Подбираю поисковые запросы... 🤔"): generated_queries = generate_search_queries(last_user_prompt)
            except Exception as e: logger.error(f"Ошибка generate_search_queries: {e}", exc_info=True); st.error("Ошибка подбора вопросов.", icon="❓")
            queries_to_search = generated_queries if generated_queries else [last_user_prompt]
            if not generated_queries: logger.warning("Используется исходный промпт для поиска.")
            search_spinner_text = f"Ищу в сети ({len(queries_to_search)})... 🌐"
            try:
                with st.spinner(search_spinner_text): search_results_str, search_performed_successfully = perform_web_search(queries_to_search)
                if search_performed_successfully:
                    logger.info("Веб-поиск успешен.")
                    system_prompt_content = f"""Текущая дата: {current_date}. Был выполнен веб-поиск. **Твоя задача:** Изучи результаты ниже и **синтезируй из них единый, связный ответ** на исходный запрос пользователя. Приоритет отдавай информации из поиска. Не упоминай сам факт поиска и не включай URL.\n\n--- Результаты веб-поиска ---\n{search_results_str}\n--- Конец результатов ---\n\nОтветь на запрос пользователя, основываясь на этой информации."""
                else:
                    logger.warning(f"Веб-поиск неудачен/пуст: '{search_results_str}'")
                    system_prompt_content = f"""Текущая дата: {current_date}. Веб-поиск был включен, но **не дал релевантных результатов** (Причина: '{search_results_str}'). Отвечай на запрос пользователя, **основываясь только на своих знаниях**. **Обязательно предупреди пользователя**, что ответ может быть неактуальным."""
            except Exception as e:
                logger.error(f"Ошибка perform_web_search: {e}", exc_info=True); st.error("Ошибка веб-поиска.", icon="🕸️");
                system_prompt_content = f"""Текущая дата: {current_date}. Произошла **ошибка** при веб-поиске. Отвечай на запрос пользователя, **основываясь только на своих знаниях**. Предупреди пользователя об ошибке поиска."""
        else: # Поиск выключен
            logger.info(">>> Веб-поиск выключен.")
            system_prompt_content = f"Текущая дата: {current_date}. Веб-поиск ВЫКЛЮЧЕН. Отвечай на запрос пользователя, основываясь только на своих общих знаниях."

        # --- Добавление системного промпта ---
        if system_prompt_content:
            context_for_ai.insert(-1, {"role": "system", "content": system_prompt_content})
            logger.info("Системный промпт добавлен.")

        # --- Стриминг ответа ---
        logger.info(">>> Запрос и стриминг ответа ИИ.")
        final_response_to_save: Optional[str] = None; ai_response_error: bool = False; full_response_chunks: List[str] = []
        try:
            with st.chat_message("assistant", avatar="💡"): # Возвращен ваш аватар
                message_placeholder = st.empty()
                message_placeholder.markdown("Генерирую ответ... ⏳")
                response_generator = stream_ai_response(current_model_id, context_for_ai)
                for chunk in response_generator:
                    if chunk is None:
                        logger.error("Генератор стриминга вернул ошибку (None).")
                        ai_response_error = True; message_placeholder.error("Ошибка получения ответа!", icon="🔥"); break
                    if chunk:
                        full_response_chunks.append(chunk)
                        message_placeholder.markdown("".join(full_response_chunks) + " ▌", unsafe_allow_html=True)
                if not ai_response_error:
                    final_response_to_save = "".join(full_response_chunks).strip()
                    if final_response_to_save: message_placeholder.markdown(final_response_to_save, unsafe_allow_html=True); logger.info("Ответ ИИ отображен.")
                    else: logger.warning("Ответ от ИИ пуст."); message_placeholder.warning("ИИ не предоставил ответ.", icon="🤷"); final_response_to_save = None
        except Exception as e:
             logger.error(f"Ошибка при отображении ответа ИИ: {e}", exc_info=True)
             st.error(f"Ошибка отображения ответа: {e}", icon="💥"); final_response_to_save = None; ai_response_error = True

        # --- Сохранение ответа ---
        if final_response_to_save and not ai_response_error:
            logger.info(">>> Сохранение ответа ИИ.")
            try:
                if current_active_chat_name in st.session_state.all_chats:
                     assistant_message: Dict[str, str] = {"role": "assistant", "content": final_response_to_save}
                     # Проверка на дубликат перед добавлением
                     if not current_chat_history or current_chat_history[-1] != assistant_message:
                          st.session_state.all_chats[current_active_chat_name].append(assistant_message)
                          save_all_chats(st.session_state.all_chats, current_active_chat_name, st.session_state.web_search_enabled)
                          logger.info("Ответ ассистента сохранен.")
                     else:
                          logger.warning("Попытка добавить дублирующее сообщение ассистента. Пропущено.")
                else: logger.error(f"Ошибка сохранения: чат '{current_active_chat_name}' не найден."); st.error("Ошибка: не удалось сохранить ответ.", icon="❌")
            except Exception as e: logger.error(f"Ошибка при сохранении ответа: {e}", exc_info=True); st.error(f"Ошибка сохранения ответа: {e}", icon="💾")
        elif ai_response_error: logger.warning("Ответ ИИ не сохранен из-за ошибки.")
        elif not final_response_to_save: logger.warning("Пустой ответ ИИ не сохранен.")

        logger.info(f"--- Обработка ответа ИИ для '{current_active_chat_name}' завершена ---")

# Добавляем небольшой отступ снизу (опционально, т.к. убрали fixed input)
# st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)
