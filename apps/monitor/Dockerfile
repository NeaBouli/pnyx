FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
RUN groupadd --gid 10001 monitor && useradd --uid 10001 --gid monitor --no-create-home --no-log-init --shell /usr/sbin/nologin monitor
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY monitor.py .
USER monitor:monitor
CMD ["python", "monitor.py"]
