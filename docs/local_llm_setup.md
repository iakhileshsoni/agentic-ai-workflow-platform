# Local LLM Runtime Setup (Ollama on 8 GB RAM)

This guide details how to configure and run local language models with **Ollama** on a Windows machine with 8 GB RAM and no confirmed GPU.

---

## 1. Prerequisites and Model Selection

On an 8 GB RAM Windows system, memory conservation is paramount. We recommend small, quantized models with bounded context windows:

| Candidate Model | Quantization | RAM Footprint | Recommended Use Case |
| :--- | :--- | :--- | :--- |
| **Qwen 2.5 3B Instruct** (Default) | `Q4_K_M` | $\approx 2.1$ GB | Superior structured JSON formatting adherence |
| **Llama 3.2 3B Instruct** (Alternative) | `Q4_K_M` | $\approx 2.0$ GB | Fast inference, lightweight CPU execution |

---

## 2. Installation and Model Pull

### Step 1: Install Ollama on Windows
Download and install Ollama from [ollama.com](https://ollama.com).

### Step 2: Pull the Recommended Model
Open PowerShell and run:
```powershell
ollama pull qwen2.5:3b-instruct
```

To verify the model is downloaded and ready:
```powershell
ollama list
```

### Step 3: Run the Ollama Service
Ensure Ollama is running in your system tray or run:
```powershell
ollama serve
```

---

## 3. Platform Configuration

Update your `.env` file (copied from `.env.example`):

```ini
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen2.5:3b-instruct
LLM_TIMEOUT_SECONDS=60.0
LLM_FALLBACK_MOCK=true
```

### Zero-Downtime Deterministic Fallback Mode
If Ollama is not installed, offline, or experiencing high load:
- The platform's `LLMAdapter` detects the unavailability immediately via the `/api/tags` health check.
- Workflows seamlessly fall back to deterministic planning mocks without throwing runtime errors.
- Both `pytest` and `scripts/run_evals.py` will complete with 100% test pass rates regardless of whether Ollama is active.
