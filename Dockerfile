FROM python:3.12-slim
WORKDIR /project
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY sql ./sql
COPY tests ./tests
CMD ["python", "-m", "src.pipeline"]

