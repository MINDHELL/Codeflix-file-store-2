#=====================================================================================##
# Don't Remove Credit @CodeFlix_Bots, @rohit_1888
# Ask Doubt on telegram @CodeflixSupport
# Copyright (C) 2025 by Codeflix-Bots@Github
# Project: https://github.com/Codeflix-Bots/FileStore
# License: MIT
#=====================================================================================##

import asyncio
import os
import random
import string
import time
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatAction
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from bot import Bot
from config import *
from helper_func import *
from database.database import *
from database.db_premium import *

# Verification timing
MIN_VERIFY_TIME = 80
MAX_VERIFY_TIME = 600
verify_cache = {}  # {user_id: {base64_string: timestamp}}

# Constants
BAN_SUPPORT = f"{BAN_SUPPORT}"
TUT_VID = f"{TUT_VID}"

# ------------------------------
# Short URL generator function
# ------------------------------
async def short_url(client: Client, message: Message, base64_string):
    try:
        user_id = message.from_user.id

        # Store generation time
        if user_id not in verify_cache:
            verify_cache[user_id] = {}
        verify_cache[user_id][base64_string] = time.time()

        prem_link = f"https://t.me/{client.username}?start=yu3elk{base64_string}7"
        short_link = await get_shortlink(SHORTLINK_URL, SHORTLINK_API, prem_link)

        if not short_link:
            return await message.reply_text(
                "⚠️ Sorry, the short link could not be generated. Please try again later."
            )

        buttons = [
            [
                InlineKeyboardButton("ᴅᴏᴡɴʟᴏᴀᴅ", url=short_link),
                InlineKeyboardButton("ᴛᴜᴛᴏʀɪᴀʟ", url=TUT_VID)
            ],
            [
                InlineKeyboardButton("ᴘʀᴇᴍɪᴜᴍ", callback_data="premium")
            ]
        ]

        await message.reply_photo(
            photo=SHORTENER_PIC,
            caption=SHORT_MSG,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        await message.reply_text(f"⚠️ Error generating short link:\n{e}")

# ------------------------------
# Start command handler
# ------------------------------
@Bot.on_message(filters.command('start') & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    is_premium = await is_premium_user(user_id)

    # Add user if not present
    if not await db.present_user(user_id):
        try:
            await db.add_user(user_id)
        except Exception:
            pass

    # Force subscription check
    if not await is_subscribed(client, user_id):
        return await not_joined(client, message)

    # Banned user check
    banned_users = await db.get_ban_users()
    if user_id in banned_users:
        return await message.reply_text(
            "<b>⛔️ You are Bᴀɴɴᴇᴅ from using this bot.</b>\n\n"
            "<i>Contact support if you think this is a mistake.</i>",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Contact Support", url=BAN_SUPPORT)]]
            )
        )

    text = message.text
    FILE_AUTO_DELETE = await db.get_del_timer()

    # Extract start payload (if any)
    start_payload = text.split(" ")[1] if len(text.split()) > 1 else None

    if start_payload:
        # Step 1: generate short link & store verification time
        await short_url(client, message, start_payload)
        return  # Stop further execution until user clicks the short link

    # Step 2: No payload → send welcome message
    await message.reply_photo(
        photo=START_PIC,
        caption=START_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username='@' + message.from_user.username if message.from_user.username else None,
            mention=message.from_user.mention,
            id=user_id
        ),
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("• ᴍᴏʀᴇ ᴄʜᴀɴɴᴇʟs •", url="https://t.me/Nova_Flix/50")],
                [
                    InlineKeyboardButton("• ᴀʙᴏᴜᴛ", callback_data="about"),
                    InlineKeyboardButton("ʜᴇʟᴘ •", callback_data="help")
                ]
            ]
        ),
        message_effect_id=5104841245755180586
    )

# ------------------------------
# File access handler (after short link)
# ------------------------------
async def handle_file_access(client: Client, message: Message, base64_string: str, is_premium: bool):
    user_id = message.from_user.id

    # BYPASS DETECTION
    if not is_premium and user_id != OWNER_ID:
        if user_id not in verify_cache or base64_string not in verify_cache[user_id]:
            await message.reply_text(
                "⛔ Bypass Detected!\nYou must click the short link first."
            )
            await client.send_message(
                OWNER_ID,
                f"⚠️ BYPASS ALERT!\nUser {message.from_user.mention} ({user_id}) tried to access file `{base64_string}` without verification."
            )
            return

        # Check elapsed time
        sent_time = verify_cache[user_id][base64_string]
        elapsed = time.time() - sent_time

        if elapsed < MIN_VERIFY_TIME:
            await message.reply_text(
                f"⛔ Bypass Detected!\nPlease complete verification first.\nMinimum verification time: {MIN_VERIFY_TIME}s."
            )
            await client.send_message(
                OWNER_ID,
                f"⚠️ BYPASS ALERT!\nUser {message.from_user.mention} ({user_id}) clicked link too early.\nElapsed: {int(elapsed)}s for file `{base64_string}`."
            )
            return

        if elapsed > MAX_VERIFY_TIME:
            del verify_cache[user_id][base64_string]
            await message.reply_text(
                "⏰ Link Expired!\nPlease generate a new link."
            )
            return

    # DECODE PAYLOAD & FETCH FILES
    string = await decode(base64_string)
    argument = string.split("-")
    ids = []

    if len(argument) == 3:
        start = int(int(argument[1]) / abs(client.db_channel.id))
        end = int(int(argument[2]) / abs(client.db_channel.id))
        ids = range(start, end + 1) if start <= end else range(start, end - 1, -1)
    elif len(argument) == 2:
        ids = [int(int(argument[1]) / abs(client.db_channel.id))]

    # Fetch messages
    temp_msg = await message.reply("<b>Please wait...</b>")
    try:
        messages = await get_messages(client, ids)
    except Exception as e:
        await message.reply_text("Something went wrong while fetching files!")
        print(f"Error getting messages: {e}")
        return
    finally:
        await temp_msg.delete()

    codeflix_msgs = []
    for msg in messages:
        original_caption = msg.caption.html if msg.caption else ""
        caption = f"{original_caption}\n\n{CUSTOM_CAPTION}" if CUSTOM_CAPTION else original_caption
        reply_markup = msg.reply_markup if DISABLE_CHANNEL_BUTTON else None

        try:
            snt_msg = await msg.copy(
                chat_id=user_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                protect_content=PROTECT_CONTENT
            )
            await asyncio.sleep(0.5)
            codeflix_msgs.append(snt_msg)
        except FloodWait as e:
            await asyncio.sleep(e.x)
            snt_msg = await msg.copy(
                chat_id=user_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                protect_content=PROTECT_CONTENT
            )
            codeflix_msgs.append(snt_msg)
        except Exception:
            pass

    # Auto-delete handling
    FILE_AUTO_DELETE = await db.get_del_timer()
    if FILE_AUTO_DELETE > 0:
        notification_msg = await message.reply(
            f"<b>This file will be deleted in {get_exp_time(FILE_AUTO_DELETE)}. Please save or forward it before it is deleted.</b>"
        )

        await asyncio.sleep(FILE_AUTO_DELETE)
        for snt_msg in codeflix_msgs:
            try:
                await snt_msg.delete()
            except Exception as e:
                print(f"Error deleting message {snt_msg.id}: {e}")

        # Reload button
        reload_url = f"https://t.me/{client.username}?start={message.command[1]}" if message.command and len(message.command) > 1 else None
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("ɢᴇᴛ ғɪʟᴇ ᴀɢᴀɪɴ!", url=reload_url)]]
        ) if reload_url else None

        try:
            await notification_msg.edit(
                "<b>Your video/file was successfully deleted!</b>",
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Error updating notification: {e}")

#=====================================================================================##
# The rest of your handlers (premium commands, force-subscription, myplan, etc.) 
# remain the same, as they are already correct.
#=====================================================================================##





#=====================================================================================##
# Don't Remove Credit @CodeFlix_Bots, @rohit_1888
# Ask Doubt on telegram @CodeflixSupport



# Create a global dictionary to store chat data
chat_data_cache = {}

async def not_joined(client: Client, message: Message):
    temp = await message.reply("<b><i>Checking Subscription...</i></b>")

    user_id = message.from_user.id
    buttons = []
    count = 0

    try:
        all_channels = await db.show_channels()  # Should return list of (chat_id, mode) tuples
        for total, chat_id in enumerate(all_channels, start=1):
            mode = await db.get_channel_mode(chat_id)  # fetch mode 

            await message.reply_chat_action(ChatAction.TYPING)

            if not await is_sub(client, user_id, chat_id):
                try:
                    # Cache chat info
                    if chat_id in chat_data_cache:
                        data = chat_data_cache[chat_id]
                    else:
                        data = await client.get_chat(chat_id)
                        chat_data_cache[chat_id] = data

                    name = data.title

                    # Generate proper invite link based on the mode
                    if mode == "on" and not data.username:
                        invite = await client.create_chat_invite_link(
                            chat_id=chat_id,
                            creates_join_request=True,
                            expire_date=datetime.utcnow() + timedelta(seconds=FSUB_LINK_EXPIRY) if FSUB_LINK_EXPIRY else None
                            )
                        link = invite.invite_link

                    else:
                        if data.username:
                            link = f"https://t.me/{data.username}"
                        else:
                            invite = await client.create_chat_invite_link(
                                chat_id=chat_id,
                                expire_date=datetime.utcnow() + timedelta(seconds=FSUB_LINK_EXPIRY) if FSUB_LINK_EXPIRY else None)
                            link = invite.invite_link

                    buttons.append([InlineKeyboardButton(text=name, url=link)])
                    count += 1
                    await temp.edit(f"<b>{'! ' * count}</b>")

                except Exception as e:
                    print(f"Error with chat {chat_id}: {e}")
                    return await temp.edit(
                        f"<b><i>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴛᴏ sᴏʟᴠᴇ ᴛʜᴇ ɪssᴜᴇs @rohit_1888</i></b>\n"
                        f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
                    )

        # Retry Button
        try:
            buttons.append([
                InlineKeyboardButton(
                    text='♻️ Tʀʏ Aɢᴀɪɴ',
                    url=f"https://t.me/{client.username}?start={message.command[1]}"
                )
            ])
        except IndexError:
            pass

        await message.reply_photo(
            photo=FORCE_PIC,
            caption=FORCE_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else '@' + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    except Exception as e:
        print(f"Final Error: {e}")
        await temp.edit(
            f"<b><i>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴛᴏ sᴏʟᴠᴇ ᴛʜᴇ ɪssᴜᴇs @rohit_1888</i></b>\n"
            f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
        )

#=====================================================================================##

@Bot.on_message(filters.command('myplan') & filters.private)
async def check_plan(client: Client, message: Message):
    user_id = message.from_user.id  # Get user ID from the message

    # Get the premium status of the user
    status_message = await check_user_plan(user_id)

    # Send the response message to the user
    await message.reply(status_message)

#=====================================================================================##
# Command to add premium user
@Bot.on_message(filters.command('addpremium') & filters.private & admin)
async def add_premium_user_command(client, msg):
    if len(msg.command) != 4:
        await msg.reply_text(
            "Usage: /addpremium <user_id> <time_value> <time_unit>\n\n"
            "Time Units:\n"
            "s - seconds\n"
            "m - minutes\n"
            "h - hours\n"
            "d - days\n"
            "y - years\n\n"
            "Examples:\n"
            "/addpremium 123456789 30 m → 30 minutes\n"
            "/addpremium 123456789 2 h → 2 hours\n"
            "/addpremium 123456789 1 d → 1 day\n"
            "/addpremium 123456789 1 y → 1 year"
        )
        return

    try:
        user_id = int(msg.command[1])
        time_value = int(msg.command[2])
        time_unit = msg.command[3].lower()  # supports: s, m, h, d, y

        # Call add_premium function
        expiration_time = await add_premium(user_id, time_value, time_unit)

        # Notify the admin
        await msg.reply_text(
            f"✅ User `{user_id}` added as a premium user for {time_value} {time_unit}.\n"
            f"Expiration Time: `{expiration_time}`"
        )

        # Notify the user
        await client.send_message(
            chat_id=user_id,
            text=(
                f"🎉 Premium Activated!\n\n"
                f"You have received premium access for `{time_value} {time_unit}`.\n"
                f"Expires on: `{expiration_time}`"
            ),
        )

    except ValueError:
        await msg.reply_text("❌ Invalid input. Please ensure user ID and time value are numbers.")
    except Exception as e:
        await msg.reply_text(f"⚠️ An error occurred: `{str(e)}`")


# Command to remove premium user
@Bot.on_message(filters.command('remove_premium') & filters.private & admin)
async def pre_remove_user(client: Client, msg: Message):
    if len(msg.command) != 2:
        await msg.reply_text("useage: /remove_premium user_id ")
        return
    try:
        user_id = int(msg.command[1])
        await remove_premium(user_id)
        await msg.reply_text(f"User {user_id} has been removed.")
    except ValueError:
        await msg.reply_text("user_id must be an integer or not available in database.")


# Command to list active premium users
@Bot.on_message(filters.command('premium_users') & filters.private & admin)
async def list_premium_users_command(client, message):
    # Define IST timezone
    ist = timezone("Asia/Kolkata")

    # Retrieve all users from the collection
    premium_users_cursor = collection.find({})
    premium_user_list = ['Active Premium Users in database:']
    current_time = datetime.now(ist)  # Get current time in IST

    # Use async for to iterate over the async cursor
    async for user in premium_users_cursor:
        user_id = user["user_id"]
        expiration_timestamp = user["expiration_timestamp"]

        try:
            # Convert expiration_timestamp to a timezone-aware datetime object in IST
            expiration_time = datetime.fromisoformat(expiration_timestamp).astimezone(ist)

            # Calculate remaining time
            remaining_time = expiration_time - current_time

            if remaining_time.total_seconds() <= 0:
                # Remove expired users from the database
                await collection.delete_one({"user_id": user_id})
                continue  # Skip to the next user if this one is expired

            # If not expired, retrieve user info
            user_info = await client.get_users(user_id)
            username = user_info.username if user_info.username else "No Username"
            first_name = user_info.first_name
            mention=user_info.mention

            # Calculate days, hours, minutes, seconds left
            days, hours, minutes, seconds = (
                remaining_time.days,
                remaining_time.seconds // 3600,
                (remaining_time.seconds // 60) % 60,
                remaining_time.seconds % 60,
            )
            expiry_info = f"{days}d {hours}h {minutes}m {seconds}s left"

            # Add user details to the list
            premium_user_list.append(
                f"UserID: <code>{user_id}</code>\n"
                f"User: @{username}\n"
                f"Name: {mention}\n"
                f"Expiry: {expiry_info}"
            )
        except Exception as e:
            premium_user_list.append(
                f"UserID: <code>{user_id}</code>\n"
                f"Error: Unable to fetch user details ({str(e)})"
            )

    if len(premium_user_list) == 1:  # No active users found
        await message.reply_text("I found 0 active premium users in my DB")
    else:
        await message.reply_text("\n\n".join(premium_user_list), parse_mode=None)


#=====================================================================================##

@Bot.on_message(filters.command("count") & filters.private & admin)
async def total_verify_count_cmd(client, message: Message):
    total = await db.get_total_verify_count()
    await message.reply_text(f"Tᴏᴛᴀʟ ᴠᴇʀɪғɪᴇᴅ ᴛᴏᴋᴇɴs ᴛᴏᴅᴀʏ: <b>{total}</b>")


#=====================================================================================##

@Bot.on_message(filters.command('commands') & filters.private & admin)
async def bcmd(bot: Bot, message: Message):        
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("• ᴄʟᴏsᴇ •", callback_data = "close")]])
    await message.reply(text=CMD_TXT, reply_markup = reply_markup, quote= True)
