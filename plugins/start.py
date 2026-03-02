#=====================================================================================##
# Credit @CodeFlix_Bots, @rohit_1888
# Project: https://github.com/Codeflix-Bots/FileStore
# License: MIT
#=====================================================================================##

import asyncio
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

# ------------------------------
# Constants
# ------------------------------
MIN_VERIFY_TIME = 80
MAX_VERIFY_TIME = 600
verify_cache = {}  # {user_id: {base64_string: {"timestamp": t, "clicked": bool}}}
BAN_SUPPORT = f"{BAN_SUPPORT}"
TUT_VID = f"{TUT_VID}"


# ------------------------------
# Short URL generator (Mongo Based)
# ------------------------------
async def short_url(client: Client, message: Message, base64_string):
    user_id = message.from_user.id

    prem_link = f"https://t.me/{client.username}?start=yu3elk{base64_string}7"
    short_link = await get_shortlink(SHORTLINK_URL, SHORTLINK_API, prem_link)

    if not short_link:
        return await message.reply_text(
            "⚠️ Could not generate short link. Please try again later."
        )

    # Store verification token in MongoDB
    await db.update_verify_status(
        user_id,
        verify_token=base64_string,
        is_verified=False,
        verified_time=int(time.time()),
        link=base64_string
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


# ------------------------------
# Start command handler
# ------------------------------
@Bot.on_message(filters.command('start') & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    is_premium = await is_premium_user(user_id)

    # Add user if not exists
    if not await db.present_user(user_id):
        try:
            await db.add_user(user_id)
        except:
            pass

    # Force subscription
    if not await is_subscribed(client, user_id):
        return await not_joined(client, message)

    # Ban check
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
    start_payload = text.split(" ")[1] if len(text.split()) > 1 else None

    if start_payload:

        # Verification return link
        if start_payload.startswith("yu3elk") and start_payload.endswith("7"):
            real_payload = start_payload[6:-1]
            await handle_file_access(client, message, real_payload, is_premium=False)
            return

        # Normal file access
        if is_premium:
            await handle_file_access(client, message, start_payload, is_premium=True)
        else:
            await short_url(client, message, start_payload)

        return

    # Welcome message
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
# File access handler (Mongo Based Per File)
# ------------------------------
# ------------------------------
# File access handler (FIXED & CLEAN)
# ------------------------------
async def handle_file_access(client: Client, message: Message, base64_string: str, is_premium: bool):

    user_id = message.from_user.id

    # =============================
    # 🔐 VERIFICATION SECTION
    # =============================
    if not is_premium and user_id != OWNER_ID:

        verify = await db.get_verify_status(user_id)

        # 1️⃣ No record OR wrong token
        if not verify or verify.get("verify_token") != base64_string:
            await message.reply_text(
                "⛔ Bypass Detected!\nYou must click the short link first."
            )

            await client.send_message(
                OWNER_ID,
                f"⚠️ BYPASS ALERT!\n\n"
                f"User: {message.from_user.mention}\n"
                f"User ID: {user_id}\n"
                f"File Token: {base64_string}"
            )
            return

        sent_time = int(verify.get("verified_time", 0))
        elapsed = int(time.time()) - sent_time

        # 2️⃣ Expired check (MUST BE BEFORE MIN CHECK)
        if elapsed > MAX_VERIFY_TIME:
            await db.update_verify_status(
                user_id,
                verify_token="",
                is_verified=False,
                verified_time=0,
                link=""
            )

            await message.reply_text(
                "⏰ Link Expired!\nPlease generate a new link."
            )
            return

        # 3️⃣ Minimum verification time check
        if elapsed < MIN_VERIFY_TIME:
            await message.reply_text(
                f"⛔ Bypass Detected!\nMinimum verification time: {MIN_VERIFY_TIME} seconds."
            )

            await client.send_message(
                OWNER_ID,
                f"⚠️ FAST VERIFY ALERT!\n\n"
                f"User: {message.from_user.mention}\n"
                f"User ID: {user_id}\n"
                f"Time Taken: {elapsed}s"
            )
            return

        # 4️⃣ SUCCESS → Clear token (one-time use)
        await db.update_verify_status(
            user_id,
            verify_token="",
            is_verified=True,
            verified_time=0,
            link=""
        )

        # Increase verify count
        count = await db.get_verify_count(user_id)
        await db.set_verify_count(user_id, count + 1)

    # =============================
    # 📂 FILE DECODE SECTION
    # =============================
    try:
        string = await decode(base64_string)
        argument = string.split("-")
        ids = []

        if len(argument) == 3:
            start = int(int(argument[1]) / abs(client.db_channel.id))
            end = int(int(argument[2]) / abs(client.db_channel.id))
            ids = range(start, end + 1) if start <= end else range(start, end - 1, -1)

        elif len(argument) == 2:
            ids = [int(int(argument[1]) / abs(client.db_channel.id))]

    except Exception as e:
        print(f"Decode Error: {e}")
        return await message.reply_text("❌ Invalid file link.")

    # =============================
    # 📥 FETCH FILES
    # =============================
    temp_msg = await message.reply("<b>Please wait...</b>")

    try:
        messages = await get_messages(client, ids)
    except Exception as e:
        await temp_msg.delete()
        print(f"Fetch Error: {e}")
        return await message.reply_text("❌ Something went wrong while fetching files!")
    finally:
        try:
            await temp_msg.delete()
        except:
            pass

    # =============================
    # 📤 SEND FILES
    # =============================
    sent_messages = []

    for msg in messages:
        original_caption = msg.caption.html if msg.caption else ""
        caption = f"{original_caption}\n\n{CUSTOM_CAPTION}" if CUSTOM_CAPTION else original_caption
        reply_markup = msg.reply_markup if DISABLE_CHANNEL_BUTTON else None

        try:
            sent = await msg.copy(
                chat_id=user_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                protect_content=PROTECT_CONTENT
            )
            sent_messages.append(sent)
            await asyncio.sleep(0.5)

        except FloodWait as e:
            await asyncio.sleep(e.x)
            sent = await msg.copy(
                chat_id=user_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                protect_content=PROTECT_CONTENT
            )
            sent_messages.append(sent)

        except Exception as e:
            print(f"Send Error: {e}")

    # =============================
    # 🗑 AUTO DELETE SECTION (FIXED)
    # =============================
    FILE_AUTO_DELETE = await db.get_del_timer()

    if FILE_AUTO_DELETE > 0:

        notification = await message.reply(
            f"<b>This file will be deleted in {get_exp_time(FILE_AUTO_DELETE)}.</b>"
        )

        await asyncio.sleep(FILE_AUTO_DELETE)

        for sent in sent_messages:
            try:
                await sent.delete()
            except:
                pass

        try:
            await notification.edit(
                "<b>Your file was successfully deleted!</b>"
            )
        except Exception as e:
            print(f"Notification Edit Error: {e}")
            
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



@Bot.on_message(filters.command("free"))
async def free_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage:\n/free FILE_ID or BATCH_ID")

    token = message.command[1]

    user_id = message.from_user.id

    # If batch
    if token.startswith("batch_"):
        files = await db.get_batch_files(token)
        if not files:
            return await message.reply("Batch not found.")

        for file in files:
            await client.send_cached_media(
                chat_id=user_id,
                file_id=file["file_id"],
                caption=file.get("caption", "")
            )
        return

    # Single file
    file = await db.get_file(token)
    if not file:
        return await message.reply("File not found.")

    await client.send_cached_media(
        chat_id=user_id,
        file_id=file["file_id"],
        caption=file.get("caption", "")
    )


@Bot.on_message(filters.command("premium"))
async def premium_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage:\n/premium FILE_ID or BATCH_ID")

    token = message.command[1]
    user_id = message.from_user.id

    if not await is_premium(user_id):
        return await message.reply(
            "❌ This is a premium file.\n\n"
            "Buy premium to access this content."
        )

    # If batch
    if token.startswith("batch_"):
        files = await db.get_batch_files(token)
        if not files:
            return await message.reply("Batch not found.")

        for file in files:
            await client.send_cached_media(
                chat_id=user_id,
                file_id=file["file_id"],
                caption=file.get("caption", "")
            )
        return

    # Single file
    file = await db.get_file(token)
    if not file:
        return await message.reply("File not found.")

    await client.send_cached_media(
        chat_id=user_id,
        file_id=file["file_id"],
        caption=file.get("caption", "")
    )







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
