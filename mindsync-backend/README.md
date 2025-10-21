# MindSync Backend

AI-powered mental health companion with positive memory recall.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run database migrations:
```bash
alembic upgrade head
```

4. Start the server:
```bash
uvicorn src.main:app --reload
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Docker Deployment

```bash
docker-compose up -d
```

## Project Structure

- `src/api/` - API routes and endpoints
- `src/services/` - Business logic services
- `src/models/` - Data models and schemas
- `src/core/` - Core functionality (database, config)
- `tests/` - Unit and integration tests
