# lab-mail-forward
Homelab internal email forwarder.

This is something I've created as a side project for use in my own homelab. It's very overengineered, probably poorly coded and might have other problems with it that I have not considered but it works for my use case.

The SMTP server, mail processing and interface for receiving notifications/and listing/viewing emails are separate, which means you can replace the current Discord backend for interfacing with the "mail server" for something else (IRC, Slack, Matrix, I don't care) if you'd want for some reason. It might also be possible to have multiple such backends at once with slight tweaks (webui I guess?).

## Deployment
```bash
# Edit .env.example and save it as .env
docker compose up --build -d
```

## Discord interface
After deployment you can interface with the project through the discord bot that authenticates using the token passed in `.env`.

The commands are as follows:  
`>alias add email@here.com` - Add an email address to your discord account  
`>alias remove email@here.com` - Remove an email address from your discord account  
`>alias list` - List your currently active addresses  

`>email view <id>` - View the email with ID of `<id>` (NOTE: you should not be able to read someone elses emails)  
`>email list [page]` - List emails from newest to oldest

If an email arrives to the SMTP server to an email address that is attached to a discord account, the user will be notified with the following message:
```
📨 New email from sender@example.com on recipient@homelab.local!
Subject: some subject
View with >email view <id here>
```
