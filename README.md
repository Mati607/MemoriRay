## 🧠 MEMORIRAY – Minimal Mental-Health Companion

<div align="center">

![MemoriRay](https://img.shields.io/badge/MemoriRay-Mental--Health-blueviolet?style=for-the-badge&logo=google)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Gemini](https://img.shields.io/badge/Google%20Gemini-LLM-4285F4?style=for-the-badge&logo=google&logoColor=white)
![Poetry](https://img.shields.io/badge/Poetry-Dependency%20Mgmt-60A5FA?style=for-the-badge&logo=python)

**A minimal mental-health chat app with Streamlit + FastAPI, powered by Google's Gemini via BAML.**

</div>

---

## 🌟 Overview

MemoriRay is a **minimal but extensible mental-health assistant** that lets users chat with an LLM-backed therapist-style agent while exploring **positive memories** (images/media) and generating **clinical-style summaries**.

- 💬 **Conversational UI** built with Streamlit
- ⚙️ **FastAPI backend** orchestrating Gemini via BAML flows
- 🧩 **BAML-powered tools** for memory selection, sentiment analysis, reporting, and more
- 🖼️ **Memory gallery** backed by local assets in `memories/`
- 🧪 Includes a more complete backend (`mindsync-backend/`) for advanced persistence and API use

---

## 🏗️ High-Level Architecture

```text
┌────────────────────┐        ┌──────────────────────┐        ┌─────────────────────────┐
│  Streamlit Frontend│        │   FastAPI Backend    │        │       LLM + Tools       │
│      (app.py)      │  HTTP  │      (bot.py)        │  BAML  │  (Gemini via google-    │
│                    │ ─────▶ │                      │ ─────▶ │  genai + baml_client)   │
└────────────────────┘        └──────────────────────┘        └─────────────────────────┘
          │                               │
          │                               ▼
          │                     ┌───────────────────┐
          │                     │  memories/        │
          │                     │  (image assets)   │
          │                     └───────────────────┘
          │
          ▼
   Local chat history
    (`chat_history.json`)
```

For a **more feature-complete backend** (multi-user support, database, vector store, etc.), see `mindsync-backend/`.

---

## 🛠️ Tech Stack

### 🧩 Core
- **Python 3.10+**
- **Poetry** for dependency and environment management

### 💻 Frontend
- **Streamlit** (`app.py`) for the chat UI and memory visualization

### ⚙️ Backend
- **FastAPI** (`bot.py`) for HTTP APIs consumed by the Streamlit app
- **BAML** (`baml_src/` + `baml_client/`) to define and call LLM workflows
- **google-genai / Gemini** as the LLM engine

### 🧠 Data & Assets
- Local **image memories** under `memories/`
- Local **chat history** persisted in `chat_history.json`

---

## 🚀 Quick Start

### ✅ Prerequisites

- **Python** 3.10+
- **Poetry**
- **Google Gemini API key**

### 📦 Install dependencies

```bash
poetry install
poetry env activate
```

### 🔐 Environment

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your_google_api_key
```

### 🧱 (Optional) Generate BAML client

Only needed when you change `.baml` files in `baml_src/`:

```bash
baml-cli generate
```

### 🧬 Run the backend (FastAPI)

```bash
poetry run python bot.py
```

### 🎨 Run the frontend (Streamlit)

```bash
poetry run streamlit run app.py
```

Then open the app at `http://localhost:8501` and start chatting with the assistant.

---

## 🔄 End-to-End Flow

1. **Generate BAML client code** (if you modified `.baml` files):

   ```bash
   baml-cli generate
   ```

2. **Start the backend** (FastAPI) in **Terminal 1**:

   ```bash
   poetry run python bot.py
   ```

3. **Start the frontend** (Streamlit) in **Terminal 2**:

   ```bash
   poetry run streamlit run app.py
   ```

4. **Use the app** by visiting `http://localhost:8501` in your browser and chatting with the assistant. The app will:
   - Send your messages to the FastAPI backend
   - Call BAML-defined flows to interact with Gemini
   - Surface relevant memories and summaries

---

## 📁 Project Structure

```text
MemoriRay/
├── app.py                     # 🧩 Streamlit frontend (chat UI + memory display)
├── bot.py                     # ⚙️ FastAPI backend that calls BAML + Gemini
├── baml_src/                  # 📜 BAML definitions (agents, tools, flows)
│   ├── therapist_bot.baml     #   LLM therapist-style agent
│   ├── select_memory.baml     #   Memory selection logic
│   ├── image_description.baml #   Vision/image captioning flows
│   ├── generate_report.baml   #   Clinical-style summaries
│   ├── sentiment.baml         #   Sentiment analysis
│   └── trusted_contact.baml   #   Trusted contact handling
├── baml_client/               # 🧱 Generated BAML Python client (from `baml-cli generate`)
├── memories/                  # 🖼️ Sample image memories
├── chat_history.json          # 💾 Local chat history log
├── i2c.py                     # 🧰 Image-to-JSON helper for memory ingestion APIs
├── mindsync-backend/          # 🧠 Full backend service (see its README)
├── pyproject.toml             # 📦 Poetry configuration
├── poetry.lock                # 🔒 Locked dependency versions
└── README.md                  # 📖 This file
```

---

## 🧠 MemoriRay vs. MindSync Backend

- **MemoriRay root app (this README)**:
  - Minimal, local-first experiment
  - Great for demos, prototyping, and exploring BAML + Gemini

- **`mindsync-backend/`**:
  - More complete backend with API routes under `src/api/`
  - Services under `src/services/` for conversations, memory, database, etc.
  - Models and schemas under `src/models/`
  - See `mindsync-backend/README.md` for setup and usage details

---

## 🧪 Development Tips

- When you modify any `.baml` files in `baml_src/`, re-run:

  ```bash
  baml-cli generate
  ```

- Restart the **backend** after regenerating the BAML client to pick up changes.
- Keep an eye on `chat_history.json` if you are debugging conversation state.

---

## 🤝 Contributing

This project is currently a lightweight demo/prototype. Feel free to:

- Adapt it to your own mental-health or coaching use-cases
- Extend the BAML flows to add safety checks, journaling, or task planning
- Integrate the `mindsync-backend/` into a larger system

---

## ⚠️ Disclaimer

MemoriRay is **not a replacement for professional mental health care**.

It is a **technical demo** for exploring LLM-based mental-health interactions. If you or someone you know is in crisis, please seek help from qualified professionals or local emergency services.

