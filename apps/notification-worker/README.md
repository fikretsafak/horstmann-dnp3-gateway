# Notification Worker

Dedicated background worker for:

- SMTP email notifications
- SMS provider notifications
- Retry/backoff logic

## Run

1. `cd apps/notification-worker`
2. `py -3.10 -m pip install -r requirements.txt`
3. `py -3.10 -m notification_service.main`
