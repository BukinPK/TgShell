import telegram.ext as tg
from telegram import Update, ChatAction
from telegram.error import BadRequest
from telegram.constants import MAX_MESSAGE_LENGTH
import os
import sys
import subprocess
from html import escape
import signal
from telegram.utils.helpers import mention_html
import traceback
from threading import Thread
from time import sleep
from private import TOKEN, ADMIN_ID


updater = tg.Updater(TOKEN, use_context=True)
dp = updater.dispatcher
bot = updater.bot
env_path = os.path.abspath('.env')
home_dir = home = os.path.expanduser('~')
child = set()
threads = []


def get_env(env_path):
    env = dict()
    if os.path.exists(env_path):
        for item in open(env_path, 'r').readlines():
            key, val = item.split('=', 1)
            env.update({key: val.strip()})
    return env

def bash(code):
    env = get_env(env_path)
    ps = subprocess.Popen(
        ['bash', '-c', f'HOME={home_dir} {code}; env > {env_path}'],
        stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, env=env,
        cwd=env.get('PWD'), text=True, preexec_fn=os.setsid)
    child.add(ps.pid)
    res = ''
    try:
        res = ps.communicate()[0]
    finally:
        child.remove(ps.pid)
    return res

def kill(upd, ctx):
    for pid in child:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    for pid in child:
        os.killpg(os.getpgid(pid), signal.SIGKILL)

def execute(upd, ctx):
    ctx.bot.send_chat_action(upd.effective_message.chat_id, ChatAction.TYPING)
    try:
        msg = bash(upd.effective_message.text)
        msg = escape(msg)
    except Exception as ex:
        msg = escape(ex.__repr__())
    msg = msg.strip()

    offset = 0
    while not sleep(.1):
        msg_splited = msg[offset:offset+MAX_MESSAGE_LENGTH]
        if not msg_splited:
            break
        upd.effective_message.reply_text(
            f'<pre>{msg_splited}</pre>', parse_mode='HTML')
        offset += MAX_MESSAGE_LENGTH

def exec_thread(upd, ctx):
    Thread(target=execute, args=[upd, ctx]).start()

def error(update, context):
    trace = ''.join(traceback.format_tb(sys.exc_info()[2]))
    payload = ''
    if update.effective_user:
        payload += f' with the user '
        payload += mention_html(
            update.effective_user.id, update.effective_user.first_name)
    text = (f'The error <code>{context.error}</code> happened{payload}. '
            f'The full traceback:\n\n<code>{trace}</code>')
    context.bot.send_message(ADMIN_ID, text, parse_mode='HTML')
    raise

def stop_and_restart():
    updater.stop()
    os.execl(sys.executable, sys.executable, *sys.argv)

def restart(update, context):
    update.message.reply_text('Bot is restarting...')
    Thread(target=stop_and_restart).start()

def alive(upd, ctx):
    upd.message.reply_text(f'{len(child)} alive processes.\n\n' +
                           ', '.join([f'<code>{p}</code>' for p in child]),
                           parse_mode='HTML')


dp.add_handler(tg.CommandHandler(
    'restart', restart, filters=tg.Filters.user(user_id=ADMIN_ID)))
dp.add_handler(tg.CommandHandler(
    'kill', kill, filters=tg.Filters.user(user_id=ADMIN_ID)))
dp.add_handler(tg.CommandHandler(
    'alive', alive, filters=tg.Filters.user(user_id=ADMIN_ID)))
dp.add_handler(tg.MessageHandler(
    tg.Filters.text & tg.Filters.user(user_id=ADMIN_ID), exec_thread))

dp.add_error_handler(error)

bot.send_message(ADMIN_ID, 'Bot is successfully restarted.')

updater.start_polling()
