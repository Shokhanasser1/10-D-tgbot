# Telegram Mini App Storefront

E-commerce Telegram Mini App (Spec 1 of 3 — see `docs/superpowers/specs/`). Cosmetics launch niche, architected for multi-niche expansion.

Full setup instructions land in Phase 11 (Docker Compose wiring). For now:

**Backend**
```
cd backend
python -m venv .venv
./.venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

**Frontend**
```
cd frontend
npm install
cp .env.example .env
npm run dev
```
