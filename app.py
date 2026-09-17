import streamlit as st
from google import genai
from google.genai import types

# -------------------------------------------------------------
# 1. PAGE SETUP (ChatGPT Style Dark Palette)
# -------------------------------------------------------------
st.set_page_config(
    page_title="MY AI",
    page_icon="🐺",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom styling for ChatGPT look & feel
st.markdown("""
<style>
    /* Dark ChatGPT background */
    .stApp {
        background-color: #212121;
        color: #ECECEC;
    }
    /* Style Chat Input Box */
    .stChatInputContainer {
        padding-bottom: 20px;
    }
    /* Clean sidebar */
    section[data-testid="stSidebar"] {
        background-color: #171717;
        border-right: 1px solid #303030;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. SIDEBAR: THE 5-KEY ENGINE & CONTROLS
# -------------------------------------------------------------
with st.sidebar:
    st.title("🐺 MY AI Settings")
    
    st.subheader("🔑 API Key Pool (5 Projects)")
    key1 = st.text_input("Key 1 (Primary)", type="password")
    key2 = st.text_input("Key 2 (Backup)", type="password")
    key3 = st.text_input("Key 3 (Backup)", type="password")
    key4 = st.text_input("Key 4 (Backup)", type="password")
    key5 = st.text_input("Key 5 (Backup)", type="password")
    
    # Pool list (filtering out empty boxes)
    api_pool = [k for k in [key1, key2, key3, key4, key5] if k.strip()]
    
    # Key Mode: Auto-Rotate or Manual Force
    st.subheader("⚙️ Key Mode")
    key_options = ["🔄 Auto-Rotate (Recommended)"] + [f"📌 Force Key {i+1}" for i in range(len(api_pool))]
    selected_mode = st.selectbox("Key Handling:", key_options if api_pool else ["No Keys Added"])

    st.divider()

    # Safety Controls
    st.subheader("🛡️ Safety Controls")
    unrestricted_mode = st.checkbox("🔥 Unrestricted Writing (BLOCK_NONE)", value=True)
    
    st.divider()

    # Grounded Creative Slider
    st.subheader("🎨 Creative Tone")
    temperature = st.slider("Grounded Realism vs Imagination", 0.0, 1.0, 0.6, step=0.05)
    if temperature <= 0.4:
        st.caption("🔍 Strict, bleak noir. Zero unearned miracles.")
    elif temperature <= 0.7:
        st.caption("🐺 Fabletown Sweet Spot: Grounded physics, mythic weight.")
    else:
        st.caption("✨ Unhinged, highly surreal imagination.")

# -------------------------------------------------------------
# 3. CONVERSATION STATE
# -------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "active_key_index" not in st.session_state:
    st.session_state.active_key_index = 0

# Display conversation on screen
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -------------------------------------------------------------
# 4. CHAT INPUT & EXECUTION
# -------------------------------------------------------------
if not api_pool:
    st.info("👈 Open the sidebar (tap > top left) and paste at least Key 1 to begin!", icon="🔑")
    st.stop()

if prompt := st.chat_input("Message MY AI..."):
    # Append & display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Configure Safety Settings
    safety_settings = []
    if unrestricted_mode:
        categories = [
            types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        ]
        for cat in categories:
            safety_settings.append(
                types.SafetySetting(
                    category=cat,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                )
            )

    # Execution Engine with Auto-Failover
    response_text = None
    attempts = 0
    max_attempts = len(api_pool)

    # Determine which key to start with
    if "Force Key" in selected_mode:
        target_index = int(selected_mode.split("Key ")[1]) - 1
        keys_to_try = [api_pool[target_index]]
    else:
        # Round-robin starting from current active key
        keys_to_try = api_pool[st.session_state.active_key_index:] + api_pool[:st.session_state.active_key_index]

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            for current_key in keys_to_try:
                try:
                    client = genai.Client(api_key=current_key)
                    config = types.GenerateContentConfig(
                        temperature=temperature,
                        safety_settings=safety_settings if unrestricted_mode else None,
                        system_instruction="You are MY AI: a grounded, gritty storyteller following strict physical reality, consequences, and deep continuity."
                    )
                    
                    # Generate response using 2.5-flash
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt,
                        config=config
                    )
                    response_text = response.text
                    # Save current successful key index
                    st.session_state.active_key_index = api_pool.index(current_key)
                    break
                except Exception as e:
                    # If quota exhausted (429), try next key silently
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        continue
                    else:
                        st.error(f"Error: {e}")
                        break

            if response_text:
                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
            elif not response_text:
                st.error("All available API keys hit their rate limits. Please try again later or add more keys.")
