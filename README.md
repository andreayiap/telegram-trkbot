telegram-trkbot
===============

`telegram-trkbot` is a telegram bot which asks you a question with a predefined set of answers at selected times of the day.
As an example, this bot can help you track your mood by asking you how you feel.


## Installation

On Debian/Ubuntu:
```
# apt-get install python python-pip
# pip install python-telegram-bot peewee emoji

$ git clone https://github.com/fg1/telegram-trkbot.git
$ cd telegram-trkbot
$ cp config.py.example config.py
```

Get your [Telegram token using BotFather](https://core.telegram.org/bots#3-how-do-i-create-a-bot) and edit `config.py` accordingly.


## Usage

Launch the bot:
```
$ python trkbot.py
```

In Telegram, the bot answers to the following commands:
```
/v - Send value
/status - Get status
/remind <hour:mins> - Set a daily reminder
/reset - Reset daily reminders
```

## Contributing

Contributions are welcome.

1. [Fork the repository](https://github.com/fg1/telegram-trkbot/fork)
2. Create your feature branch (`git checkout -b my-feature`)
3. Commit your changes (`git commit -am 'Commit message'`)
4. Push to the branch (`git push origin my-feature`)
5. Create a pull request
