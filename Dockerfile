FROM python:3.12.10-slim

WORKDIR /app

COPY . .

RUN pip install uv
RUN uv sync

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]