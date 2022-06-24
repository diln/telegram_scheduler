FROM python:3.10

ENV TZ=Europe/Moscow

WORKDIR /opt/scheduler_bot

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY scheduler.py FreeMonospaced.ttf logging.ini creds.json ./

ENTRYPOINT ["python", "scheduler.py"]