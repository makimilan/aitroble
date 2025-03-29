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
# Устанавливаем более информативный формат и уровень INFO
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Ключ API из секретов Streamlit ---
# Получаем ключ API, обеспечивая его наличие
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY")

# --- Константы ---
# API и модели
OPENROUTER_API_URL: str = "https://openrouter.ai/api/v1/chat/completions"
# Обновленные или предпочитаемые модели (можно легко менять)
MODES: Dict[str, str] = {
    " Claude 3 Sonnet": "anthropic/claude-3-sonnet-20240229", # Добавлен для примера
    " Mistral Large": "mistralai/mistral-large-latest", # Добавлен для примера
    " DeepSeek V2": "deepseek/deepseek-chat", # Обновлен
    " DeepThink (R1)": "deepseek/deepseek-r1:free", # Оставлен
    " Стандарт (V3)": "deepseek/deepseek-chat-v3-0324:free", # Оставлен
}
DEFAULT_MODE: str = " Claude 3 Sonnet" # Изменен дефолтный режим

# Локальное хранилище
LOCAL_STORAGE_KEY: str = "multi_chat_storage_v19" # Снова сменил ключ для обновления
DEFAULT_CHAT_NAME: str = "Новый чат"

# Веб-поиск
MAX_SEARCH_RESULTS_PER_QUERY: int = 3 # Уменьшил для краткости
MAX_QUERIES_TO_GENERATE: int = 2 # Уменьшил для скорости
MAX_SNIPPET_LENGTH: int = 250 # Немного уменьшил
SEARCH_QUERY_GENERATION_MODEL: str = "deepseek/deepseek-chat" # Конкретная модель для генерации запросов

# Сеть и тайм-ауты
REQUEST_TIMEOUT: int = 30 # Общий таймаут для запросов
STREAM_TIMEOUT: int = 180 # Таймаут для стриминга

# Заголовки для API
HTTP_REFERER: str = "https://your-streamlit-app-url.com" # **ВАЖНО:** Замените на URL вашего приложения, если деплоите
APP_TITLE: str = "Streamlit Advanced Chat AI"
HEADERS: Dict[str, str] = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": HTTP_REFERER,
    "X-Title": APP_TITLE
}

# --- Настройка страницы Streamlit ---
st.set_page_config(
    page_title="Чат ИИ Pro",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Улучшенный CSS ---
st.markdown("""
<style>
    /* Общие стили */
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* Убираем лишние отступы Streamlit */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 5rem; /* Больше места снизу для поля ввода */
        padding-left: 1.5rem;
        padding-right: 1.5rem;
    }

    /* Стилизация сообщений чата */
    [data-testid="stChatMessage"] {
        background-color: rgba(0, 0, 0, 0.03); /* Легкий фон для сообщений */
        border-radius: 0.5rem;
        padding: 0.8rem 1rem !important; /* Внутренние отступы */
        margin-bottom: 1rem !important; /* Отступ между сообщениями */
        border: 1px solid rgba(0, 0, 0, 0.05);
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    [data-testid="stChatMessage"] > div { /* Контейнер аватара и контента */
        gap: 0.75rem;
    }
    [data-testid="stChatMessage"] .stChatMessageContent {
        padding: 0 !important;
    }
    [data-testid="stChatMessage"] .stChatMessageContent p {
        margin-bottom: 0.2rem;
        line-height: 1.6; /* Улучшаем читаемость текста */
    }
    /* Выделение сообщения пользователя */
    [data-testid="stChatMessage"][data-testid="chatAvatarIcon-user"] {
         background-color: rgba(80, 137, 207, 0.08); /* Немного другой фон для пользователя */
         border-color: rgba(80, 137, 207, 0.2);
    }

    /* Сайдбар */
    [data-testid="stSidebar"] {
        padding: 1.5rem 1rem;
        background-color: #f8f9fa; /* Светлый фон сайдбара */
        border-right: 1px solid #e9ecef;
    }
    [data-testid="stSidebar"] h2 {
        text-align: center;
        margin-bottom: 1.5rem;
        font-size: 1.3rem;
        color: #343a40;
    }
    [data-testid="stSidebar"] .stButton button {
        width: 100%;
        margin-bottom: 0.6rem;
        border-radius: 0.3rem; /* Менее скругленные кнопки */
        font-weight: 500;
        background-color: #ffffff; /* Белые кнопки */
        border: 1px solid #ced4da;
        color: #495057;
        transition: background-color 0.2s ease, border-color 0.2s ease;
    }
    [data-testid="stSidebar"] .stButton button:hover {
        background-color: #f1f3f5;
        border-color: #adb5bd;
    }
    [data-testid="stSidebar"] .stButton button:active {
        background-color: #e9ecef;
    }
    /* Кнопка удаления - красная */
    [data-testid="stSidebar"] .stButton[data-testid*="delete_chat_button"] button {
        background-color: #f8d7da;
        border-color: #f5c6cb;
        color: #721c24;
    }
    [data-testid="stSidebar"] .stButton[data-testid*="delete_chat_button"] button:hover {
        background-color: #f1b0b7;
        border-color: #eba3ab;
    }
    /* Радио-кнопки и переключатель */
    [data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"],
    [data-testid="stSidebar"] [data-testid="stToggle"] label {
        font-size: 0.95rem;
        margin-bottom: 0.4rem;
        font-weight: 600;
        color: #495057;
    }
    [data-testid="stSidebar"] .stRadio > div { /* Отступы для радио */
        padding: 0.1rem 0;
    }
    [data-testid="stSidebar"] [data-testid="stToggle"] { /* Отступ для переключателя */
         margin-top: 0.5rem;
    }

    /* Поле ввода */
    [data-testid="stChatInput"] {
      background-color: #ffffff;
      border-top: 1px solid #e9ecef;
      padding: 0.75rem 1.5rem; /* Отступы вокруг поля ввода */
      position: fixed; /* Фиксируем внизу */
      bottom: 0;
      left: 0;
      right: 0;
      z-index: 100; /* Поверх остального контента */
      box-shadow: 0 -2px 5px rgba(0,0,0,0.05);
    }
    [data-testid="stChatInput"] textarea {
        border-radius: 0.3rem;
        border: 1px solid #ced4da;
        background-color: #f8f9fa; /* Легкий фон для поля */
    }
    [data-testid="stChatInput"] textarea:focus {
        border-color: #80bdff;
        box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
    }

    /* Спиннер */
    [data-testid="stSpinner"] > div > div {
        /* Стилизация самого спиннера (крутилки) */
        border-top-color: #0d6efd; /* Цвет спиннера */
    }

    /* Стили для markdown внутри сообщений */
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
    st.stop() # Останавливаем выполнение, если ключа нет

# --- Инициализация LocalStorage ---
# Обернуто в try-except для большей надежности
try:
    localS = LocalStorage()
    logger.info("LocalStorage инициализирован успешно.")
except Exception as e:
    logger.error(f"Критическая ошибка инициализации LocalStorage: {e}", exc_info=True)
    st.error("Не удалось инициализировать локальное хранилище. История чатов не будет сохраняться между сессиями.", icon="🚨")
    localS = None # Устанавливаем в None, чтобы функции проверки работали

# --- Функции для работы с чатами ---

def load_all_chats() -> Tuple[Dict[str, List[Dict[str, str]]], Optional[str]]:
    """Загружает все чаты и имя активного чата из LocalStorage."""
    default_chats: Dict[str, List[Dict[str, str]]] = {f"{DEFAULT_CHAT_NAME} 1": []}
    default_active: str = f"{DEFAULT_CHAT_NAME} 1"
    initial_search_state: bool = False # По умолчанию поиск выключен

    # Устанавливаем начальное состояние поиска в session_state, если его нет
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
        # Проверяем структуру данных
        if isinstance(data, dict) and "chats" in data and "active_chat" in data and isinstance(data["chats"], dict):
            loaded_chats: Dict[str, List[Dict[str, str]]] = {}
            active_chat_name: Optional[str] = data["active_chat"]

            # Очистка и проверка каждого чата
            for name, history in data["chats"].items():
                if isinstance(history, list):
                    # Фильтруем сообщения, оставляя только валидные
                    valid_history = [
                        msg for msg in history
                        if isinstance(msg, dict) and msg.get("role") in ["user", "assistant"] and isinstance(msg.get("content"), str)
                    ]
                    loaded_chats[name] = valid_history
                else:
                    logger.warning(f"История чата '{name}' имеет неверный формат (не список), пропускается.")

            # Если после очистки чатов не осталось, возвращаем дефолтные
            if not loaded_chats:
                logger.warning("После очистки не осталось валидных чатов, возврат к дефолтным.")
                st.session_state.web_search_enabled = initial_search_state # Сброс поиска
                return default_chats, default_active

            # Проверяем, существует ли активный чат
            if active_chat_name not in loaded_chats:
                fallback_active = list(loaded_chats.keys())[0]
                logger.warning(f"Активный чат '{active_chat_name}' не найден в загруженных чатах, выбран первый доступный: '{fallback_active}'.")
                active_chat_name = fallback_active

            # Загружаем состояние веб-поиска
            st.session_state.web_search_enabled = data.get("web_search_enabled", initial_search_state)
            logger.info(f"Чаты успешно загружены. Активный чат: '{active_chat_name}'. Веб-поиск: {st.session_state.web_search_enabled}.")
            return loaded_chats, active_chat_name
        else:
            logger.warning("Структура данных в LocalStorage некорректна, возврат чатов по умолчанию.")
            st.session_state.web_search_enabled = initial_search_state # Сброс поиска
            return default_chats, default_active
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка декодирования JSON из LocalStorage: {e}. Возврат чатов по умолчанию.", exc_info=True)
        st.session_state.web_search_enabled = initial_search_state # Сброс поиска
        return default_chats, default_active
    except Exception as e:
        logger.error(f"Неожиданная ошибка при загрузке чатов: {e}. Возврат чатов по умолчанию.", exc_info=True)
        st.session_state.web_search_enabled = initial_search_state # Сброс поиска
        return default_chats, default_active


def save_all_chats(chats_dict: Dict[str, List[Dict[str, str]]], active_chat_name: Optional[str], web_search_state: bool) -> bool:
    """Сохраняет все чаты, имя активного чата и состояние веб-поиска в LocalStorage."""
    if not localS:
        logger.warning("LocalStorage недоступен, сохранение невозможно.")
        return False
    if not isinstance(chats_dict, dict):
        logger.error("Попытка сохранить чаты неверного формата (не словарь).")
        return False

    # Очистка данных перед сохранением (на всякий случай)
    cleaned_chats: Dict[str, List[Dict[str, str]]] = {}
    for name, history in chats_dict.items():
        if isinstance(history, list):
            cleaned_chats[name] = [
                msg for msg in history
                if isinstance(msg, dict) and msg.get("role") in ["user", "assistant"] and isinstance(msg.get("content"), str)
            ]
        else:
            logger.warning(f"При сохранении обнаружена неверная история для чата '{name}', будет пропущена.")

    # Проверка активного чата
    if not cleaned_chats:
        active_chat_name = None # Нет чатов - нет активного
        logger.info("Нет чатов для сохранения.")
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


# --- Функции поиска и генерации запросов ---

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
        "model": SEARCH_QUERY_GENERATION_MODEL,
        "messages": [{"role": "user", "content": generation_prompt}],
        "max_tokens": 150,
        "temperature": 0.5, # Чуть выше для разнообразия
        "stop": ["\n\n"], # Останавливаемся на двойном переносе строки
    }
    generated_queries: List[str] = []

    try:
        logger.info(f"Генерация поисковых ВОПРОСОВ для: '{user_prompt[:50]}...'")
        response = requests.post(OPENROUTER_API_URL, headers=HEADERS, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status() # Проверка на HTTP ошибки
        data = response.json()
        raw_queries_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if raw_queries_text:
            # Очистка и фильтрация сгенерированных строк
            potential_queries = raw_queries_text.strip().split('\n')
            generated_queries = [
                re.sub(r"^\s*[\d\.\-\*]+\s*", "", q.strip()).strip('" ') # Удаляем нумерацию/маркеры и кавычки
                for q in potential_queries if q.strip() and len(q.strip()) > 5 # Отсеиваем пустые и слишком короткие строки
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

    # Возвращаем не более MAX_QUERIES_TO_GENERATE
    return generated_queries[:MAX_QUERIES_TO_GENERATE]


def clean_html(raw_html: Optional[str]) -> str:
    """Удаляет HTML теги и декодирует HTML сущности."""
    if not isinstance(raw_html, str):
        return ""
    # Удаляем теги
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    # Декодируем сущности типа &
    cleantext = unescape(cleantext)
    # Удаляем лишние пробелы
    cleantext = re.sub(r'\s+', ' ', cleantext).strip()
    return cleantext


def perform_web_search(queries: List[str]) -> Tuple[str, bool]:
    """Выполняет веб-поиск по списку запросов с помощью DuckDuckGo Search."""
    all_results_text: str = ""
    search_errors: List[str] = []
    search_performed_successfully: bool = False

    if not queries:
        logger.warning("Нет запросов для веб-поиска.")
        return "Веб-поиск не выполнялся, так как не было сгенерировано или предоставлено поисковых запросов.", False

    logger.info(f"Начинаю веб-поиск по {len(queries)} запросам...")
    aggregated_results: List[Dict[str, str]] = []

    try:
        # Используем менеджер контекста для DDGS
        with DDGS(timeout=REQUEST_TIMEOUT) as ddgs:
            for idx, query in enumerate(queries, 1):
                query_log = f"'{query[:60]}...'" if len(query) > 60 else f"'{query}'"
                logger.info(f"  [Поиск {idx}/{len(queries)}] Запрос: {query_log}")
                try:
                    # Получаем результаты поиска
                    search_results = list(ddgs.text(query, max_results=MAX_SEARCH_RESULTS_PER_QUERY))
                    # Очищаем заголовки и сниппеты
                    for result in search_results:
                        result['title'] = clean_html(result.get('title', 'Без заголовка'))
                        result['body'] = clean_html(result.get('body', '')) # Очищаем тело
                    aggregated_results.extend(search_results)
                    logger.info(f"    Найдено {len(search_results)} результатов для {query_log}.")
                except Exception as e:
                    logger.error(f"    Ошибка поиска по запросу {query_log}: {e}", exc_info=True)
                    search_errors.append(query_log) # Добавляем проблемный запрос в список

        if search_errors:
            st.toast(f"Проблемы при поиске по: {', '.join(search_errors)}", icon="🕸️")

        # Обработка и форматирование результатов
        if aggregated_results:
            # Фильтруем дубликаты по очищенному тексту сниппета (body)
            unique_results_dict: Dict[str, Dict[str, str]] = {}
            for res in aggregated_results:
                body = res.get('body')
                # Добавляем только если есть тело и такого тела еще не было
                if body and body not in unique_results_dict:
                    unique_results_dict[body] = res

            unique_results = list(unique_results_dict.values())
            logger.info(f"Всего найдено: {len(aggregated_results)}, Уникальных (по сниппету): {len(unique_results)}")

            if unique_results:
                # Формируем текстовое представление результатов
                result_lines = []
                for i, res in enumerate(unique_results, 1):
                    title = res.get('title', 'Без заголовка')
                    body = res.get('body', '')
                    # Обрезаем сниппет, если он слишком длинный
                    snippet = (body[:MAX_SNIPPET_LENGTH] + '...') if len(body) > MAX_SNIPPET_LENGTH else body
                    result_lines.append(f"Источник {i}: {title}\nСниппет: {snippet}")

                all_results_text = "\n\n".join(result_lines)
                search_performed_successfully = True # Поиск успешен, есть результаты
                logger.info("Веб-поиск завершен успешно, результаты отформатированы.")
            else:
                all_results_text = "Веб-поиск не дал уникальных текстовых результатов после фильтрации."
                logger.info(all_results_text)
                # search_performed_successfully остается False
        else:
            all_results_text = "Веб-поиск не вернул результатов."
            logger.info(all_results_text)
            # search_performed_successfully остается False

        return all_results_text.strip(), search_performed_successfully

    except Exception as e:
        logger.error(f"Критическая ошибка во время веб-поиска: {e}", exc_info=True)
        st.error(f"Критическая ошибка веб-поиска: {e}", icon="🕸️")
        return f"Критическая ошибка веб-поиска: {e}", False


# --- Функция стриминга ответа ИИ ---

def stream_ai_response(model_id: str, chat_history: List[Dict[str, str]]) -> Generator[Optional[str], None, None]:
    """Отправляет запрос к API и возвращает генератор для стриминга ответа."""
    if not isinstance(chat_history, list) or not chat_history:
        logger.error("Неверный формат истории чата для стриминга.")
        yield None # Сигнал об ошибке
        return

    payload = {
        "model": model_id,
        "messages": chat_history,
        "stream": True
        # Можно добавить другие параметры: temperature, max_tokens и т.д.
        # "temperature": 0.7,
        # "max_tokens": 1024,
    }
    stream_successful: bool = False
    response = None # Инициализируем переменную response

    try:
        logger.info(f"Запрос стриминга к модели: {model_id}")
        response = requests.post(
            OPENROUTER_API_URL,
            headers=HEADERS,
            json=payload,
            stream=True,
            timeout=(REQUEST_TIMEOUT, STREAM_TIMEOUT) # Таймаут на подключение и чтение
        )
        response.raise_for_status() # Проверяем HTTP статус (4xx, 5xx)
        logger.info("Стриминг начат успешно.")

        # Обрабатываем поток ответа
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    try:
                        json_data_str = decoded_line[len("data: "):].strip()
                        if json_data_str == "[DONE]":
                            logger.info("Стриминг завершен сигналом [DONE].")
                            break # Нормальное завершение стрима
                        if json_data_str:
                            chunk = json.loads(json_data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            delta_content = delta.get("content") # Может быть None
                            if delta_content: # Отправляем только если есть контент
                                stream_successful = True
                                yield delta_content
                    except json.JSONDecodeError:
                        logger.warning(f"Ошибка декодирования JSON чанка: '{json_data_str}'")
                        continue # Пропускаем поврежденный чанк
                    except Exception as e:
                        logger.error(f"Ошибка обработки чанка стрима: {e}", exc_info=True)
                        continue # Продолжаем обработку следующих чанков

        # Проверка, был ли хоть какой-то контент получен
        if not stream_successful:
            logger.warning("Стрим завершился, но не было получено ни одного чанка с контентом.")
            # Не возвращаем None здесь, т.к. это не ошибка сети/API, а пустой ответ

    except requests.exceptions.Timeout as e:
        logger.error(f"Ошибка стриминга: Таймаут ({STREAM_TIMEOUT}s). {e}")
        yield None # Сигнал об ошибке
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети или API во время стриминга: {e}")
        # Попытка прочитать тело ответа для диагностики, если возможно
        error_details = "Нет деталей ответа."
        if response is not None:
            try: error_details = response.text[:500] # Читаем начало ответа
            except Exception: pass # Если прочитать не удалось
        logger.error(f"  Детали ответа (если есть): {error_details}")
        yield None # Сигнал об ошибке
    except Exception as e:
        logger.error(f"Неизвестная ошибка во время стриминга: {e}", exc_info=True)
        yield None # Сигнал об ошибке
    finally:
        # Убедимся, что соединение закрыто, если оно было открыто
        if response is not None:
            try: response.close(); logger.debug("Соединение стриминга закрыто.")
            except Exception: pass


# --- Инициализация состояния Streamlit ---
if "all_chats" not in st.session_state or "active_chat" not in st.session_state:
    logger.info("Первичная инициализация состояния сессии (чаты).")
    # Загружаем чаты и активный чат
    st.session_state.all_chats, st.session_state.active_chat = load_all_chats()
else:
    logger.debug("Состояние сессии (чаты) уже инициализировано.")

# Инициализация режима, если он отсутствует
if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = DEFAULT_MODE
    logger.info(f"Инициализация режима по умолчанию: {DEFAULT_MODE}")

# Инициализация состояния веб-поиска (если load_all_chats не установил)
if "web_search_enabled" not in st.session_state:
     st.session_state.web_search_enabled = False # Безопасное значение по умолчанию
     logger.warning("web_search_enabled не был установлен при загрузке, установлен в False.")


# --- Проверка и корректировка активного чата ---
# Эта проверка важна после любых операций, которые могли изменить all_chats
if not isinstance(st.session_state.get("all_chats"), dict):
     logger.error("Критическая ошибка: st.session_state.all_chats не является словарем. Сброс.")
     st.session_state.all_chats, st.session_state.active_chat = load_all_chats() # Попытка перезагрузить

active_chat_name = st.session_state.get("active_chat")
all_chats_keys = list(st.session_state.all_chats.keys())

if active_chat_name not in all_chats_keys:
    logger.warning(f"Активный чат '{active_chat_name}' не найден в текущем списке чатов {all_chats_keys}.")
    if all_chats_keys:
        st.session_state.active_chat = all_chats_keys[0]
        logger.info(f"Установлен новый активный чат: '{st.session_state.active_chat}'")
    else:
        # Если вообще нет чатов, создаем новый
        new_name = generate_new_chat_name([])
        st.session_state.all_chats = {new_name: []}
        st.session_state.active_chat = new_name
        logger.info(f"Чатов не было, создан и активирован новый чат: '{new_name}'")
        # Сохраняем сразу после создания первого чата
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
    # Перезапускаем скрипт, чтобы все элементы UI обновились с правильным активным чатом
    st.rerun()

# --- Сайдбар ---
with st.sidebar:
    st.markdown("## 💬 Управление чатами")
    chat_names = list(st.session_state.all_chats.keys())

    # Выбор активного чата
    try:
        # Находим индекс текущего активного чата для st.radio
        active_chat_index = chat_names.index(st.session_state.active_chat)
    except ValueError:
        # Если активный чат (по какой-то причине) не в списке, выбираем первый
        logger.warning(f"Активный чат '{st.session_state.active_chat}' не найден в списке ключей при отрисовке сайдбара. Выбран первый.")
        active_chat_index = 0
        if chat_names: # Если список не пуст
            st.session_state.active_chat = chat_names[0]
        else:
            # Эта ситуация не должна возникать из-за проверок выше, но на всякий случай
            logger.error("Критическая ошибка: Нет чатов для выбора в сайдбаре.")
            st.error("Ошибка: Нет доступных чатов.")
            st.stop() # Не можем продолжать без чатов

    # Используем st.radio для выбора чата
    selected_chat = st.radio(
        "Выберите чат:",
        options=chat_names,
        index=active_chat_index,
        key="chat_selector", # Ключ для виджета
        label_visibility="collapsed" # Скрываем сам лейбл "Выберите чат:"
    )

    # Если пользователь выбрал другой чат
    if selected_chat is not None and selected_chat != st.session_state.active_chat:
        st.session_state.active_chat = selected_chat
        logger.info(f"Пользователь выбрал чат: {selected_chat}")
        # Сохраняем состояние при смене чата
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
        st.rerun() # Перезапускаем для обновления основного окна чата

    # Кнопки управления чатами
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Новый", key="new_chat_button", help="Создать новый пустой чат"):
            new_name = generate_new_chat_name(chat_names)
            st.session_state.all_chats[new_name] = []
            st.session_state.active_chat = new_name
            logger.info(f"Создан новый чат: {new_name}")
            save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
            st.rerun()
    with col2:
        # Кнопка удаления активна только если есть чаты
        if chat_names and len(chat_names) > 0: # Добавил проверку > 0 для ясности
             # Используем кастомный data-testid для CSS
            if st.button("🗑️ Удалить", key="delete_chat_button", type="secondary", help="Удалить текущий выбранный чат", use_container_width=True):
                chat_to_delete = st.session_state.active_chat
                logger.info(f"Запрос на удаление чата: {chat_to_delete}")

                if chat_to_delete in st.session_state.all_chats:
                    del st.session_state.all_chats[chat_to_delete]
                    logger.info(f"Чат '{chat_to_delete}' удален.")
                    remaining_chats = list(st.session_state.all_chats.keys())

                    if remaining_chats:
                        # Переключаемся на первый оставшийся чат
                        st.session_state.active_chat = remaining_chats[0]
                    else:
                        # Если удалили последний, создаем новый
                        new_name = generate_new_chat_name([])
                        st.session_state.all_chats = {new_name: []}
                        st.session_state.active_chat = new_name
                        logger.info("Удален последний чат, создан новый.")

                    save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
                    st.toast(f"Чат '{chat_to_delete}' удален.", icon="🗑️")
                    st.rerun()
                else:
                    logger.warning(f"Попытка удалить несуществующий чат: {chat_to_delete}")
                    st.toast("Ошибка: Чат для удаления не найден.", icon="❓")

    st.divider()

    # Переключатель веб-поиска
    search_toggled = st.toggle(
        "🌐 Веб-поиск",
        value=st.session_state.web_search_enabled,
        key="web_search_toggle",
        help="Использовать поиск в интернете для более актуальных ответов"
    )
    # Если состояние изменилось
    if search_toggled != st.session_state.web_search_enabled:
        st.session_state.web_search_enabled = search_toggled
        logger.info(f"Состояние веб-поиска изменено на: {search_toggled}")
        # Сохраняем состояние при изменении настройки поиска
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
        # Перезапуск не нужен, изменение применится при следующем запросе

    st.divider()

    # Выбор режима (модели)
    st.markdown("##### 🧠 Режим ИИ")
    mode_options = list(MODES.keys())
    try:
        # Находим индекс текущего режима
        current_mode_index = mode_options.index(st.session_state.selected_mode)
    except ValueError:
        logger.warning(f"Выбранный режим '{st.session_state.selected_mode}' не найден в опциях {mode_options}. Сброс на {DEFAULT_MODE}.")
        st.session_state.selected_mode = DEFAULT_MODE
        current_mode_index = mode_options.index(DEFAULT_MODE) # Находим индекс дефолтного

    selected_mode_radio = st.radio(
        "Выберите модель:",
        options=mode_options,
        index=current_mode_index,
        key="mode_selector",
        label_visibility="collapsed" # Скрываем лейбл
    )

    # Если режим изменился
    if selected_mode_radio is not None and selected_mode_radio != st.session_state.selected_mode:
        st.session_state.selected_mode = selected_mode_radio
        logger.info(f"Пользователь выбрал режим: {selected_mode_radio}")
        # Сохранение состояния не требуется, т.к. режим не хранится в local storage
        # Перезапуск не нужен, режим применится при следующем запросе

# --- Основная область: Чат ---

# Получаем актуальное имя активного чата и ID модели
current_active_chat_name = st.session_state.active_chat
current_mode_name = st.session_state.selected_mode
current_model_id = MODES.get(current_mode_name, MODES[DEFAULT_MODE]) # Берем ID из словаря, с фолбэком на дефолтный

# Заголовок чата показывает имя чата и используемую модель
st.markdown(f"### Чат: {current_active_chat_name} <span style='font-size: 0.7em; color: grey;'>({current_mode_name.strip()})</span>", unsafe_allow_html=True)

# Контейнер для отображения сообщений чата
chat_container = st.container()
with chat_container:
    # Проверяем, существует ли активный чат в состоянии
    if current_active_chat_name in st.session_state.all_chats:
        chat_history = st.session_state.all_chats[current_active_chat_name]
        # Отображаем каждое сообщение
        for i, message in enumerate(chat_history):
            role = message.get("role")
            content = message.get("content")
            avatar = "🧑‍💻" if role == "user" else "✨" # Используем другой эмодзи для ИИ
            if role and content: # Отображаем только валидные сообщения
                # Используем уникальный ключ на основе индекса и роли
                with st.chat_message(role, avatar=avatar):
                    st.markdown(content, unsafe_allow_html=True)
            else:
                logger.warning(f"Пропущено некорректное сообщение в истории чата '{current_active_chat_name}': {message}")
    else:
        # Эта ситуация маловероятна из-за проверок выше, но добавим сообщение
        st.warning(f"Активный чат '{current_active_chat_name}' не найден. Попробуйте выбрать другой чат или создать новый.")
        logger.error(f"Попытка отобразить историю несуществующего чата: {current_active_chat_name}")


# --- Поле ввода пользователя ---
# Используем st.chat_input, он автоматически располагается внизу
prompt = st.chat_input(f"Спросите {current_mode_name.strip()}...")

if prompt:
    # Проверяем, существует ли активный чат ПЕРЕД добавлением сообщения
    if current_active_chat_name in st.session_state.all_chats:
        logger.info(f"Получен новый промпт в чате '{current_active_chat_name}'.")
        # Добавляем сообщение пользователя в историю текущего чата
        user_message: Dict[str, str] = {"role": "user", "content": prompt}
        st.session_state.all_chats[current_active_chat_name].append(user_message)

        # Сохраняем обновленное состояние
        save_all_chats(st.session_state.all_chats, current_active_chat_name, st.session_state.web_search_enabled)

        # Перезапускаем страницу, чтобы отобразить сообщение пользователя и запустить генерацию ответа ИИ
        st.rerun()
    else:
        st.error("Ошибка: Не удалось отправить сообщение, так как текущий чат не найден.", icon="❌")
        logger.error(f"Ошибка добавления сообщения: чат '{current_active_chat_name}' не найден при отправке промпта.")


# --- Логика генерации и стриминга ответа ИИ ---
# Эта часть выполняется ПОСЛЕ перезапуска (st.rerun) из-за нового сообщения пользователя

# Проверяем, существует ли активный чат и есть ли в нем история
if current_active_chat_name in st.session_state.all_chats:
    current_chat_history = st.session_state.all_chats[current_active_chat_name]

    # Генерируем ответ только если последнее сообщение от пользователя
    if current_chat_history and current_chat_history[-1]["role"] == "user":

        last_user_prompt = current_chat_history[-1]["content"]
        logger.info(f"\n--- Начало обработки ответа ИИ для чата '{current_active_chat_name}' ---")
        logger.info(f"Последний промпт: '{last_user_prompt[:100]}...'")
        logger.info(f"Режим ИИ: {current_mode_name} ({current_model_id})")
        logger.info(f"Веб-поиск: {'ВКЛЮЧЕН' if st.session_state.web_search_enabled else 'ВЫКЛЮЧЕН'}")

        # Подготовка контекста для ИИ
        context_for_ai: List[Dict[str, str]] = list(current_chat_history) # Копируем историю
        system_prompt_content: Optional[str] = None
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")

        # --- Этап 1: Веб-поиск (если включен) ---
        if st.session_state.web_search_enabled:
            logger.info(">>> Этап 1: Веб-поиск активирован.")
            search_results_str: str = "Поиск не выполнялся."
            search_performed_successfully: bool = False
            generated_queries: List[str] = []

            # 1.1 Генерация поисковых запросов
            try:
                with st.spinner("Подбираю поисковые запросы... 🤔"):
                    generated_queries = generate_search_queries(last_user_prompt)
            except Exception as e:
                logger.error(f"Ошибка при вызове generate_search_queries: {e}", exc_info=True)
                st.error("Ошибка во время подбора поисковых вопросов.", icon="❓")
                # Продолжаем без сгенерированных запросов, будем использовать исходный

            # Если запросы не сгенерированы, используем исходный промпт пользователя
            queries_to_search = generated_queries if generated_queries else [last_user_prompt]
            if not generated_queries:
                logger.warning("Не удалось сгенерировать поисковые вопросы, будет использован исходный промпт пользователя для поиска.")

            # 1.2 Выполнение поиска
            search_spinner_text = f"Ищу в сети ({len(queries_to_search)} запрос(а))... 🌐"
            try:
                with st.spinner(search_spinner_text):
                    search_results_str, search_performed_successfully = perform_web_search(queries_to_search)

                if search_performed_successfully:
                    logger.info("Веб-поиск завершен успешно с результатами.")
                    # Формируем системный промпт с результатами поиска
                    system_prompt_content = f"""Текущая дата: {current_date}.
Был выполнен веб-поиск по запросу пользователя.
**Твоя задача:** Внимательно изучи представленные ниже результаты веб-поиска и **синтезируй из них единый, связный и исчерпывающий ответ** на исходный запрос пользователя. Отдавай приоритет информации из результатов поиска.
**Важно:** Не цитируй источники напрямую (например, "Источник 1 сказал..."). Не включай URL. Просто используй найденную информацию для формирования своего ответа. Не упоминай сам факт поиска, если это не требуется для ответа по существу.

--- РЕЗУЛЬТАТЫ ВЕБ-ПОИСКА ---
{search_results_str}
--- КОНЕЦ РЕЗУЛЬТАТОВ ---

Теперь, основываясь **преимущественно на этой информации**, ответь на запрос пользователя: "{last_user_prompt}"
"""
                else:
                    logger.warning(f"Веб-поиск не дал релевантных результатов. Причина: '{search_results_str}'")
                    # Формируем системный промпт с уведомлением о неудаче
                    system_prompt_content = f"""Текущая дата: {current_date}.
Веб-поиск был включен, но **не дал полезных результатов** (Возможная причина: {search_results_str}).
**Твоя задача:** Ответь на запрос пользователя, **основываясь исключительно на своих общих знаниях**.
**Важно:** Так как актуальная информация из сети недоступна, **предупреди пользователя**, что твой ответ может быть не самым свежим или полным, особенно если вопрос касается недавних событий или быстро меняющихся тем.

Запрос пользователя: "{last_user_prompt}"
"""

            except Exception as e:
                logger.error(f"Ошибка на этапе выполнения perform_web_search: {e}", exc_info=True)
                st.error("Произошла ошибка во время веб-поиска.", icon="🕸️")
                # Системный промпт на случай полной ошибки поиска
                system_prompt_content = f"""Текущая дата: {current_date}.
Произошла **ошибка** при попытке выполнить веб-поиск.
**Твоя задача:** Ответь на запрос пользователя, **основываясь исключительно на своих общих знаниях**.
**Важно:** Предупреди пользователя, что из-за технической ошибки веб-поиск не удался, и твой ответ может быть неактуальным.

Запрос пользователя: "{last_user_prompt}"
"""
        else: # Веб-поиск выключен
            logger.info(">>> Этап 1: Веб-поиск выключен.")
            system_prompt_content = f"Текущая дата: {current_date}. Веб-поиск ВЫКЛЮЧЕН. Отвечай на запрос пользователя, основываясь только на своих общих знаниях."

        # --- Этап 2: Добавление системного промпта (если он есть) ---
        if system_prompt_content:
            # Вставляем системный промпт перед последним сообщением пользователя
            # Это распространенная практика для некоторых моделей
            context_for_ai.insert(-1, {"role": "system", "content": system_prompt_content})
            logger.info("Системный промпт добавлен в контекст.")
            # logger.debug(f"System prompt content: {system_prompt_content[:200]}...") # Логируем начало промпта для отладки

        # --- Этап 3: Стриминг ответа ИИ ---
        logger.info(">>> Этап 2: Запрос и стриминг ответа ИИ.")
        final_response_to_save: Optional[str] = None
        ai_response_error: bool = False
        full_response_chunks: List[str] = []

        try:
            # Используем st.chat_message для создания блока ответа ассистента
            with st.chat_message("assistant", avatar="✨"):
                # Создаем placeholder с помощью st.empty() внутри блока сообщения
                message_placeholder = st.empty()
                # Показываем индикатор загрузки внутри placeholder
                message_placeholder.markdown("Генерирую ответ... ⏳")

                # Получаем генератор ответа от API
                response_generator = stream_ai_response(current_model_id, context_for_ai)

                # Итерируем по чанкам ответа
                for chunk in response_generator:
                    if chunk is None:
                        # Генератор вернул None, что сигнализирует об ошибке
                        logger.error("Генератор стриминга вернул ошибку (None).")
                        ai_response_error = True
                        message_placeholder.error("Ошибка получения ответа от ИИ!", icon="🔥")
                        # Прерываем цикл, так как стриминг не удался
                        break
                    if chunk:
                        # Добавляем чанк к списку
                        full_response_chunks.append(chunk)
                        # Обновляем содержимое placeholder'а текущим накопленным текстом + индикатор
                        # Используем unsafe_allow_html=True для корректного отображения markdown во время стрима
                        message_placeholder.markdown("".join(full_response_chunks) + " ▌", unsafe_allow_html=True)

                # После завершения цикла стриминга (если не было ошибки)
                if not ai_response_error:
                    final_response_to_save = "".join(full_response_chunks).strip()
                    if final_response_to_save:
                        # Отображаем финальный ответ в placeholder'е без индикатора
                        message_placeholder.markdown(final_response_to_save, unsafe_allow_html=True)
                        logger.info("Ответ ИИ успешно получен и отображен.")
                    else:
                        # Стрим завершился, но ответ пустой
                        logger.warning("Ответ от ИИ пуст после успешного стриминга.")
                        message_placeholder.warning("ИИ не предоставил содержательный ответ.", icon="🤷")
                        final_response_to_save = None # Не сохраняем пустой ответ
                # Если была ошибка (ai_response_error == True), сообщение об ошибке уже отображено в placeholder'е

        except Exception as e:
             # Ловим ошибки, которые могут возникнуть вне генератора (например, при создании st.chat_message)
             logger.error(f"Неожиданная ошибка при обработке и отображении ответа ИИ: {e}", exc_info=True)
             # Показываем ошибку в основном потоке, так как placeholder может быть недоступен
             st.error(f"Произошла ошибка при отображении ответа ИИ: {e}", icon="💥")
             final_response_to_save = None # Не сохраняем ответ, если была ошибка отображения
             ai_response_error = True

        # --- Этап 4: Сохранение ответа ИИ (если он успешен и не пуст) ---
        if final_response_to_save and not ai_response_error:
            logger.info(">>> Этап 3: Сохранение ответа ИИ в историю.")
            try:
                # Проверяем, что активный чат все еще существует (на всякий случай)
                if current_active_chat_name in st.session_state.all_chats:
                     # Формируем сообщение ассистента
                     assistant_message: Dict[str, str] = {"role": "assistant", "content": final_response_to_save}
                     # Добавляем его в историю
                     st.session_state.all_chats[current_active_chat_name].append(assistant_message)
                     # Сохраняем все чаты в LocalStorage
                     save_all_chats(st.session_state.all_chats, current_active_chat_name, st.session_state.web_search_enabled)
                     logger.info("Ответ ассистента успешно добавлен в историю и сохранен.")
                     # --- RERUN НЕ НУЖЕН ---
                     # Ответ уже отображен на экране с помощью st.empty()
                else:
                     logger.error(f"Ошибка сохранения ответа: чат '{current_active_chat_name}' не найден во время сохранения.")
                     st.error("Ошибка: не удалось сохранить ответ ИИ, чат не найден.", icon="❌")
            except Exception as e:
                 logger.error(f"Ошибка при сохранении ответа ИИ в session_state или LocalStorage: {e}", exc_info=True)
                 st.error(f"Ошибка сохранения ответа ИИ: {e}", icon="💾")
        elif ai_response_error:
            logger.warning("Ответ ИИ не будет сохранен из-за ошибки во время генерации/стриминга.")
        elif not final_response_to_save:
             logger.warning("Пустой ответ ИИ не будет сохранен.")


        # Логирование завершения обработки
        logger.info(f"--- Обработка ответа ИИ для чата '{current_active_chat_name}' завершена ---")

# Добавляем небольшой отступ снизу, чтобы поле ввода не перекрывало последний ответ
st.markdown("<div style='height: 5rem;'></div>", unsafe_allow_html=True)
