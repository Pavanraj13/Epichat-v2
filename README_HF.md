---
title: EpiChat Backend
emoji: 🧠
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
---

# EpiChat Backend API

FastAPI backend for the EpiChat seizure detection system.

- **EEG Analysis:** PyTorch-based seizure classification
- **AI Chatbot:** Gemini-powered clinical assistant  
- **Database:** Neon PostgreSQL

Set the following secrets in your Space settings:
- `GEMINI_API_KEY`
- `DATABASE_URL`
- `ALLOWED_ORIGINS`
