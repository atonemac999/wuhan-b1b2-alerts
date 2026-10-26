# Wuhan B1/B2 observation alerts

Personal monitor of the public hourly B1/B2 regular-interview summary at
https://visabida.com/trend. Checks every 15 minutes using GitHub Actions and
sends changes in the earliest observed date or available-date count to Bark.
This is an hourly third-party observation summary, not live official inventory.
No visa credentials are collected. Notifications do not reserve appointments.

Set the repository Actions secret `VISA_BARK_ENDPOINT` to your Bark endpoint.
Never commit this value. Dispatch the workflow with mode `status` for a test.
The date/count signature is cached to suppress unchanged notifications.
An unreadable or stale (>3 hours) summary triggers one outage notification;
recovery triggers one notification. Missing data is never treated as no slots.

There is no cutoff date configured: all future observed dates qualify.
GitHub scheduling can be delayed. Public repositories with no activity for
60 days may have scheduled workflows automatically disabled by GitHub.
No paid resources or subscription are required for this public-repository setup.
