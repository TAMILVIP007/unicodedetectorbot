from asyncio import sleep
from logging import INFO, basicConfig, getLogger
from re import search
from time import time

from emoji import UNICODE_EMOJI
from pyrogram import Client, __version__, filters
from pyrogram.errors import RPCError
from pyrogram.types import (
    CallbackQuery,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from redis import StrictRedis

from config import *

basicConfig(
    format="%(asctime)s - [UNICODE-DETECTOR] - %(levelname)s - %(message)s",
    level=INFO,
)
LOGGER = getLogger(__name__)
bot = Client(
    "detector",
    bot_token=BOT_TOKEN,
    api_id=APP_ID,
    api_hash=API_HASH,
    sleep_threshold=15,
)

print(f"Started detector with pyrogram version {__version__}")

REDIS = StrictRedis.from_url(REDIS_URL, decode_responses=True)
try:
    REDIS.ping()
except BaseException:
    raise Exception("Your redis server is not alive, please check again!")
finally:
    REDIS.ping()
    LOGGER.info("Your redis server is alive!")


@bot.on_message(filters.command("start") & ~filters.bot)
async def start(_, m: Message):
    if m and not m.from_user:
        return
    if m.chat.type != "private":
        return await m.reply_text("I'm alive!")
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="Add me to your chat!",
                url=f"https://t.me/{BOT_USERNAME}?startgroup=true",
            )
        ],
    ])
    return await m.reply_text(
        "Hi there! i'm the one who removes all unicode users from your chat,\
        if you give me a chance!\nCheck /help !",
        reply_markup=kb,
    )


@bot.on_message(filters.command("help") & ~filters.bot)
async def help(_, m: Message):
    if m and not m.from_user:
        return
    return await m.reply_text(
        "Just add me to your chat with ban user permission and \
        toggle /detector on | off !")


@bot.on_message(filters.command("ping") & ~filters.bot)
async def ping(_, m: Message):
    if m and not m.from_user:
        return
    starttime = time()
    reply = await m.reply_text("Pinging ...")
    delta_ping = time() - starttime
    return await reply.edit_text(f"<b>Pong!</b>\n{delta_ping * 1000:.3f} ms")


# thanks to hamkercat for this shortcut
async def member_permissions(chat_id: int, user_id: int):
    perms = []
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except RPCError:
        return []
    if member.can_delete_messages:
        perms.append("can_delete_messages")
    if member.can_restrict_members:
        perms.append("can_restrict_members")
    if member.can_change_info:
        perms.append("can_change_info")
    return perms


@bot.on_message(filters.command("detector") & ~filters.bot)
async def power(_, m: Message):
    if m and not m.from_user:
        return
    if m.chat.type == "private":
        return await m.reply_text("This command works only on supergroups!")

    permissions = await member_permissions(int(m.chat.id), int(m.from_user.id))
    if "can_change_info" not in permissions:
        return await m.reply_text("You don't have enough permissions!")
    args = m.text.split()
    status = REDIS.get(f"Chat_{m.chat.id}")

    if len(args) < 2:
        return await m.reply_text(
            f"This group's current setting is: `{status}`\nTry with on and off to toggle!"
        )
    option = args[1].lower()
    if option in ("yes", "on", "true"):
        REDIS.set(f"Chat_{m.chat.id}", str("True"))
        await m.reply_text(
            "Turned on.",
            quote=True,
        )
    elif option in ("no", "off", "false"):
        REDIS.set(f"Chat_{m.chat.id}", str("False"))
        await m.reply_text(
            "Turned off.",
            quote=True,
        )
    return


# thanks to https://github.com/Squirrel-Network/nebula8/blob/master/core/utilities/regex.py
HAS_ARABIC = "[\u0600-\u06ff]|[\u0750-\u077f]|[\ufb50-\ufbc1]|[\ufbd3-\ufd3f]|[\ufd50-\ufd8f]|[\ufd92-\ufdc7]|[\ufe70-\ufefc]|[\uFDF0-\uFDFD]+"
HAS_CIRILLIC = "[а-яА-Я]+"
HAS_CHINESE = "[\u4e00-\u9fff]+"
EMOJI = UNICODE_EMOJI["en"]


async def check_string(string: str):
    check = search(HAS_ARABIC, string)
    check = search(HAS_CHINESE, string)
    check = search(HAS_CIRILLIC, string)
    for a in string:
        if a in EMOJI:
            check = True
    return check is not None


@bot.on_callback_query(filters.regex("^action_"))
async def _buttons(c: Client, q: CallbackQuery):
    splitter = (str(q.data).replace("action_", "")).split("=")
    chat_id = q.message.chat.id
    action = str(splitter[1])
    user_id = int(splitter[2])
    preeser = q.from_user.id
    mention = (await c.get_users(user_id)).mention
    permissions = await member_permissions(chat_id, preeser)
    whopress = await q.message.chat.get_member(preeser)
    if whopress.status not in ["creator", "administrator"]:
        await q.answer(
            "You're not even an admin, don't try this!",
            show_alert=True,
        )
        return
    if action == "ban":
        bann = "Baned !"
    elif action == "kick":
        bann = "Kicked !"
    elif action == "mute":
        bann = "Muted !"
    else:
        bann = "Solved !"

    editreport = f"""
<b>Action:</b>
{mention} was having unicode letters in the name!
<b>Status:</b> Action Taken by {q.from_user.mention} !
<b>Action:</b> {bann}
    """
    if action == "kick":
        if "can_restrict_members" not in permissions:
            await q.answer("You don't have enough permissions.",
                           show_alert=True)
            return
        try:
            await c.kick_chat_member(chat_id, user_id)
            await q.answer("kicked Succesfully !")
            await q.message.edit_text(editreport)
            await c.unban_chat_member(chat_id, user_id)
            return
        except RPCError as err:
            await q.message.edit_text(
                f"Failed to Kick\n<b>Error:</b>\n</code>{err}</code>")
            return
    elif action == "ban":
        if "can_restrict_members" not in permissions:
            await q.answer("You don't have enough permissions.",
                           show_alert=True)
            return
        try:
            await c.kick_chat_member(chat_id, user_id)
            await q.answer("Succesfully Banned!")
            await q.message.edit_text(editreport)
            return
        except RPCError as err:
            await q.message.edit_text(f"Failed to Ban\n<b>Error:</b>\n`{err}`")
            return
    elif action == "mute":
        if "can_restrict_members" not in permissions:
            await q.answer("You don't have enough permissions.",
                           show_alert=True)
            return
        try:
            await q.message.chat.restrict_member(
                user_id,
                ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_stickers=False,
                    can_send_animations=False,
                    can_send_games=False,
                    can_use_inline_bots=False,
                    can_add_web_page_previews=False,
                    can_send_polls=False,
                    can_change_info=False,
                    can_invite_users=True,
                    can_pin_messages=False,
                ),
            )
            await q.answer("Muted !")
            await q.message.edit_text(editreport)
            return
        except RPCError as err:
            await q.message.edit_text(f"Failed to Ban\n<b>Error:</b>\n`{err}`")
            return
    elif action == "oke":
        if "can_restrict_members" not in permissions:
            await q.answer("You don't have enough permissions.",
                           show_alert=True)
            return
        if "can_delete_messages" not in permissions:
            await q.answer("You don't have enough permissions.",
                           show_alert=True)
            return
        await q.message.edit_text(editreport)
        return
    return


@bot.on_message(filters.group & filters.all & ~filters.bot, group=69)
async def triggered(c: Client, m: Message):
    if m and not m.from_user:
        return
    if not bool(REDIS.get(f"Chat_{m.chat.id}")):
        return
    x = await c.get_users(int(m.from_user.id))
    user_has = ""
    try:
        user_has = x.first_name
    except TypeError:
        pass
    try:
        user_has += x.last_name
    except TypeError:
        pass
    who = await m.chat.get_member(int(m.from_user.id))
    if who.status in ["creator", "administrator"]:
        return
    if not user_has:
        await c.send_message(int(m.chat.id), "User detected without a name!!")
        return await sleep(3)

    what = await check_string(str(user_has))
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "Kick",
                callback_data=f"action_=kick={m.from_user.id}",
            ),
            InlineKeyboardButton(
                "Ban",
                callback_data=f"action_=ban={m.from_user.id}",
            ),
        ],
        [
            InlineKeyboardButton(
                "Mute",
                callback_data=f"action_=mute={m.from_user.id}",
            ),
            InlineKeyboardButton(
                "Solved !",
                callback_data=f"action_=oke={m.from_user.id}",
            ),
        ],
    ])
    admin_data = await bot.get_chat_members(int(m.chat.id),
                                            filter="administrators")
    ADMINS_TAG = str()
    TAG = "\u200b"
    for admin in admin_data:
        if not admin.user.is_bot:
            ADMINS_TAG += f"[{TAG}](tg://user?id={admin.user.id})"
    ADMINS_TAG += "Unicode user detected !!"
    if what:
        await c.send_message(int(m.chat.id), ADMINS_TAG, reply_markup=keyboard)
    return await sleep(3)


bot.run()
