import hashlib
import re
import datetime
from os import getenv
from pathlib import Path

from pyrogram import Client, filters, idle
from pyrogram.enums import ChatType, MessageMediaType
from pyrogram.types import (Message, CallbackQuery, InlineKeyboardButton,
                            InlineKeyboardMarkup)
from pyrogram.errors.exceptions.bad_request_400 import (ChannelInvalid,
                                                        PeerIdInvalid,
                                                        UsernameNotOccupied,
                                                        UsernameInvalid)
from pyrogram.errors.exceptions.not_acceptable_406 import ChannelPrivate

from forward import user
from config import Forwarding, Bot
from logger import logger

# Config path
app_dir = Path(__file__).parent
config_dir = app_dir / "config"

# Translation languages
LANGS = {
    "Auto": "auto",
    "Spanish": "es",
    "English": "en",
    "Italian": "it",
    "French": "fr",
    "Portuguese": "pt",
    "German": "de"
}
# Reversed languages
REV_LANGS = {v: k for k, v in LANGS.items()}

# Load the bot configuration
bot_config = Bot().get_config()
forwardings = Forwarding()

# Set up the Telegram client
API_ID = getenv("API_ID") if getenv("API_ID") else bot_config["api_id"]
API_HASH = getenv("API_HASH") if getenv("API_HASH") else bot_config["api_hash"]

bot = Client(str(Path(config_dir/"bot")), API_ID, API_HASH)
commands = ["start", "menu", "blockimage",
            "blockall", "rmblockall", "replaceall", "rmreplaceall"]
answer_users = {}


# Lambda function to create a hash from a string
async def md5(word): return hashlib.md5(word.encode("utf-8")).hexdigest()


async def is_admin(filter, client: Client, event: Message | CallbackQuery):
    """ Check if the user is an admin"""
    id = event.chat.id if type(event) is Message else event.message.chat.id
    admins = Bot().get_config()["admins"]
    return id in admins


@bot.on_message(filters.create(is_admin) & filters.command(commands))
async def on_command(client: Client, message: Message):
    current_command = message.command[0]

    if "start" == current_command or "menu" == current_command:
        await menu(message, False)
    if "blockimage" == current_command:
        if message.media is MessageMediaType.PHOTO:
            await block_image(message)
        else:
            await message.reply("This command can only be used in photos")

    if "blockall" == message.command[0]:
        await block_all(message)
    if "rmblockall" == message.command[0]:
        await rm_block_all(message)
    if "replaceall" == message.command[0]:
        await replace_all(message)
    if "rmreplaceall" == message.command[0]:
        await rm_replace_all(message)


@bot.on_message(filters.create(is_admin))
async def on_message(client: Client, message: Message):
    global answer_users
    user_id = message.chat.id

    if str(user_id) not in answer_users:
        answer_users[str(user_id)] = [False, None, None]
    if answer_users[str(user_id)][0]:
        answer_type = answer_users[str(user_id)][1]
        forwarder_id = answer_users[str(user_id)][2]

        if answer_type == "change_name":
            await change_name(message, forwarder_id, True)
        elif answer_type == "add_replace_word":
            await add_replace_word(message, forwarder_id, True)
        elif answer_type == "add_blocked_word":
            await add_blocked_word(message, forwarder_id, True)
        elif answer_type == "source_add":
            await source_add(message, forwarder_id, True)
        elif answer_type == "new_forwarder_target":
            await new_forwarder_get_target(message, True)
        elif answer_type == "new_forwarder_source":
            chat_id = list(forwarder_id.keys())[0]
            chat_name = forwarder_id[chat_id]
            await new_forwarder_get_source(message, chat_id, chat_name, True)


@bot.on_callback_query(filters.create(is_admin))
async def on_callback_query(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    message = callback_query.message
    user_id = message.chat.id
    answer_users[str(user_id)] = [False, None, None]

    if data == "menu":
        await menu(message)
    if data == "forwarders":
        await forwarders(message)
    if data.startswith("forwarder_"):
        id_hash = data.split("_")[-1]
        await forwarder(message, id_hash)
    if data.startswith("name_"):
        id_hash = data.split("_")[-1]
        await change_name(message, id_hash)
    if data.startswith("enabled_"):
        id_hash = data.split("_")[-1]
        await enable_forwarder(message, id_hash)
    if data.startswith("reply_"):
        id_hash = data.split("_")[-1]
        await toggle_reply(message, id_hash)
    if data.startswith("duplicated_text_"):
        id_hash = data.split("_")[-1]
        await toggle_duplicated_text(message, id_hash)
    if data.startswith("forwarding_mode_"):
        id_hash = data.split("_")[-1]
        await change_forwarding_mode(message, id_hash)
    if data.startswith("replace_words_"):
        id_hash = data.split("_")[-1]
        await change_replace_words(message, id_hash)
    if data.startswith("replace_delete_"):
        id_hash = data.split("_")[-1]
        word = data.split("_")[-2]
        await delete_replace_word(message, id_hash, word)
    if data.startswith("replace_add_"):
        id_hash = data.split("_")[-1]
        await add_replace_word(message, id_hash)
    if data.startswith("blocked_words_"):
        id_hash = data.split("_")[-1]
        await change_blocked_words(message, id_hash)
    if data.startswith("blocked_delete_"):
        id_hash = data.split("_")[-1]
        word = data.split("_")[-2]
        await delete_blocked_word(message, id_hash, word)
    if data.startswith("blocked_add_"):
        id_hash = data.split("_")[-1]
        await add_blocked_word(message, id_hash)
    if data.startswith("source_chats_"):
        id_hash = data.split("_")[-1]
        await source_chats(message, id_hash)
    if data.startswith("source_chat_"):
        id_hash = data.split("_")[-1]
        chat_id = data.split("_")[-2]
        await source_chat(message, id_hash, chat_id)
    if data.startswith("source_delete_"):
        id_hash = data.split("_")[-1]
        chat_id = data.split("_")[-2]
        await source_delete(message, id_hash, chat_id)
    if data.startswith("source_add_"):
        id_hash = data.split("_")[-1]
        await source_add(message, id_hash)
    if data.startswith("info_"):
        id_hash = data.split("_")[-1]
        await forwarder_info(message, id_hash)

    if data == "new":
        await new_forwarder_get_target(message)
    if data.startswith("delete_forwarder_"):
        id_hash = data.split("_")[-1]
        await delete_forwarder(message, id_hash, 1)
    if data.startswith("confirm_delete_forwarder_"):
        id_hash = data.split("_")[-1]
        await delete_forwarder(message, id_hash, 2)

    if data.startswith("send_text_only_"):
        id_hash = data.split("_")[-1]
        await toggle_send_text_only(message, id_hash)

    if data.startswith("translation_"):
        id_hash = data.split("_")[-1]
        await translation(message, id_hash)
    if data.startswith("toggle_translation_"):
        id_hash = data.split("_")[-1]
        await toggle_translation(message, id_hash)
    if data.startswith("toggle_show_original_"):
        id_hash = data.split("_")[-1]
        await toggle_show_original(message, id_hash)
    if data.startswith("translate_to_select_"):
        id_hash = data.split("_")[-1]
        await translate_to_select(message, id_hash)
    if data.startswith("translate_to_set_"):
        id_hash = data.split("_")[-1]
        lang_code = data.split("_")[-2]
        await translate_to_set(message, id_hash, lang_code)
    if data.startswith("translate_from_select_"):
        id_hash = data.split("_")[-1]
        await translate_from_select(message, id_hash)
    if data.startswith("translate_from_set_"):
        id_hash = data.split("_")[-1]
        lang_code = data.split("_")[-2]
        await translate_from_set(message, id_hash, lang_code)

    await callback_query.answer()


async def menu(message: Message, edit: bool = True) -> None:
    """ Create the menu. """
    # Create the keyboard
    keyboard = [
        [{"🔥 See forwarding": "forwarders"}],
        [{"➕ Create forwarding": "new"}],
    ]
    keyboard = await create_keyboard(keyboard)
    # Create the text
    text = "Welcome, what do you want to do?"

    # Send the message
    if edit:
        await message.edit(text, reply_markup=keyboard)
    else:
        await message.reply(text, reply_markup=keyboard)


async def forwarders(message: Message) -> None:
    """ Create the forwarders menu. """
    forwarders = (await forwardings.get_config())["forwarders"]
    forwarders = sorted(forwarders, key=lambda x: x["name"])

    # Create the keyboard
    keyboard = []
    for forwarder in forwarders:
        name = ("🟢 " if forwarder["enabled"] else "🔴 ") + forwarder["name"]
        forwarder_id = f"forwarder_{forwarder['target']}"
        keyboard.append([{name: forwarder_id}])
    keyboard.append([{"◀️ Back": "menu"}])
    keyboard = await create_keyboard(keyboard)
    # Create the text
    text = "Select a forwarding"

    # Send the message
    await message.edit(text, reply_markup=keyboard)


async def forwarder(message: Message, forwarder_id: str) -> None:
    """ Forward the message to the forwarder. """
    # Get the forwarder
    forwarder = await forwardings.get_forwarder(forwarder_id)

    name = f"✏️ Name: {forwarder['name']}"
    enabled = "🟢 Enabled" if forwarder["enabled"] else "🔴 Disabled"
    reply = "🔁 Reply: on" if forwarder["reply"] else "🔁 Reply: off"
    duplicated_text = ("🔄 Duplicated text: on" if forwarder["duplicated_text"]
                       else "🔄 Duplicated text: off")
    forwarding_mode = "↪️ Forwarding mode: "
    forwarding_mode += ("copy" if forwarder["forwarding_mode"] == "copy" else
                        "forward")
    replace_words = "🔖 Words to replace"
    blocked_words = "🚫 Blocked words"
    source_chats = "👁 Source chats"

    send_text_only = ("🔄 Send text only: on" if forwarder["send_text_only"]
                      else "🔄 Send text only: off")
    translation = "🗣️ Translation"

    # Create the keyboard
    keyboard = [
        [{name: f"name_{forwarder_id}"}],
        [{enabled: f"enabled_{forwarder_id}"}],
        [{reply: f"reply_{forwarder_id}"}],
        [{duplicated_text: f"duplicated_text_{forwarder_id}"}],
        [{forwarding_mode: f"forwarding_mode_{forwarder_id}"}],
        [{replace_words: f"replace_words_{forwarder_id}"}],
        [{blocked_words: f"blocked_words_{forwarder_id}"}],
        [{source_chats: f"source_chats_{forwarder_id}"}],
        [{send_text_only: f"send_text_only_{forwarder_id}"}],
        [{translation: f"translation_{forwarder_id}"}],
        [{"ℹ️ Information": f"info_{forwarder_id}"}],
        [{"🗑️ Delete": f"delete_forwarder_{forwarder_id}"}],
        [{"◀️ Back": "forwarders"}]
    ]
    if forwarder["forwarding_mode"] != "copy":
        keyboard.pop(5)

    text = "Forwarding settings"

    # Send the message
    keyboard = await create_keyboard(keyboard)
    await message.edit(text, reply_markup=keyboard)


async def change_name(message: Message, forwarder_id: str, change=False):
    """ Change the name of the forwarder. """
    user_id = message.chat.id

    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)

    if not change:
        # Create the keyboard
        keyboard = [
            [{"◀️ Back": f"forwarder_{forwarder_id}"}]
        ]
        keyboard = await create_keyboard(keyboard)
        # Create the text
        text = "Enter the new name"

        # Send the message
        await message.edit(text, reply_markup=keyboard)

        answer_users[str(user_id)] = [True, "change_name", forwarder_id,
                                      message]
    else:
        message_edit = answer_users[str(user_id)][3]
        answer = message.text
        forwarder_dict["name"] = answer
        await forwardings.update_forwarder(forwarder_dict)
        await forwarder(message_edit, forwarder_id)
        answer_users[str(user_id)] = [False, None, None, None]


async def enable_forwarder(message: Message, forwarder_id: str):
    """ Enable the forwarder. """
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)

    forwarder_dict["enabled"] = not forwarder_dict["enabled"]
    await forwardings.update_forwarder(forwarder_dict)
    await forwarder(message, forwarder_id)


async def toggle_reply(message: Message, forwarder_id: str):
    """ Toggle the reply of the forwarder. """
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)

    forwarder_dict["reply"] = not forwarder_dict["reply"]
    await forwardings.update_forwarder(forwarder_dict)
    await forwarder(message, forwarder_id)


async def toggle_duplicated_text(message: Message, forwarder_id: str):
    """ Toggle the duplicated text of the forwarder. """
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)

    forwarder_dict["duplicated_text"] = not forwarder_dict["duplicated_text"]
    await forwardings.update_forwarder(forwarder_dict)
    await forwarder(message, forwarder_id)


async def change_forwarding_mode(message: Message, forwarder_id: str):
    """ Change the forwarding mode of the forwarder. """
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)

    if forwarder_dict["forwarding_mode"] == "copy":
        forwarder_dict["forwarding_mode"] = "forward"
    else:
        forwarder_dict["forwarding_mode"] = "copy"
    await forwardings.update_forwarder(forwarder_dict)
    await forwarder(message, forwarder_id)


async def change_replace_words(message: Message, forwarder_id: str):
    """ Change the replace words of the forwarder. """
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)

    # Create the keyboard
    keyboard = []
    for word, value in forwarder_dict["replace_words"].items():
        word_md5 = await md5(word)
        keyboard.append([
            {f"{word} -> {value}":
             f"replace_delete_{word_md5}_{forwarder_id}"}])
    keyboard.append([{"➕ Add": f"replace_add_{forwarder_id}"}])
    keyboard.append([{"◀️ Back": f"forwarder_{forwarder_id}"}])
    keyboard = await create_keyboard(keyboard)

    # Create the text
    text = "Add a word to replace.\n"
    text += "To delete a word, click on its name."

    # Send the message
    await message.edit(text, reply_markup=keyboard)


async def delete_replace_word(message: Message, forwarder_id: str,
                              word_md5: str):
    """ Delete a replace word from the forwarder. """
    forwarder = await forwardings.get_forwarder(forwarder_id)

    # Create the keyboard
    keyboard = []
    for source_id, source_name in forwarder["source"].items():
        name = f"{source_name} ({source_id})"
        keyboard.append([{name: f"source_chat_{source_id}"}])
    keyboard.append([{"◀️ Back": f"forwarder_{forwarder_id}"}])
    keyboard = await create_keyboard(keyboard)
    # Create the text
    text = "Select a source chat."

    # Send the message
    await message.edit(text, reply_markup=keyboard)
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)

    # Find the word by its md5
    for word in forwarder_dict["replace_words"].keys():
        if await md5(word) == word_md5:
            break

    # Delete the word
    del forwarder_dict["replace_words"][word]
    await forwardings.update_forwarder(forwarder_dict)
    await change_replace_words(message, forwarder_id)


async def add_replace_word(message: Message, forwarder_id: str, change=False):
    """ Add a replace word to the forwarder. """
    user_id = message.chat.id
    # Create the keyboard
    keyboard = [
        [{"◀️ Back": f"replace_words_{forwarder_id}"}]
    ]
    keyboard = await create_keyboard(keyboard)

    if not change:
        # Create the text
        text = "Enter the word to be replaced in this format:\n"
        text += "`word>replaced_word`\n\n"
        text += "You can add several replacements at the same time, just\n"
        text += "split them with a line break.\n\n"
        text += "Example:\n"
        text += "`word1>replaced_word1\n"
        text += "word2>replaced_word2\n"
        text += "word3>replaced_word3`"

        # Send the message
        await message.edit(text, reply_markup=keyboard)

        answer_users[str(user_id)] = [True, "add_replace_word", forwarder_id,
                                      message]
    else:
        message_edit = answer_users[str(user_id)][3]
        answer = message.text

        # Check if has the right format
        if ">" not in answer:
            text = "**Error:** The format is not correct.\n\n"
            text += f"**Text entered:** ```{answer}```"
            await message_edit.edit(text, reply_markup=keyboard)
            return

        # Get the words and the values to replace
        replaces = answer.split("\n")
        replaces = [replace.split(">") for replace in replaces]

        # Get the forwarder
        forwarder_dict = await forwardings.get_forwarder(forwarder_id)

        # Add the words and the values to replace
        for replace in replaces:
            word, value = replace
            forwarder_dict["replace_words"][word] = value

        # Update the forwarder
        await forwardings.update_forwarder(forwarder_dict)
        await change_replace_words(message_edit, forwarder_id)
        answer_users[str(user_id)] = [False, None, None, None]


async def change_blocked_words(message: Message, forwarder_id: str):
    """ Change the blocked words of the forwarder. """
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)

    # Create the keyboard
    keyboard = []
    for word in forwarder_dict["blocked_words"]:
        word_md5 = await md5(word)
        keyboard.append([
            {f"{word}": f"blocked_delete_{word_md5}_{forwarder_id}"}])
    keyboard.append([{"➕ Add": f"blocked_add_{forwarder_id}"}])
    keyboard.append([{"◀️ Back": f"forwarder_{forwarder_id}"}])
    keyboard = await create_keyboard(keyboard)

    # Create the text
    text = "Add a word to replace.\n"
    text += "To delete a word, click on its name."

    # Send the message
    await message.edit(text, reply_markup=keyboard)


async def delete_blocked_word(message: Message, forwarder_id: str,
                              word_md5: str):
    """ Delete a blocked word from the forwarder. """
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)

    # Find the word by its md5
    for word in forwarder_dict["blocked_words"]:
        if await md5(word) == word_md5:
            break

    # Delete the word
    forwarder_dict["blocked_words"].remove(word)
    await forwardings.update_forwarder(forwarder_dict)
    await change_blocked_words(message, forwarder_id)


async def add_blocked_word(message: Message, forwarder_id: str, change=False):
    """ Add a blocked word to the forwarder. """
    user_id = message.chat.id
    # Create the keyboard
    keyboard = [
        [{"◀️ Back": f"blocked_words_{forwarder_id}"}]
    ]
    keyboard = await create_keyboard(keyboard)

    if not change:
        # Create the text
        text = "Enter the word you want to block.\n\n"
        text += "You can add several words to block at the same time, \n"
        text += "just split them with a line break.\n\n"
        text += "Example:\n"
        text += "`word1\nword2\nword3`"

        # Send the message
        await message.edit(text, reply_markup=keyboard)

        answer_users[str(user_id)] = [True, "add_blocked_word", forwarder_id,
                                      message]
    else:
        message_edit = answer_users[str(user_id)][3]
        answer = message.text

        # Get the words and the values to blocked
        blockeds = answer.split("\n")

        # Get the forwarder
        forwarder_dict = await forwardings.get_forwarder(forwarder_id)

        # Add the words and the values to blocked
        for blocked in blockeds:
            forwarder_dict["blocked_words"].append(blocked)

        # Update the forwarder
        await forwardings.update_forwarder(forwarder_dict)
        await change_blocked_words(message_edit, forwarder_id)
        answer_users[str(user_id)] = [False, None, None, None]


async def source_chats(message: Message, forwarder_id) -> None:
    """ Create the forwarders menu. """
    forwarder = await forwardings.get_forwarder(forwarder_id)

    # Create the keyboard
    keyboard = []
    for source_id, source_name in forwarder["source"].items():
        name = f"{source_name}"
        keyboard.append([{name: f"source_chat_{source_id}_{forwarder_id}"}])
    keyboard.append([{"➕ Add": f"source_add_{forwarder_id}"}])
    keyboard.append([{"◀️ Back": f"forwarder_{forwarder_id}"}])
    keyboard = await create_keyboard(keyboard)
    # Create the text
    text = "Select a source chat."

    # Send the message
    await message.edit(text, reply_markup=keyboard)


async def source_chat(message: Message, forwarder_id: str, source_id: str):
    """ Forward the message to the forwarder. """
    # Create the keyboard
    keyboard = [
        [{"🗑️ Delete": f"source_delete_{source_id}_{forwarder_id}"}],
        [{"◀️ Back": f"source_chats_{forwarder_id}"}]
    ]

    text = "Source chat settings."
    text += await get_chat_info(source_id)

    # Update the forwarders name
    if re.search(r"\*\*Name:\*\* (.+)", text):
        name = re.search(r"\*\*Name:\*\* (.+)", text).group(1)
        forwarder_dict = await forwardings.get_forwarder(forwarder_id)
        forwarder_dict["source"][source_id] = name
        await forwardings.update_forwarder(forwarder_dict)

    # Send the message
    keyboard = await create_keyboard(keyboard)
    await message.edit(text, reply_markup=keyboard)


async def source_delete(message: Message, forwarder_id: str, source_id: str):
    """ Delete the source chat. """
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)

    # Delete the source chat
    del forwarder_dict["source"][source_id]
    await forwardings.update_forwarder(forwarder_dict)
    await source_chats(message, forwarder_id)


async def source_add(message: Message, forwarder_id: str, change=False):
    """ Add the source chat. """
    user_id = message.chat.id
    # Create the keyboard
    keyboard = [
        [{"◀️ Back": f"source_chats_{forwarder_id}"}]
    ]
    keyboard = await create_keyboard(keyboard)

    if not change:
        # Create the text
        text = "Enter the source chat.\n\n"
        text += "You can add chats in several ways:\n\n"
        text += "**-Entering the chat ID**\n"
        text += "`628910404\n628910400`\n\n"
        text += "**-Entering the chat username**\n"
        text += "`@Nunnito\n@Python`\n\n"
        text += "**-Entering a link from a chat message**\n"
        text += "`https://t.me/c/1165316653/1815937\nhttps://t.me/python/1234`"
        text += "\n\n**-Forwarding a chat message**\n"

        # Send the message
        await message.edit(text, reply_markup=keyboard)

        answer_users[str(user_id)] = [True, "source_add", forwarder_id,
                                      message]
    else:
        # Message to be edited
        message_edit = answer_users[str(user_id)][3]
        # Get the forwarder
        forwarder_dict = await forwardings.get_forwarder(forwarder_id)

        # Get all the chats ids
        chats_ids, invalid_ids = await get_chats_id(message)

        # Add the chats and the values to source chat
        for chat_id, name in chats_ids.items():
            forwarder_dict["source"][chat_id] = name

        # Create the text
        text = ""
        if chats_ids:
            text = "The following source chats have been added:\n"
            for chat_id, name in chats_ids.items():
                text += f"**{name}**\n"
        if invalid_ids:
            text += "\n\nThe following chats have not been added:\n"
            for chat_id in invalid_ids:
                text += f"**{chat_id}**\n"

        # Update the forwarder
        await forwardings.update_forwarder(forwarder_dict)
        # Send the message
        await message_edit.edit(text, reply_markup=keyboard)
        answer_users[str(user_id)] = [False, None, None, None]


async def forwarder_info(message: Message, forwarder_id: str):
    """ Create the forwarders menu. """
    # Create the keyboard
    keyboard = [
        [{"◀️ Back": f"forwarder_{forwarder_id}"}]
    ]
    keyboard = await create_keyboard(keyboard)

    # Create the text
    text = await get_chat_info(forwarder_id)

    # Send the message
    await message.edit(text, reply_markup=keyboard)


async def new_forwarder_get_target(message: Message, change=False):
    """ Create a new forwarder. """
    user_id = message.chat.id
    # Create the keyboard
    keyboard = [
        [{"◀️ Back": "menu"}]
    ]
    keyboard = await create_keyboard(keyboard)

    if not change:
        # Create the text
        text = "Enter the target chat.\n\n"
        text += "You can add chats in several ways:\n\n"
        text += "**-Entering the chat ID**\n"
        text += "`628910404`\n\n"
        text += "**-Entering the chat username**\n"
        text += "`@Nunnito`\n\n"
        text += "**-Entering a link from a chat message**\n"
        text += "`https://t.me/c/1165316653/1815937`"
        text += "\n\n**-Forwarding a chat message**\n"

        # Send the message
        await message.edit(text, reply_markup=keyboard)

        answer_users[str(user_id)] = [True, "new_forwarder_target", None,
                                      message]
    else:
        # Message to be edited
        message_edit = answer_users[str(user_id)][3]

        # Get all the chats ids
        chats_ids, invalid_ids = await get_chats_id(message)
        if not chats_ids:
            text = "The target chat is invalid."
            await message_edit.edit(text, reply_markup=keyboard)
            answer_users[str(user_id)] = [False, None, None, None]
            return
        elif await forwardings.get_forwarder(list(chats_ids.keys())[0]):
            text = "The target chat is already in use."
            await message_edit.edit(text, reply_markup=keyboard)
            answer_users[str(user_id)] = [False, None, None, None]
            return
        else:
            # Get the chat id
            chat_id = list(chats_ids.keys())[0]
            # Get the chat name
            chat_name = chats_ids[chat_id]

            await new_forwarder_get_source(message_edit, chat_id, chat_name)


async def new_forwarder_get_source(message: Message, forwarder_id: str,
                                   forwarder_name: str, change=False):
    """ Create a new forwarder. """
    user_id = message.chat.id
    # Create the keyboard
    keyboard = [
        [{"◀️ Back": "forwarders"}]
    ]
    keyboard = await create_keyboard(keyboard)

    if not change:
        # Create the text
        text = "Excellent, now enter the source chat.\n\n"
        text += "It is added in a very similar way to the target chat, "
        text += "the only difference is that more that one cam be added.\n\n"
        text += "You can add chats in several ways:\n\n"
        text += "**-Entering the chat ID**\n"
        text += "`628910404\n628910400`\n\n"
        text += "**-Entering the chat username**\n"
        text += "`@Nunnito\n@Python`\n\n"
        text += "**-Entering a link from a chat message**\n"
        text += "`https://t.me/c/1165316653/1815937\nhttps://t.me/python/1234`"
        text += "\n\n**-Forwarding a chat message**\n"

        # Send the message
        await message.edit(text, reply_markup=keyboard)

        answer_users[str(user_id)] = [True, "new_forwarder_source",
                                      {forwarder_id: forwarder_name}, message]
    else:
        # Message to be edited
        message_edit = answer_users[str(user_id)][3]

        # Get all the chats ids
        sources, invalid_ids = await get_chats_id(message)
        if not sources:
            text = "The source chat is invalid."
            await message_edit.edit(text, reply_markup=keyboard)
            answer_users[str(user_id)] = [False, None, None, None]
            return

        # Create the text
        text = ""
        if sources:
            text = "The following source chats have been added:\n"
            for chat_id, name in sources.items():
                text += f"**{name}**\n"
        if invalid_ids:
            text += "\n\nThe following chats have not been added:\n"
            for chat_id in invalid_ids:
                text += f"**{chat_id}**\n"

        await forwardings.add_forwarder(forwarder_name, forwarder_id, sources)
        # Send the message
        await message_edit.edit(text, reply_markup=keyboard)
        answer_users[str(user_id)] = [False, None, None, None]


async def delete_forwarder(message: Message, forwarder_id: str, step=1):
    """ Delete a forwarder. """
    if step == 1:
        # Create the keyboard
        keyboard = [
            [{"Yes, sure": f"confirm_delete_forwarder_{forwarder_id}"}],
            [{"No, cancel": f"forwarder_{forwarder_id}"}]
        ]
        keyboard = await create_keyboard(keyboard)

        # Create the text
        text = "Are you sure you want to delete it?"
        text += await get_chat_info(forwarder_id)

        # Send the message
        await message.edit(text, reply_markup=keyboard)
    elif step == 2:
        # Delete the forwarder
        await forwardings.remove_forwarder(forwarder_id)

        # Return to the forwarders menu
        await forwarders(message)


async def toggle_send_text_only(message: Message, forwarder_id: str):
    """ Toggle send text only """
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)

    forwarder_dict["send_text_only"] = not forwarder_dict["send_text_only"]
    await forwardings.update_forwarder(forwarder_dict)
    await forwarder(message, forwarder_id)


async def translation(message: Message, forwarder_id: str):
    """ Translation system """
    # Get to and from languages
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)
    enable = forwarder_dict["translate"]
    to_lang = REV_LANGS[forwarder_dict["translate_to"]]
    from_lang = REV_LANGS[forwarder_dict["translate_from"]]
    show_original = forwarder_dict["translate_show_original"]

    # Create the keyboard
    keyboard = [
        [{"🟢 Enabled" if enable else "🔴 Disabled":
          f"toggle_translation_{forwarder_id}"}],
        [{f"🔄 Show original: {'Yes' if show_original else 'No'}":
          f"toggle_show_original_{forwarder_id}"}],
        [{f"↪️ To: {to_lang}": f"translate_to_select_{forwarder_id}"}],
        [{f"↩️ From: {from_lang}": f"translate_from_select_{forwarder_id}"}],
        [{"◀️ Back": f"forwarder_{forwarder_id}"}]
    ]

    # Create the keyboard
    keyboard = await create_keyboard(keyboard)
    # Create the text
    text = "Configure the translation"

    # Send the message
    await message.edit(text, reply_markup=keyboard)


async def toggle_translation(message: Message, forwarder_id: str):
    """ Toggle the translation of the forwarder. """
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)

    forwarder_dict["translate"] = not forwarder_dict["translate"]
    await forwardings.update_forwarder(forwarder_dict)
    await translation(message, forwarder_id)


async def toggle_show_original(message: Message, forwarder_id: str):
    """ Toggle the show original of the forwarder. """
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)

    forwarder_dict["translate_show_original"] = not forwarder_dict[
        "translate_show_original"]
    await forwardings.update_forwarder(forwarder_dict)
    await translation(message, forwarder_id)


async def translate_to_select(message: Message, forwarder_id: str):
    """ Select the to language. """
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)

    # Create the keyboard
    keyboard = []
    for lang, lang_code in LANGS.items():
        if lang_code == "auto":
            continue
        elif lang_code == forwarder_dict["translate_to"]:
            btn_text = f"🟢 {lang}"
        else:
            btn_text = f"🔴 {lang}"
        btn_data = {btn_text: f"translate_to_set_{lang_code}_{forwarder_id}"}
        keyboard.append([btn_data])
    keyboard.append([{"◀️ Back": f"translation_{forwarder_id}"}])

    # Create the keyboard
    keyboard = await create_keyboard(keyboard)
    # Create the text
    text = "Select the language to translate to"

    # Send the message
    await message.edit(text, reply_markup=keyboard)


async def translate_to_set(message: Message, forwarder_id: str, lang: str):
    """ Set the to language. """
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)
    forwarder_dict["translate_to"] = lang

    await forwardings.update_forwarder(forwarder_dict)
    await translate_to_select(message, forwarder_id)


async def translate_from_select(message: Message, forwarder_id: str):
    """ Select the from language. """
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)

    # Create the keyboard
    keyboard = []
    for lang, lang_code in LANGS.items():
        if lang_code == forwarder_dict["translate_from"]:
            btn_text = f"🔴 {lang}"
        else:
            btn_text = f"🟢 {lang}"
        btn_data = {btn_text: f"translate_from_set_{lang_code}_{forwarder_id}"}
        keyboard.append([btn_data])
    keyboard.append([{"◀️ Back": f"translation_{forwarder_id}"}])

    # Create the keyboard
    keyboard = await create_keyboard(keyboard)
    # Create the text
    text = "Select the language to translate from"

    # Send the message
    await message.edit(text, reply_markup=keyboard)


async def translate_from_set(message: Message, forwarder_id: str, lang: str):
    """ Set the from language. """
    # Get the forwarder
    forwarder_dict = await forwardings.get_forwarder(forwarder_id)
    forwarder_dict["translate_from"] = lang

    await forwardings.update_forwarder(forwarder_dict)
    await translate_from_select(message, forwarder_id)


async def create_keyboard(buttons: list) -> InlineKeyboardMarkup:
    """ Create a keyboard with the given buttons.

    Parameters
    ----------
    buttons : list
        A list with the buttons to create.
        The keys are the button text and the values are the callback data.

    Returns
    -------
    InlineKeyboardMarkup
        The keyboard with the given buttons.
    """
    keyboard = []
    # Create the buttons
    for i, button_index in enumerate(buttons):
        keyboard.append([])
        for button in button_index:
            for key, value in button.items():
                keyboard[i].append(InlineKeyboardButton(key, value))

    return InlineKeyboardMarkup(keyboard)


async def get_chat_info(chat_id: str) -> str:
    # Create the text
    try:
        chat_info = await user.get_chat(chat_id)
        if chat_info.type is ChatType.CHANNEL or\
                chat_info.type is ChatType.SUPERGROUP:
            chat_type = ("Channel" if chat_info.type is ChatType.CHANNEL
                         else "Group")
            text = f"\n\n**Name:** {chat_info.title}"
            text += f"\n**ID:** `{chat_info.id}`"
            text += f"\n**Type:** {chat_type}"
            if chat_info.username:
                text += f"\n**Username:** @{chat_info.username}"
            text += f"\n**Members count:** {chat_info.members_count}"
            text += "\n**Protected content:** "
            text += "Yes" if chat_info.has_protected_content else "No"
        elif chat_info.type is ChatType.PRIVATE:
            text = f"\n\n**Name:** {chat_info.first_name}"
            if chat_info.last_name:
                text += f" {chat_info.last_name}"
            text += f"\n**ID:** `{chat_info.id}`"
            text += "\n**Type:** Private"
            if chat_info.username:
                text += f"\n**Username:** @{chat_info.username}"
        elif chat_info.type is ChatType.BOT:
            text = f"\n\n**Name:** {chat_info.first_name}"
            text += f"\n**ID:** `{chat_info.id}`"
            text += "\n**Type:** Bot"
            text += f"\n**Username:** @{chat_info.username}"
    except (ChannelInvalid, ChannelPrivate, PeerIdInvalid,
            UsernameNotOccupied):
        text = "\n\n**Error:** Chat information could not be obtained.\n"
        text += "**Reason:** The chat does not exist or you are not in it.\n"
        text += f"**ID:** `{chat_id}`"

    return text


async def get_chats_id(message: Message) -> list | bool:
    """ Get the chat IDs from the given chats. """
    if message.forward_from_chat:
        name = message.forward_from_chat.title
        chats_ids = {message.forward_from_chat.id: name}
        return chats_ids, None
    elif message.forward_from:
        name = message.forward_from.first_name
        if message.forward_from.last_name:
            name += f" {message.forward_from.last_name}"
        chats_ids = {message.forward_from.id: name}
        return chats_ids, None
    else:
        chats_ids = {}
        invalid_ids = []
        chats = message.text.split("\n")
        for chat in chats:
            chat_id = None
            chat_id_url = re.search(r"https://t.me/c/(\d+)/\d+", chat)
            chat_username_url = re.search(r"https://t.me/(\w+)/\d+", chat)
            is_username = re.search(r"^@?\w+", chat)
            if chat_id_url:
                chat_id = int(f"-100{chat_id_url.group(1)}")
            elif chat_username_url:
                chat_id = chat_username_url.group(1)
            elif chat.isnumeric() or chat.startswith("-"):
                chat_id = int(chat)
            elif is_username:
                chat_id = is_username.group(0)
            else:
                invalid_ids.append(chat)

            if chat_id:
                try:
                    chat_info = await user.get_chat(chat_id)
                    chat_id = str(chat_info.id)
                    if chat_info.title:
                        name = chat_info.title
                    else:
                        name = chat_info.first_name
                        name += f" {chat_info.last_name}" if\
                            chat_info.last_name else ""
                    chats_ids[chat_id] = name
                except (ChannelInvalid, ChannelPrivate, PeerIdInvalid,
                        UsernameNotOccupied, UsernameInvalid):
                    invalid_ids.append(chat_id)

        return chats_ids, invalid_ids


async def block_image(message: Message) -> None:
    """ Add blocked images to all the forwarders. """
    # Set name to current timestamp
    name = datetime.datetime.now().timestamp()
    # Download the image
    image_path = await message.download(config_dir/"blocked_img"/f"{name}.jpg")

    # Add the image to blocked images
    await forwardings.add_blocked_image(image_path)

    # Reply
    await message.reply_text("Image blocked!")


async def block_all(message: Message) -> None:
    """ Add blocked words to all the forwarders. """
    # Get the forwarders
    forwarders_ids = await forwardings.get_forwardings()

    # If the blocked words are empty
    if message.text.replace("/blockall", "").strip() == "":
        await message.reply_text("Blocked words can't be empty!")
        return

    # Get the blocked words
    blocked_words = message.text.replace("/blockall", "").strip().split("\n")

    # Add the blocked words to all the forwarders
    for forwarder_id in forwarders_ids:
        forwarder_dict = await forwardings.get_forwarder(str(forwarder_id))

        # Add the blocked words to the forwarder
        for blocked_word in blocked_words:
            if blocked_word not in forwarder_dict["blocked_words"]:
                forwarder_dict["blocked_words"].append(blocked_word)

        await forwardings.update_forwarder(forwarder_dict)

    await message.reply_text("Word blocking added to all the forwarders.")


async def rm_block_all(message: Message) -> None:
    """ Remove blocked words from all the forwarders. """
    # Get the forwarders
    forwarders_ids = await forwardings.get_forwardings()

    # If the blocked words are empty
    if message.text.replace("/rmblockall", "").strip() == "":
        await message.reply_text("Blocked words can't be empty!")
        return

    # Get the blocked words
    blocked_words = message.text.replace("/rmblockall", "").strip().split("\n")

    # Remove the blocked words from all the forwarders
    for forwarder_id in forwarders_ids:
        forwarder_dict = await forwardings.get_forwarder(str(forwarder_id))

        for blocked_word in blocked_words:
            if blocked_word in forwarder_dict["blocked_words"]:
                forwarder_dict["blocked_words"].remove(blocked_word)

        await forwardings.update_forwarder(forwarder_dict)

    await message.reply_text("Word blocking removed from all the forwarders.")


async def replace_all(message: Message) -> None:
    """ Add replaced words to all the forwarders. """
    # Get the forwarders
    forwarders_ids = await forwardings.get_forwardings()

    # If the replaced words are empty
    if message.text.replace("/replaceall", "").strip() == "":
        await message.reply_text("Replaced words can't be empty!")
        return

    # Get the replaced words
    replaced_words = message.text.replace("/replaceall", "").strip()

    # Check if has the right format
    if ">" not in replaced_words:
        text = "**Error:** The format of the replaced words is incorrect.\n\n"
        text += f"**Introduced text:** `{replaced_words}`"
        await message.reply_text(text)
        return

    # Get the words and the values to replace
    replaces = replaced_words.split("\n")
    replaces = [replace.split(">") for replace in replaces]

    # Add the replaced words to all the forwarders
    for forwarder_id in forwarders_ids:
        forwarder_dict = await forwardings.get_forwarder(str(forwarder_id))

        for replace in replaces:
            word, value = replace
            forwarder_dict["replace_words"][word] = value

        await forwardings.update_forwarder(forwarder_dict)

    await message.reply_text("Word replacement added to all the forwarders.")


async def rm_replace_all(message: Message) -> None:
    """ Remove replaced words from all the forwarders. """
    # Get the forwarders
    forwarders_ids = await forwardings.get_forwardings()

    # If the replaced words are empty
    if message.text.replace("/rmreplaceall", "").strip() == "":
        await message.reply_text("Replaced words can't be empty!")
        return

    # Get the replaced words
    replaced_words = message.text.replace("/rmreplaceall", "")\
                                 .strip().split("\n")

    # Remove the replaced words from all the forwarders
    for forwarder_id in forwarders_ids:
        forwarder_dict = await forwardings.get_forwarder(str(forwarder_id))

        for replace in replaced_words:
            if replace in forwarder_dict["replace_words"]:
                forwarder_dict["replace_words"].pop(replace)

        await forwardings.update_forwarder(forwarder_dict)

    await message.reply_text(
        "Word replacement removed from all the forwarders.")


if not Path(config_dir/"user.session").exists():
    logger.info("Log-in with your phone number")
user.start()

# Iter over all chats
for dialog in user.get_dialogs():
    pass

Bot().add_admin(user.get_me().id)  # Add user id to admin database
if not Path(config_dir/"bot.session").exists():
    logger.info("Log-in with you bot token")
bot.start()
logger.info("Bot started")
logger.info(f"Bot username: @{bot.get_me().username}")
idle()
bot.stop()
