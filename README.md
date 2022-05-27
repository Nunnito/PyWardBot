# PyWardBot
> Telegram forwarder written in Python

PyWardBot is an open source Telegram message forwarder powered by
[Pyrogram](https://github.com/pyrogram/pyrogram)

![img_1](https://i.imgur.com/F12yXjv.gif)

## Features
- Set by Telegram ID or by username
- Telegram protected content bypass
- Message reply detection
- Message edit detection
- Messaged delete detection
- Enable and disable options
- Replace words
- Block words
- Add origin chats
- Get chat info
- Two sending mode: **copy message or forward message**

## Use cases
- Forward messages from one chat to another
- Download protected media files
- Backup messages
- Send messages to multiple chats

## Installation and configuration

### Installation
First, you will need to have
[Python](https://realpython.com/installing-python/#how-to-install-python-on-windows)
and
[^1] [Git](https://github.com/git-guides/install-git) installed on your system.
Also you will need to create a new
[Telegram bot](https://www.siteguarding.com/en/how-to-get-telegram-bot-api-token)
and get the bot token.

After installing Python and Git, and creating a bot, open a terminal and do the following:
```bash
# Clone repository
git clone https://github.com/nunnito/PyWardBot.git

# Change directory to the cloned repository
cd PyWardBot

# Install dependencies
pip install -r requirements.txt

# Run the bot
python3 app/main.py
```

### Configuration
After running the bot for the first time, you will get the following output:
```
25-05-2022 18:00:00 - config:23 - ERROR: bot.json not found
25-05-2022 18:00:00 - config:24 - WARNING: bot.json has been created with default values. Please edit it with your own api_id and api_hash values. You can find them on https://my.telegram.org/apps
```
You will need to edit the `bot.json` file with your own `api_id` and `api_hash` values in order to run the bot.

Get those values from
[this tutorial](https://arshmaan.com/how-to-get-telegram-api-id-and-hash-id/)
or just go to [My Telegram Org](https://my.telegram.org/apps) and create a new app.

Once you have these values go to the `PyWardBot/app/config/` folder and open the `bot.json` file.

You will see a content like this:
```json
{
    "api_id": 1234567,
    "api_hash": "0123456789abcdef0123456789abcdef",
    "admins": []
}
```
Replace `1234567` and `0123456789abcdef0123456789abcdef` with your own `api_id` and `api_hash` values.

Then run the bot again:
```bash
python3 app/main.py
```

You will be prompted to enter your phone number:
```bash
25-05-2022 18:00:00 - main:839 - INFO: Log-in with your phone number
Welcome to Pyrogram (version 1.4.8)
Pyrogram is free software and comes with ABSOLUTELY NO WARRANTY. Licensed
under the terms of the GNU Lesser General Public License v3 or later (LGPLv3+).

Enter phone number or bot token:
```

Remember to enter your phone number in the international format (e.g. +11234567890).

After entering your phone number, a code will be sent to your Telegram account. Enter the code and press enter.

Then you will be prompted to enter your bot token:
```bash
25-05-2022 18:00:0 - main:843 - INFO: Log-in with you bot token
Welcome to Pyrogram (version 1.4.8)
Pyrogram is free software and comes with ABSOLUTELY NO WARRANTY. Licensed
under the terms of the GNU Lesser General Public License v3 or later (LGPLv3+).

Enter phone number or bot token:
```

After entering your bot token, and if everything went well, you will see the following output:
```bash
25-05-2022 20:15:08 - main:845 - INFO: Bot started
25-05-2022 20:20:08 - main:846 - INFO: Bot username: @YOURBOTUSERNAME
```

That's it! Now you can start the bot and set it up!


## FAQ
### Is necessary to install Git?
No, you can download the source code as a zip file from [here](https://github.com/nunnito/PyWardBot/archive/refs/heads/master.zip). Then unzip it and follow the installation [instructions](#installation)

### How to add a new admin?
By default, the bot is configured to run only for yourself. If you want to add a new admin, you can do it by adding the new Telegram ID to the `admins` array in the `bot.json` file.

### What are the different modes of sending messages?
There are two modes of sending messages:

- **copy message**: the bot will copy the message to the destination chat.
- **forward message**: the bot will forward the message to the destination chat.


### How to send only outgoing or only incoming messages?
For this you need to open the `forwarding.json` file and modify the `outgoing` and `incoming` properties. By default, the bot will forward all messages.
