# ChildSafe Assistant

## Backend Setup
```bash
cd backend
uv sync
uv run python app/cli.py download --report all
uv run python app/cli.py chunk-and-post
uv run uvicorn app.api:app --reload
```

## Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

## Deployment with Fabric
```bash
cd deploy
fab deploy
```
