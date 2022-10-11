# lab-mail-forward
Homelab internal email forwarder.

This is something I've created as a side project for use in my own homelab. It's very overengineered, probably poorly coded and might have other problems with it that I have not considered but it works for my use case.

The SMTP server, mail processing and interface for receiving notifications/and listing/viewing emails are separate, which means you can replace the current Discord backend for interfacing with the "mail server" for something else (IRC, Slack, Matrix, I don't care) if you'd want for some reason. It might also be possible to have multiple such backends at once with slight tweaks (webui I guess?).

## Deployment
```bash
# Edit .env.example and save it as .env
docker compose up --build -d
```
