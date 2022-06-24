# Scheduler telegram bot
The bot takes data from Google spreadsheet and adds rows.

## Getting Started
* Create `creds.json` with Google credentials
* Build image:
```
docker build . -t telegram_scheduler
```
* Run container:
```
docker run -d --restart unless-stopped \
--name telegram_scheduler_bot \
-e bot_token={TOKEN} \
-e sheet_id={SHEET_ID} \
telegram_scheduler
```
