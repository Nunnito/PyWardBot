# TODO: whitelist words or whitelist patterns to only capture messages that
# match with a pattern or contains a word.
# TODO: make a filter config to only capture messages that contains selected
# media. Ex: Select to only forward messages with photos, videos, audios, etc.
# TODO: Blacklist regex pattern?
# TODO: Make a filter to only capture types of messages.
# Ex: Only forwarded messages, edited messages, deleted messages, etc.
# TODO: Make a filter to only send media messages, skipping text and viceversa
# Ex: If a photo with a caption is sent, only send the photo, not the caption
# TODO: Toggle message removal from the chat.

import os
import re

from pyrogram import Client, filters
from pyrogram.types import (Message, InputMediaPhoto, InputMediaVideo,
                            InputMediaAudio, InputMediaDocument,
                            InputMediaAnimation)
from pyrogram.errors.exceptions.bad_request_400 import (MediaInvalid,
                                                        MessageIdInvalid,
                                                        MessageNotModified)

from config import Bot, Forwarding, MessagesIDs
from logger import logger

# Load the bot configuration
bot_config = Bot().get_config()


# Set up the Telegram client
API_ID = bot_config["api_id"]
API_HASH = bot_config["api_hash"]

user = Client("user", API_ID, API_HASH)
current_media_group = None  # Current media group ID

Messages = MessagesIDs()
Forwardings = Forwarding()


async def is_forwarder(filter, client: Client, message: Message):
    """Check if the chat id is in the forwarding list"""
    id = message.chat.id
    forwarding_ids = await Forwardings.get_forwarding_ids()
    return id in forwarding_ids


async def replace_words(target: dict, text: str):
    """Replace words and select text with regex"""
    words = target["replace_words"]
    if text is None:
        logger.debug("Text is None, returning an empty string")
        return ""

    logger.debug(f"Replace mode is: {target['replace_words_mode']}")
    for word in words:
        # Replace only boundary words matches
        if target["replace_words_mode"] == "word_boundary_match":
            sub_word = word
            # If the word starts with
            if word[0] in ["@", "#", "$"]:
                sub_word = word[1:]
                symbol = word[0]
                pattern = r"[%s]\b%s\b" % (symbol, sub_word)
            # If the word ends with
            elif word[-1] in ["@", "#", "$"]:
                sub_word = word[:-1]
                symbol = word[-1]
                pattern = r"\b%s[%s]" % (sub_word, symbol)
            else:
                pattern = r"\b%s\b" % word
            text = re.sub(pattern, words[word], text, flags=re.I)
        # Replace any match
        else:
            text = re.sub(word, words[word], text, flags=re.I)

    # Select a match with regex
    for pattern in target["patterns"]:
        if re.search(pattern, text, re.DOTALL):
            logger.debug(f"Pattern '{pattern}' found in text")
            text = re.search(pattern, text, re.DOTALL)
            text = text.group(target["patterns"][pattern])
            break

    logger.debug("Returning text")
    return text


async def forward_message(message: Message, target: dict, edited=False,
                          media_group=False):
    """Forward a message to a target"""
    msg_ids = await Messages.get_message_ids()
    target = str(target["target"])
    source = str(message.chat.id)
    ids = message.message_id

    if media_group:
        messages = await user.get_media_group(source, message.message_id)
        ids = [msg.message_id for msg in messages]

    if edited:
        origin_edit_id = str(message.message_id)
        edit_id = -1
        can_edit = True
        # If the message id is in the list of messages ids
        if target in msg_ids and source in msg_ids[target] and origin_edit_id\
                in msg_ids[target][source]:
            edit_id = msg_ids[target][source][origin_edit_id]
        else:
            can_edit = False
            logger.error("The message cannot be deleted, because it does " +
                         "not exist in the target chat")
        if media_group and can_edit:
            edit_id = [msg_ids[target][source][str(id)] for id in ids]
        if edit_id != -1:
            deleted_id = await user.get_messages(target, edit_id)
            # Remove message, to resend it already edited
            if media_group:
                await on_deleted_message(user, deleted_id)
            else:
                await on_deleted_message(user, [deleted_id])
        await user.delete_messages(target, edit_id)

    if not message.chat.has_protected_content:
        msg = await user.forward_messages(target, source, ids)
        from_user = message.chat.title if message.chat.title else\
            message.chat.first_name
        to_user = msg.chat.title if msg.chat.title else msg.chat.first_name
        logger.info(f"Forwarding message from {from_user} to {to_user}")
    else:
        logger.error("The chat is restricted from forwarding messages")
        return

    if media_group:
        for old_msg, new_msg in zip(messages, msg):
            await Messages.add_message_id(target, source, old_msg.message_id,
                                          new_msg.message_id)
    else:
        await Messages.add_message_id(target, source, message.message_id,
                                      msg.message_id)

    if media_group and edited:
        await on_media_group_edited(user, msg[0])
    elif media_group:
        await on_media_group(user, msg[0])
    else:
        await on_new_message(user, msg)


async def copy_message(message: Message, target: dict, edited=False,
                       pinned=False, reply=False, media_group=False):
    """Copy a message to a target"""
    msg_ids = await Messages.get_message_ids()
    forwarder = target
    target = str(target["target"])
    source = str(message.chat.id)
    from_user = message.chat.title if message.chat.title else\
        message.chat.first_name

    if pinned:
        origin_pinned_id = str(message.pinned_message.message_id)
        pinned_id = -1
        to_user = await user.get_chat(target)
        to_user = to_user.title if to_user.title else to_user.first_name

        # If the message id is in the list of messages ids
        if target in msg_ids and source in msg_ids[target] and\
                origin_pinned_id in msg_ids[target][source]:
            pinned_id = msg_ids[target][source][origin_pinned_id]
        try:
            await user.pin_chat_message(target, pinned_id, both_sides=True)
            logger.info(f"Pinning message from {from_user} to {to_user}")
        except MessageIdInvalid:
            logger.error("The message cannot be pinned, because it does not " +
                         "exist in the target chat")
        return

    elif media_group:
        messages = await user.get_media_group(source, message.message_id)
        media_input = []
        downloaded_media = []

        for msg_media in messages:
            text = await replace_words(forwarder, msg_media.caption)
            entities = msg_media.caption_entities
            # If the chat has protected content, download the media to send it
            if msg_media.chat.has_protected_content:
                path = await msg_media.download()
            # If the chat has not protected content, get the file_id to send it
            else:
                path = msg_media[msg_media.media].file_id
            downloaded_media.append(path)
            if msg_media.media == "photo":
                media_input.append(InputMediaPhoto(path, text))
            elif msg_media.media == "video":
                media_input.append(InputMediaVideo(path, caption=text))
            elif msg_media.media == "audio":
                media_input.append(InputMediaAudio(path, caption=text))
            elif msg_media.media == "document":
                media_input.append(InputMediaDocument(path, caption=text))
            elif msg_media.media == "animation":
                media_input.append(InputMediaAnimation(path, caption=text))

        reply_id = None
        if reply:
            src_reply_id = str(message.reply_to_message.message_id)
            # If the message id is in the list of messages ids
            if target in msg_ids and source in msg_ids[target] and\
                    src_reply_id in msg_ids[target][source]:
                reply_id = msg_ids[target][source][src_reply_id]
                logger.debug(f"Replying to message: {reply_id}")
            else:
                logger.error("The reply message cannot be forwarded, " +
                             "because it does not exist in the target chat")
                return

        msg = await user.send_media_group(target, media_input,
                                          reply_to_message_id=reply_id)
        to_user = msg[0].chat.title if msg[0].chat.title else\
            msg[0].chat.first_name
        logger.info(f"Copying media group from {from_user} to {to_user}")

        for path in downloaded_media:
            if os.path.isfile(path):
                logger.debug(f"Removing file {path}")
                os.remove(path)
        for old_msg, new_msg in zip(messages, msg):
            await Messages.add_message_id(target, source, old_msg.message_id,
                                          new_msg.message_id)

    elif message.media is not None:
        downloadable_media = ["photo", "video", "audio", "voice", "document",
                              "animation", "video_note", "sticker"]
        text = await replace_words(forwarder, message.caption)
        entities = message.caption_entities
        reply_id = None

        if message.media in downloadable_media:
            # If the chat has protected content, download the media to send it
            if message.chat.has_protected_content:
                logger.debug(f"{from_user} has protected content, "
                             "downloading media")
                path = await message.download()
            else:
                logger.debug(f"{from_user} has no protected content, "
                             "using file_id")
                path = message[message.media].file_id

        if reply:
            src_reply_id = str(message.reply_to_message_id)
            # If the message id is in the list of messages ids
            if target in msg_ids and source in msg_ids[target] and\
                    src_reply_id in msg_ids[target][source]:
                reply_id = msg_ids[target][source][src_reply_id]
                logger.debug(f"Replying to message: {reply_id}")
            # If the chat has not protected content, get the file_id to send it
            else:
                logger.error("The media cannot be replied, because it " +
                             "does not exist in the target chat")
                return

        if edited:
            origin_edit_id = str(message.message_id)
            edit_id = -1
            # If the message id is in the list of messages ids
            if target in msg_ids and source in msg_ids[target] and\
                    origin_edit_id in msg_ids[target][source]:
                edit_id = msg_ids[target][source][origin_edit_id]
            if message.media == "photo":
                media = InputMediaPhoto(path, text)
            elif message.media == "video":
                media = InputMediaVideo(path, caption=text)
            elif message.media == "audio":
                media = InputMediaAudio(path, caption=text)
            elif message.media == "document":
                media = InputMediaDocument(path, caption=text)
            elif message.media == "animation":
                media = InputMediaAnimation(path, caption=text)

            try:
                if message.media == "web_page":
                    text = await replace_words(forwarder, message.text)
                    msg = await user.edit_message_text(target, edit_id, text,
                                                       entities=entities)
                    to_user = msg.chat.title if msg.chat.title else\
                        msg.chat.first_name
                    logger.info(f"Editing media from {from_user} to {to_user}")
                else:
                    msg = await user.edit_message_media(target, edit_id, media)
                    to_user = msg.chat.title if msg.chat.title else\
                        msg.chat.first_name
                    logger.info(f"Editing media from {from_user} to {to_user}")
                    if entities is not None:
                        await user.edit_message_caption(
                            target, edit_id, text, caption_entities=entities)
            except MessageIdInvalid:
                logger.error("The media cannot be edited, because it does " +
                             "not exist in the target chat")
                return
            except MessageNotModified:
                logger.error("The media could not be edited, because an atte" +
                             "mpt was made to edit using the same content")
                return

        else:
            if message.media == "photo":
                msg = await user.send_photo(target, path, text,
                                            caption_entities=entities,
                                            reply_to_message_id=reply_id)
            elif message.media == "audio":
                msg = await user.send_audio(target, path, text,
                                            caption_entities=entities,
                                            reply_to_message_id=reply_id)
            elif message.media == "document":
                msg = await user.send_document(target, path, caption=text,
                                               caption_entities=entities,
                                               reply_to_message_id=reply_id)
            elif message.media == "sticker":
                msg = await user.send_sticker(target, path,
                                              reply_to_message_id=reply_id)
            elif message.media == "video":
                msg = await user.send_video(target, path, text,
                                            caption_entities=entities,
                                            reply_to_message_id=reply_id)
            elif message.media == "animation":
                msg = await user.send_animation(target, path, text,
                                                caption_entities=entities,
                                                reply_to_message_id=reply_id)
            elif message.media == "voice":
                msg = await user.send_voice(target, path, text,
                                            caption_entities=entities,
                                            reply_to_message_id=reply_id)
            elif message.media == "video_note":
                msg = await user.send_video_note(target, path,
                                                 reply_to_message_id=reply_id)
            elif message.media == "location":
                latitude = message.location.latitude
                longitude = message.location.longitude
                msg = await user.send_location(target, latitude, longitude,
                                               reply_to_message_id=reply_id)
            elif message.media == "venue":
                latitude = message.venue.location.latitude
                longitude = message.venue.location.longitude
                title = message.venue.title
                address = message.venue.address
                msg = await user.send_venue(target, latitude, longitude, title,
                                            address,
                                            reply_to_message_id=reply_id)
            elif message.media == "contact":
                phone_number = message.contact.phone_number
                first_name = message.contact.first_name
                last_name = message.contact.last_name
                msg = await user.send_contact(target, phone_number,
                                              first_name, last_name,
                                              reply_to_message_id=reply_id)
            elif message.media == "dice":
                emoji = message.dice.emoji
                msg = await user.send_dice(target, emoji,
                                           reply_to_message_id=reply_id)
            elif message.media == "web_page":
                text = await replace_words(forwarder, message.text)
                msg = await user.send_message(target, text, entities=entities,
                                              reply_to_message_id=reply_id)
            # Only will be sent if the poll type is regular
            elif message.media == "poll" and message.poll.type == "regular":
                question = message.poll.question
                options = [option.text for option in message.poll.options]
                is_anonymous = message.poll.is_anonymous
                type = message.poll.type
                allows_multiple_answers = message.poll.allows_multiple_answers
                try:
                    msg = await user.send_poll(target, question, options,
                                               is_anonymous, type,
                                               allows_multiple_answers,
                                               reply_to_message_id=reply_id)
                except MediaInvalid:
                    logger.error("The poll could not be sent. Maybe the " +
                                 "target is a private chat?")
                    return
            to_user = msg.chat.title if msg.chat.title else msg.chat.first_name
            logger.info(f"Sending media from {from_user} to {to_user}")
            await Messages.add_message_id(target, source, message.message_id,
                                          msg.message_id)

        if message.media in downloadable_media:
            if os.path.isfile(path):
                logger.debug(f"Removing file {path}")
                os.remove(path)

    # If the message is just a text message
    else:
        text = await replace_words(forwarder, message.text)
        entities = message.entities
        reply_id = None

        if reply:
            src_reply_id = str(message.reply_to_message_id)
            # If the message id is in the list of messages ids
            if target in msg_ids and source in msg_ids[target] and\
                    src_reply_id in msg_ids[target][source]:
                reply_id = msg_ids[target][source][src_reply_id]
                logger.debug(f"Replying to message: {reply_id}")
            else:
                logger.error("The message cannot be replied, because it " +
                             "does not exist in the target chat")
                return

        if edited:
            origin_edit_id = str(message.message_id)
            edit_id = -1
            if target in msg_ids and origin_edit_id in msg_ids[target][source]:
                edit_id = msg_ids[target][source][origin_edit_id]
            try:
                msg = await user.edit_message_text(target, edit_id, text,
                                                   entities=entities)
                to_user = msg.chat.title if msg.chat.title else\
                    msg.chat.first_name
                logger.info(f"Editing message from {from_user} to {to_user}")
            except MessageIdInvalid:
                logger.error("The message cannot be edited, because it does " +
                             "not exist in the target chat")
                return
            except MessageNotModified:
                logger.error("The message could not be edited, because an at" +
                             "tempt was made to edit using the same content")
                return

        else:
            msg = await user.send_message(target, text, entities=entities,
                                          reply_to_message_id=reply_id)
            to_user = msg.chat.title if msg.chat.title else msg.chat.first_name
            logger.info(f"Sending message from {from_user} to {to_user}")
            await Messages.add_message_id(target, source, message.message_id,
                                          msg.message_id)

    # Call messages function to handle the new message
    if media_group and reply:
        await on_media_group_reply(user, msg[0])
    elif media_group:
        await on_media_group(user, msg[0])
    elif reply:
        await on_message_reply(user, msg)
    elif edited:
        await on_message_edited(user, msg)
    else:
        await on_new_message(user, msg)


async def get_targets(event: Message, media_group=False):
    """Get the target chats for the message"""
    targets = []
    next_forwarder = False
    source = event.chat.id
    forwarding_ids = await Forwardings.get_forwarding_ids()
    config = await Forwardings.get_config()
    outgoing = event.outgoing

    if source in forwarding_ids:
        for forwarder in config["forwarders"]:
            if outgoing and not forwarder["outgoing"]:
                continue
            if not outgoing and not forwarder["incoming"]:
                continue

            for word in forwarder["blocked_words"]:
                if media_group:
                    for message in event:
                        if message.caption is not None:
                            if word.lower() in message.caption.lower():
                                next_forwarder = True
                                break
                        if next_forwarder:
                            break
                else:
                    if event.caption is not None:
                        if word.lower() in event.caption.lower():
                            next_forwarder = True
                            break
                    if event.text is not None:
                        if word.lower() in event.text.lower():
                            next_forwarder = True
                            break

            if next_forwarder:
                continue
            if forwarder["enabled"]:
                if source in [int(src) for src in forwarder["source"].keys()]:
                    targets.append(forwarder)

    return targets


@user.on_message(filters.create(is_forwarder) & filters.edited &
                 ~filters.media_group)
async def on_message_edited(client: Client, message: Message):
    """Handle edited messages"""
    for target in await get_targets(message):
        if target["forwarding_mode"] == "copy":
            await copy_message(message, target, edited=True)
        else:
            await forward_message(message, target, edited=True)


@user.on_message(filters.create(is_forwarder) & filters.pinned_message &
                 ~filters.media_group)
async def on_message_pinned(client: Client, message: Message):
    """Handle pinned messages"""
    for target in await get_targets(message):
        await copy_message(message, target, pinned=True)


@user.on_message(filters.create(is_forwarder) & filters.reply &
                 ~filters.media_group)
async def on_message_reply(client: Client, message: Message):
    """Handle the reply to a message"""
    for target in await get_targets(message):
        if target["forwarding_mode"] == "copy":
            await copy_message(message, target, reply=True)
        else:
            await forward_message(message, target)


@user.on_message(filters.create(is_forwarder) & ~filters.media_group)
async def on_new_message(client: Client, message: Message):
    """Handle new messages"""
    for target in await get_targets(message):
        if target["forwarding_mode"] == "copy":
            await copy_message(message, target)
        else:
            await forward_message(message, target)


@user.on_message(filters.create(is_forwarder) & filters.media_group &
                 filters.reply)
async def on_media_group_reply(client: Client, message: Message):
    """Handle reply media groups messages"""
    global current_media_group
    if current_media_group == message.media_group_id:
        return

    current_media_group = message.media_group_id
    for target in await get_targets(message):
        if target["forwarding_mode"] == "copy":
            await copy_message(message, target, media_group=True, reply=True)
        else:
            await forward_message(message, target)


@user.on_message(filters.create(is_forwarder) & filters.media_group &
                 filters.edited)
async def on_media_group_edited(client: Client, message: Message):
    """Handle edited media group messages"""
    for target in await get_targets(message):
        if target["forwarding_mode"] == "copy":
            await copy_message(message, target, edited=True)
        else:
            await forward_message(message, target, media_group=True,
                                  edited=True)


@user.on_message(filters.create(is_forwarder) & filters.media_group)
async def on_media_group(client: Client, message: Message):
    """Handle media group messages"""
    global current_media_group
    if current_media_group == message.media_group_id:
        return

    current_media_group = message.media_group_id
    for target in await get_targets(message):
        if target["forwarding_mode"] == "copy":
            await copy_message(message, target, media_group=True)
        else:
            await forward_message(message, target, media_group=True)


@user.on_deleted_messages()
async def on_deleted_message(client: Client, messages: list[Message]):
    msg_ids = await Messages.get_message_ids()
    deleted_msg = []
    deleted_ids = []
    # If the message comes from a private chat
    if messages[0].chat is None:
        for message in messages:
            msg_id = str(message.message_id)
            for target in msg_ids:
                for source in msg_ids[target]:
                    if msg_id in msg_ids[target][source]:
                        del_id = msg_ids[target][source][msg_id]
                        msg_deleted = await client.get_messages(target, del_id)
                        deleted_msg.append(msg_deleted)
                        deleted_ids.append(del_id)
    # If the message comes from a group or channel
    else:
        for message in messages:
            msg_id = str(message.message_id)
            chat = str(message.chat.id)
            for target in msg_ids:
                if chat in msg_ids[target] and msg_id in msg_ids[target][chat]:
                    del_id = msg_ids[target][chat][msg_id]
                    msg_deleted = await client.get_messages(target, del_id)
                    deleted_msg.append(msg_deleted)
                    deleted_ids.append(del_id)

    # If there are messages to delete
    if len(deleted_msg) > 0 and msg_deleted.chat is not None:
        target = msg_deleted.chat.id
        from_user = msg_deleted.chat.title if msg_deleted.chat.title else\
            msg_deleted.chat.first_name
        logger.info(f"Removing messages from {from_user}")
        await user.delete_messages(target, deleted_ids)
        await on_deleted_message(user, deleted_msg)
