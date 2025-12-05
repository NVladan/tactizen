# Logs Directory

This directory contains application logs. Log files are automatically created and managed by the logging system.

## Log Files

- **app.log** - General application logs (all levels)
- **error.log** - Error-level logs only (ERROR and CRITICAL)
- **transactions.log** - Financial transaction logs
- **security.log** - Security-related events (login attempts, suspicious activity)

## Rotation

- **app.log** and **error.log**: Rotate when they reach 10MB (keeps 10 backups)
- **transactions.log** and **security.log**: Rotate daily at midnight (keeps 90/365 days respectively)

## Note

These files are excluded from git via .gitignore. Never commit logs to version control as they may contain sensitive information.
