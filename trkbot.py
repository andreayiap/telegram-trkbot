#!/usr/bin/env python
# -*- encoding: utf-8 -*+

import logging
import datetime
from peewee import *
from emoji import emojize
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Updater, Job, CallbackQueryHandler
from telegram.ext import CommandHandler, MessageHandler, Filters
from functools import wraps
from config import *

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# -------------------------------------
db = SqliteDatabase(DB_PATH)


class MVal(Model):
    user = IntegerField(null=False)
    date = DateField(default=datetime.date.today)
    dt = DateTimeField(default=datetime.datetime.now)
    val = IntegerField(null=False)

    class Meta:
        database = db


class Schedule(Model):
    chat_id = IntegerField(null=False)
    user = IntegerField(null=False)
    run_at_hour = IntegerField(null=False)
    run_at_mins = IntegerField(null=False)

    class Meta:
        database = db

    def wait_delay(self):
        run_at = datetime.time(self.run_at_hour, self.run_at_mins)
        run_day = datetime.date.today()

        next_dt = datetime.datetime.combine(run_day, run_at)
        delay = next_dt - datetime.datetime.now()
        delay = delay.total_seconds()
        if delay > 0:
            return delay

        run_day += datetime.timedelta(days=1)
        next_dt = datetime.datetime.combine(run_day, run_at)
        delay = next_dt - datetime.datetime.now()
        return delay.total_seconds()

    def push_job(self, job_queue, chat_data=None):
        ctx = {'chat_id': self.chat_id, 'sched': self}
        next_t = self.wait_delay()
        job = Job(push_job, next_t, repeat=True, context=ctx)
        job_queue.put(job)
        logger.debug('(%d) Next execution in %d secs' % (self.chat_id, next_t))

        if chat_data is None:
            return next_t

        if 'jobs' not in chat_data:
            chat_data['jobs'] = []
        chat_data['jobs'].append((job, self))
        return next_t

# -------------------------------------


def get_user_id(update):
    # extract user_id from arbitrary update
    try:
        user_id = update.message.from_user.id
    except (NameError, AttributeError):
        try:
            user_id = update.inline_query.from_user.id
        except (NameError, AttributeError):
            try:
                user_id = update.chosen_inline_result.from_user.id
            except (NameError, AttributeError):
                try:
                    user_id = update.callback_query.from_user.id
                except (NameError, AttributeError):
                    print("No user_id available in update.")
                    return
    return user_id


def restricted(func):
    @wraps(func)
    def wrapped(bot, update, *args, **kwargs):
        user_id = get_user_id(update)
        if user_id not in AUTH_USERS:
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(bot, update, *args, **kwargs)

    return wrapped


def get_keyboard():
    keyboard = [[]]
    for i in range(len(OPTIONS)):
        keyboard[0].append(InlineKeyboardButton(emojize('   %s   ' % OPTIONS[i], use_aliases=True), callback_data=str(i)))

    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup


def push_job(bot, job):
    bot.sendMessage(job.context['chat_id'], text=QUESTION, reply_markup=get_keyboard())
    job.interval = job.context['sched'].wait_delay()
    logger.debug('(%d) Next execution in %d secs' % (job.context['chat_id'], job.interval))


@restricted
def cmd_start(bot, upd):
    """/start handler
    Just send an help message
    """
    upd.message.reply_text('Hello!\n\n/v - Send value\n/status - Get status\n/remind <hour:mins> - Set a daily reminder\n/reset - Reset daily reminders')


@restricted
def cmd_remind(bot, upd, args, job_queue, chat_data):
    """/remind handler
    Enables a user to set a reminder to send a value
    """
    if len(args) != 1:
        upd.message.reply_text('Usage: /remind <hour:mins>')
        return

    try:
        hours, minutes = map(int, args[0].split(':'))
        run_at = datetime.time(hours, minutes)
    except:
        upd.message.reply_text('Usage: /remind <hour:mins>')
        return

    s = Schedule(chat_id=upd.message.chat_id, user=get_user_id(upd), run_at_hour=hours, run_at_mins=minutes)
    s.save()
    next_t = s.push_job(job_queue, chat_data)

    upd.message.reply_text('Okay! Next execution in %d secs' % next_t)


@restricted
def cmd_reset(bot, upd, chat_data):
    """/reset handler
    Reset the reminders
    """
    if 'jobs' in chat_data:
        while len(chat_data['jobs']) > 0:
            job, s = chat_data['jobs'].pop()
            s.delete_instance()
            job.schedule_removal()

    for s in Schedule.select().where(Schedule.chat_id == upd.message.chat_id):
        s.delete_instance()

    upd.message.reply_text('Done!')


@restricted
def cmd_val(bot, upd):
    """/v handler
    """
    upd.message.reply_text(QUESTION, reply_markup=get_keyboard())


@restricted
def cmd_status(bot, upd):
    """/status handler
    Lists the reminders
    """
    chat_id = upd.message.chat_id
    t = []
    for s in Schedule.select().where(Schedule.chat_id == chat_id):
        t.append(str(s.run_at_hour).zfill(2) + ':' + str(s.run_at_mins).zfill(2))

    if len(t) > 0:
        upd.message.reply_text('Reminders: ' + ', '.join(t))
    else:
        upd.message.reply_text('No reminders set')


@restricted
def clbk_val(bot, upd):
    query = upd.callback_query
    logger.info('(%d) Received val: %s' % (query.message.chat_id, query.data))
    opt = int(query.data)
    v = MVal(val=opt, user=get_user_id(upd))
    v.save()
    bot.editMessageText(text=emojize('Saved: %s' % OPTIONS[opt], use_aliases=True), chat_id=query.message.chat_id, message_id=query.message.message_id)


def error_hdler(bot, upd, err):
    logger.warning('Update "%s" caused error "%s"' % (update, error))


def main():
    upd = Updater(TOKEN)

    dp = upd.dispatcher
    dp.add_handler(CommandHandler('start', cmd_start))
    dp.add_handler(CommandHandler('v', cmd_val))
    dp.add_handler(CommandHandler('remind', cmd_remind, pass_args=True, pass_job_queue=True, pass_chat_data=True))
    dp.add_handler(CommandHandler('reset', cmd_reset, pass_chat_data=True))
    dp.add_handler(CommandHandler('status', cmd_status))
    dp.add_handler(CallbackQueryHandler(clbk_val))
    dp.add_handler(MessageHandler(Filters.all, cmd_start))
    dp.add_error_handler(error_hdler)

    jq = upd.job_queue
    for s in Schedule.select():
        chat_data = {}
        s.push_job(jq, chat_data)
        dp.chat_data[s.chat_id] = chat_data

    upd.start_polling()
    upd.idle()


if __name__ == '__main__':
    db.connect()
    db.create_tables([MVal, Schedule], safe=True)
    main()
    db.close()
