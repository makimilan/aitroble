import streamlit as st
import requests
from duckduckgo_search import DDGS

# ======= СТИЛИЗАЦИЯ СТРАНИЦЫ (ТЁМНАЯ ТЕМА) =======
st.markdown(
    """
    <style>
    /* Общие настройки фона и текста */
    body {
        background-color: #1e1e1e;
        color: #ffffff;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }
    /* Центрирование и ограничение ширины основного контейнера */
    .main > div {
        max-width: 800px;
        margin: 0 auto;
    }
    /* Стили для боковой панели (sidebar) */
    [data-testid="stSidebar"] {
        background-color: #232323;
    }
    /* Стили для блоков чата */
    .chat-container {
        padding: 20px;
        margin-bottom: 20px;
        border-radius: 10px;
    }
    .user-message {
        background-color: #2a2a2a;
        padding: 10px;
        border-radius: 10px;
        margin-bottom: 10px;
        text-align: right;
    }
    .ai-message {
        background-color: #3a3a3a;
        padding: 10px;
        border-radius: 10px;
        margin-bottom: 10px;
        text-align: left;
    }
    /* Стилизация элементов ввода и кнопок */
    .stTextArea textarea {
        background-color: #2a2a2a;
        color: #ffffff;
    }
    .stTextArea label {
        color: #ffffff;
    }
    .stButton button {
        background-color: #4a4a4a;
        color: #ffffff;
        border: none;
        border-radius: 5px;
        padding: 0.6rem 1rem;
    }
    .stButton button:hover {
        background-color: #5a5a5a;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ======= ЗАГОЛОВОК ПРИЛОЖЕНИЯ =======
st.title("Образовательный AI помощник")
st.markdown(
    "Добро пожаловать! Этот чат-помощник поможет вам разобраться в школьных темах "
    "с подробными и доступными объяснениями."
)

# ======= НАСТРОЙКИ В БОКОВОЙ ПАНЕЛИ =======
st.sidebar.header("Настройки модели")

# Маппинг названий для реального API
model_mapping = {
    "v3": "deepseek-chat-v3-0324:free",
    "r1": "deepseek-r1:free"
}

model_key = st.sidebar.selectbox("Выберите модель", ["v3", "r1"])
model_choice = model_mapping[model_key]

enable_web_search = st.sidebar.checkbox("Включить автоматический веб поиск", value=False)

# ======= ПАРАМЕТРЫ API =======
API_KEY = "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"
API_URL = "https://api.openrouter.ai/v1/chat/completions"  # Уточните реальный URL при необходимости

# ======= ИНИЦИАЛИЗАЦИЯ ИСТОРИИ ДИАЛОГА =======
if 'conversation' not in st.session_state:
    st.session_state.conversation = []

# ======= ФУНКЦИИ =======
def web_search(query):
    """
    Выполняет веб-поиск через DuckDuckGo с использованием DDGS и возвращает результаты.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        return results
    except Exception as e:
        st.error(f"Ошибка веб-поиска: {e}")
        return None

def call_ai_model(model, conversation):
    """
    Отправляет историю сообщений на API провайдера OpenRouter и возвращает ответ AI.
    Предполагается, что API возвращает JSON с полями 'response' (ответ модели)
    и 'thinking' (описание процесса мышления модели).
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    payload = {
        "model": model,
        "messages": conversation,
        "temperature": 0.7
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            ai_response = data.get("response", "Нет ответа от модели.")
            thinking_process = data.get("thinking", "")
            return ai_response, thinking_process
        else:
            return f"Ошибка API: {response.status_code}", ""
    except Exception as e:
        return f"Ошибка запроса: {e}", ""

# ======= ОТОБРАЖЕНИЕ ИСТОРИИ ЧАТА =======
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

for entry in st.session_state.conversation:
    if entry["role"] == "user":
        st.markdown(
            f'<div class="user-message"><b>Вы:</b> {entry["content"]}</div>',
            unsafe_allow_html=True
        )
    elif entry["role"] == "ai":
        st.markdown(
            f'<div class="ai-message"><b>AI:</b> {entry["content"]}</div>',
            unsafe_allow_html=True
        )
    elif entry["role"] == "system":
        st.markdown(
            f'<div class="ai-message"><i>{entry["content"]}</i></div>',
            unsafe_allow_html=True
        )

st.markdown('</div>', unsafe_allow_html=True)

# ======= ФОРМА ДЛЯ ВВОДА СООБЩЕНИЯ =======
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_area("Ваше сообщение", height=100)
    submit_button = st.form_submit_button(label="Отправить")

if submit_button and user_input:
    # Добавляем сообщение пользователя в историю диалога
    st.session_state.conversation.append({"role": "user", "content": user_input})
    
    # Если включён веб-поиск, выполняем его и добавляем результаты в историю как системное сообщение
    if enable_web_search:
        st.info("Выполняется веб-поиск...")
        search_results = web_search(user_input)
        if search_results:
            # Формируем контекст из результатов
            search_context = "\n".join(
                [f"{item.get('title', 'Без заголовка')}: {item.get('href', '')}" for item in search_results]
            )
            st.session_state.conversation.append({
                "role": "system", 
                "content": f"Результаты веб-поиска:\n{search_context}"
            })
    
    # Вызов AI модели
    with st.spinner("AI обрабатывает запрос..."):
        ai_reply, thinking = call_ai_model(model_choice, st.session_state.conversation)
    
    # Добавляем ответ AI в историю диалога
    st.session_state.conversation.append({"role": "ai", "content": ai_reply})
    
    # Если функция experimental_rerun доступна, выполняем перезапуск приложения
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

# ======= ОТОБРАЖЕНИЕ ПРОЦЕССА МЫШЛЕНИЯ AI (ПРИ НАЛИЧИИ) =======
if "thinking" in locals() and thinking:
    st.markdown("### Процесс мышления AI")
    st.markdown(thinking)
