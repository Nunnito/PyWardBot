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
# TODO: Edited, deleted, pinned, replied messages toggles.

import os
import re
import datetime
from pathlib import Path
from os import getenv

from deep_translator import GoogleTranslator
from sewar.full_ref import uqi
from cv2 import imread

from pyrogram import Client, filters
from pyrogram.raw.functions.messages import SendVote
from pyrogram.enums import MessageMediaType, PollType
from pyrogram.types import (Message, InputMediaPhoto, InputMediaVideo,
                            InputMediaAudio, InputMediaDocument,
                            InputMediaAnimation)
from pyrogram.errors.exceptions.bad_request_400 import (MediaInvalid,
                                                        MessageIdInvalid,
                                                        MessageNotModified)

from config import Bot, Forwarding, MessagesIDs
from logger import logger

# Config path
app_dir = Path(__file__).parent
config_dir = app_dir / "config"

# Load the bot configuration
bot_config = Bot().get_config()


# Set up the Telegram client
API_ID = getenv("API_ID") if getenv("API_ID") else bot_config["api_id"]
API_HASH = getenv("API_HASH") if getenv("API_HASH") else bot_config["api_hash"]

user = Client(str(Path(config_dir/"user")), API_ID, API_HASH)
current_media_group = None  # Current media group ID

Messages = MessagesIDs()
Forwardings = Forwarding()


async def is_identical_to_last(message: Message, target: int) -> bool:
    """Check if the message is identical to the last message"""
    generator = message._client.get_chat_history(target, 1)
    last_message = [m async for m in generator]
    return message.text == last_message[0].text


async def translate(text: str, to: str, from_: str, show_original: bool,
                    original_prefix: str, translation_prefix: str) -> str:
    """Translate the text"""
    strip_text = False
    found_hashtag = re.search(r"#\w+\b", text)

    # This is to avoid the translation of the hashtag
    if found_hashtag:
        stripped_text = found_hashtag.group()
        text = text.replace(stripped_text, "3141592")
        strip_text = True

    # Translate the text
    translated_text = GoogleTranslator(from_, to).translate(text)
    if strip_text:
        translated_text = translated_text.replace("3141592", stripped_text)
        text = text.replace("3141592", stripped_text)

    # Show the original text and translated text together
    if show_original:
        return (f"{original_prefix}\n{text}\n\n"
                f"{translation_prefix}\n{translated_text}")

    return translated_text


async def get_media_type(message: Message) -> str:
    match message.media:
        case MessageMediaType.PHOTO:
            return message.photo.file_id
        case MessageMediaType.VIDEO:
            return message.video.file_id
        case MessageMediaType.AUDIO:
            return message.audio.file_id
        case MessageMediaType.VOICE:
            return message.voice.file_id
        case MessageMediaType.DOCUMENT:
            return message.document.file_id
        case MessageMediaType.ANIMATION:
            return message.animation.file_id
        case MessageMediaType.VIDEO_NOTE:
            return message.video_note.file_id
        case MessageMediaType.STICKER:
            return message.sticker.file_id


async def is_image_blocked(message: Message) -> bool:
    """Check if the image is blocked"""
    imgs = await Forwardings.get_blocked_images()

    # Set name of the image to current timestamp
    name = datetime.datetime.now().timestamp()

    # Download the photo and read it with cv2
    test_path = await message.download(config_dir/"blocked_img"/f"{name}.jpg")
    test_img = imread(test_path)

    # Remove the downloaded photo (this is safe because is already in memory)
    if os.path.isfile(test_path):
        os.remove(test_path)

    for img in imgs:
        # Open original image
        og_img = imread(img)

        # Check if the image is the same size
        if og_img.shape[:2] == (message.photo.height, message.photo.width):
            # Check similarity with the original image
            if uqi(test_img, og_img) >= 0.9:
                logger.debug(f"Image '{img}' is blocked")
                return True

    return False


async def is_forwarder(filter, client: Client, message: Message) -> bool:
    """Check if the chat id is in the forwarding list"""
    id = message.chat.id
    forwarding_ids = await Forwardings.get_forwarding_ids()
    return id in forwarding_ids


async def replace_words(target: dict, text: str,
                        is_caption: bool = False) -> str:
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
        if re.search(pattern["pattern"], text, re.DOTALL):
            logger.debug(f"Pattern '{pattern['name']}' found in text")
            text = re.search(pattern["pattern"], text, re.DOTALL)
            text = text.group(pattern["group"])
            break

    if target["translate"]:
        translated_text = await translate(
            text,
            target["translate_to"],
            target["translate_from"],
            target["translate_show_original"],
            target["translate_original_prefix"],
            target["translate_translation_prefix"])
        if is_caption and len(translated_text) <= 1024:
            text = translated_text
        elif not is_caption and len(translated_text) <= 4096:
            text = translated_text

    logger.debug("Returning text")
    return text


async def forward_message(message: Message, target: dict, edited=False,
                          media_group=False):
    """Forward a message to a target"""
    msg_ids = await Messages.get_message_ids()
    target = str(target["target"])
    source = str(message.chat.id)
    ids = message.id

    if media_group:
        messages = await user.get_media_group(source, message.id)
        ids = [msg.id for msg in messages]

    if edited:
        origin_edit_id = str(message.id)
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

        if media_group:
            mgm = msg[0]
            to_user = mgm.chat.title if mgm.chat.title else mgm.chat.first_name
        else:
            to_user = msg.chat.title if msg.chat.title else msg.chat.first_name
        logger.info(f"Forwarding message from {from_user} to {to_user}")
    else:
        logger.error("The chat is restricted from forwarding messages")
        return

    if media_group:
        for old_msg, new_msg in zip(messages, msg):
            await Messages.add_message_id(target, source, old_msg.id,
                                          new_msg.id)
    else:
        await Messages.add_message_id(target, source, message.id, msg.id)

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
        origin_pinned_id = str(message.pinned_message.id)
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
        messages = await user.get_media_group(source, message.id)
        media_input = []
        downloaded_media = []

        for msg_media in messages:
            text = await replace_words(forwarder, msg_media.caption, True)
            entities = msg_media.caption_entities
            # If the chat has protected content, download the media to send it
            if msg_media.chat.has_protected_content:
                path = await msg_media.download()
            # If the chat has not protected content, get the file_id to send it
            else:
                path = await get_media_type(msg_media)

            downloaded_media.append(path)
            if msg_media.media is MessageMediaType.PHOTO:
                media_input.append(InputMediaPhoto(path, text))
            elif msg_media.media is MessageMediaType.VIDEO:
                media_input.append(InputMediaVideo(path, caption=text))
            elif msg_media.media is MessageMediaType.AUDIO:
                media_input.append(InputMediaAudio(path, caption=text))
            elif msg_media.media is MessageMediaType.DOCUMENT:
                media_input.append(InputMediaDocument(path, caption=text))
            elif msg_media.media is MessageMediaType.ANIMATION:
                media_input.append(InputMediaAnimation(path, caption=text))

        reply_id = None
        if reply:
            src_reply_id = str(message.reply_to_message.id)
            # If the message id is in the list of messages ids
            if target in msg_ids and source in msg_ids[target] and\
                    src_reply_id in msg_ids[target][source]:
                reply_id = msg_ids[target][source][src_reply_id]
                logger.debug(f"Replying to message: {reply_id}")
            else:
                logger.error("The reply message cannot be forwarded, " +
                             "because it does not exist in the target chat")
                return

        if forwarder["send_text_only"]:
            msg = await user.send_message(target, text, entities=entities,
                                          reply_to_message_id=reply_id)
            await Messages.add_message_id(target, source, messages[0].id,
                                          msg.id)
        else:
            msg = await user.send_media_group(target, media_input,
                                              reply_to_message_id=reply_id)
            for old_msg, new_msg in zip(messages, msg):
                await Messages.add_message_id(target, source, old_msg.id,
                                              new_msg.id)

        to_user = msg[0].chat.title if msg[0].chat.title else\
            msg[0].chat.first_name
        logger.info(f"Copying media group from {from_user} to {to_user}")

        for path in downloaded_media:
            if os.path.isfile(path):
                logger.debug(f"Removing file {path}")
                os.remove(path)

    elif message.media is not None:
        downloadable_media = [MessageMediaType.PHOTO, MessageMediaType.VIDEO,
                              MessageMediaType.AUDIO, MessageMediaType.VOICE,
                              MessageMediaType.DOCUMENT,
                              MessageMediaType.ANIMATION,
                              MessageMediaType.VIDEO_NOTE,
                              MessageMediaType.STICKER]
        text = await replace_words(forwarder, message.caption, True)
        entities = message.caption_entities
        reply_id = None

        if message.media in downloadable_media:
            if message.media is MessageMediaType.PHOTO:
                if await is_image_blocked(message):
                    logger.error("The image is blocked")
                    return

            # If the chat has protected content, download the media to send it
            if message.chat.has_protected_content:
                logger.debug(f"{from_user} has protected content, "
                             "downloading media")
                path = await message.download()
            else:
                logger.debug(f"{from_user} has no protected content, "
                             "using file_id")
                path = await get_media_type(message)

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
            origin_edit_id = str(message.id)
            edit_id = -1
            # If the message id is in the list of messages ids
            if target in msg_ids and source in msg_ids[target] and\
                    origin_edit_id in msg_ids[target][source]:
                edit_id = msg_ids[target][source][origin_edit_id]
            if message.media is MessageMediaType.PHOTO:
                media = InputMediaPhoto(path, text)
            elif message.media is MessageMediaType.VIDEO:
                media = InputMediaVideo(path, caption=text)
            elif message.media is MessageMediaType.AUDIO:
                media = InputMediaAudio(path, caption=text)
            elif message.media is MessageMediaType.DOCUMENT:
                media = InputMediaDocument(path, caption=text)
            elif message.media is MessageMediaType.ANIMATION:
                media = InputMediaAnimation(path, caption=text)

            try:
                if message.media is MessageMediaType.WEB_PAGE:
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
            if forwarder["send_text_only"] and text != "":
                msg = await user.send_message(target, text, entities=entities,
                                              reply_to_message_id=reply_id)
            elif message.media is MessageMediaType.PHOTO:
                msg = await user.send_photo(target, path, text,
                                            caption_entities=entities,
                                            reply_to_message_id=reply_id)
            elif message.media is MessageMediaType.AUDIO:
                msg = await user.send_audio(target, path, text,
                                            caption_entities=entities,
                                            reply_to_message_id=reply_id)
            elif message.media is MessageMediaType.DOCUMENT:
                msg = await user.send_document(target, path, caption=text,
                                               caption_entities=entities,
                                               reply_to_message_id=reply_id)
            elif message.media is MessageMediaType.STICKER:
                msg = await user.send_sticker(target, path,
                                              reply_to_message_id=reply_id)
            elif message.media is MessageMediaType.VIDEO:
                msg = await user.send_video(target, path, text,
                                            caption_entities=entities,
                                            reply_to_message_id=reply_id)
            elif message.media is MessageMediaType.ANIMATION:
                msg = await user.send_animation(target, path, text,
                                                caption_entities=entities,
                                                reply_to_message_id=reply_id)
            elif message.media is MessageMediaType.VOICE:
                msg = await user.send_voice(target, path, text,
                                            caption_entities=entities,
                                            reply_to_message_id=reply_id)
            elif message.media is MessageMediaType.VIDEO_NOTE:
                msg = await user.send_video_note(target, path,
                                                 reply_to_message_id=reply_id)
            elif message.media is MessageMediaType.LOCATION:
                latitude = message.location.latitude
                longitude = message.location.longitude
                msg = await user.send_location(target, latitude, longitude,
                                               reply_to_message_id=reply_id)
            elif message.media is MessageMediaType.VENUE:
                latitude = message.venue.location.latitude
                longitude = message.venue.location.longitude
                title = message.venue.title
                address = message.venue.address
                msg = await user.send_venue(target, latitude, longitude, title,
                                            address,
                                            reply_to_message_id=reply_id)
            elif message.media is MessageMediaType.CONTACT:
                phone_number = message.contact.phone_number
                first_name = message.contact.first_name
                last_name = message.contact.last_name
                msg = await user.send_contact(target, phone_number,
                                              first_name, last_name,
                                              reply_to_message_id=reply_id)
            elif message.media is MessageMediaType.DICE:
                emoji = message.dice.emoji
                msg = await user.send_dice(target, emoji,
                                           reply_to_message_id=reply_id)
            elif message.media is MessageMediaType.WEB_PAGE:
                entities = message.entities
                text = await replace_words(forwarder, message.text)
                msg = await user.send_message(target, text, entities=entities,
                                              reply_to_message_id=reply_id)
            # Only will be sent if the poll type is regular
            elif message.media is MessageMediaType.POLL and\
                    message.poll.type is PollType.REGULAR:
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
            elif message.media is MessageMediaType.POLL and\
                    message.poll.type is PollType.QUIZ:
                # Answer the quiz to get the correct answer and explanation
                peer = await user.resolve_peer(message.chat.id)
                msg_id = message.id
                options = [b'0']
                r = await user.invoke(SendVote(peer=peer, msg_id=msg_id,
                                               options=options))

                # Get the correct answer
                for question in r.updates[0].results.results:
                    if question.correct:
                        correct_option = int(question.option)
                        break
                # Get the explanation
                explanation = r.updates[0].results.solution

                # Get base quiz
                question = message.poll.question
                options = [option.text for option in message.poll.options]
                is_anonymous = message.poll.is_anonymous
                type = message.poll.type
                allows_multiple_answers = message.poll.allows_multiple_answers

                # Send the quiz
                try:
                    msg = await user.send_poll(target, question, options,
                                               is_anonymous, type,
                                               allows_multiple_answers,
                                               correct_option, explanation,
                                               reply_to_message_id=reply_id)
                except MediaInvalid:
                    logger.error("The poll could not be sent. Maybe the " +
                                 "target is a private chat?")
                    return

            to_user = msg.chat.title if msg.chat.title else msg.chat.first_name
            logger.info(f"Sending media from {from_user} to {to_user}")
            await Messages.add_message_id(target, source, message.id, msg.id)

        if message.media in downloadable_media:
            if os.path.isfile(path):
                logger.debug(f"Removing file {path}")
                os.remove(path)

    # If the message is just a text message
    else:
        text = await replace_words(forwarder, message.text)
        entities = message.entities
        reply_id = None

        if not forwarder["duplicated_text"]:
            if await is_identical_to_last(message, target):
                logger.debug("The message is identical to the last message, " +
                             "skipping")
                return

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
            origin_edit_id = str(message.id)
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
            await Messages.add_message_id(target, source, message.id, msg.id)

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
    source = event.chat.id
    forwarding_ids = await Forwardings.get_forwarding_ids()
    config = await Forwardings.get_config()
    outgoing = event.outgoing

    if source in forwarding_ids:
        for forwarder in config["forwarders"]:
            next_forwarder = False

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
                # If forward outgoing messages is disabled, add the message ID
                # to messages.json
                if outgoing and not forwarder["outgoing"]:
                    await Messages.add_message_id(str(forwarder["target"]),
                                                  str(source), event.id,
                                                  event.id)
                    continue
                # If forward incoming messages is disabled, add the message ID
                # to messages.json
                if not outgoing and not forwarder["incoming"]:
                    await Messages.add_message_id(str(forwarder["target"]),
                                                  str(source), event.id,
                                                  event.id)
                    continue
                if source in [int(src) for src in forwarder["source"].keys()]:
                    targets.append(forwarder)

    return targets


@user.on_edited_message(filters.create(is_forwarder) & ~filters.media_group)
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
        if not target["reply"]:  # If the reply is disabled, continue
            continue
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
        if not target["reply"]:  # If the reply is disabled, continue
            continue
        if target["forwarding_mode"] == "copy":
            await copy_message(message, target, media_group=True, reply=True)
        else:
            await forward_message(message, target)


@user.on_edited_message(filters.create(is_forwarder) & filters.media_group)
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
            msg_id = str(message.id)
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
            msg_id = str(message.id)
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
