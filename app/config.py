import json
import os
from pathlib import Path

from logger import logger

# Create a folder that will hold the configuration files
app_dir = Path(__file__).parent
config_dir = app_dir / "config"
config_dir.mkdir(exist_ok=True)


class Bot:
    bot = {
        "api_id": 1234567,
        "api_hash": "0123456789abcdef0123456789abcdef",
        "admins": []
    }

    def get_config(self) -> dict:
        """Load the bot configuration from the bot.json file."""
        if not os.path.exists(config_dir/"bot.json"):
            logger.error("bot.json not found")
            logger.warning("bot.json has been created with default values. " +
                           "Please edit it with your own api_id and api_hash" +
                           " values. You can find them on " +
                           "https://my.telegram.org/apps.\n" +
                           "you can also use the API_ID and API_HASH " +
                           "envinroment variables.")

            with open(config_dir/"bot.json", "w") as f:
                json.dump(self.bot, f, indent=4, ensure_ascii=False)

            if not os.getenv("API_ID") or not os.getenv("API_HASH"):
                logger.error("API_ID and API_HASH environment variables not " +
                             " found please add them to your environment " +
                             "variables.")
                logger.error("Exiting...")
                exit(1)

        with open(config_dir/"bot.json", "r") as f:
            return json.load(f)

    def add_admin(self, admin: int) -> None:
        """Add an admin to the bot configuration."""
        if admin not in self.get_config()["admins"]:
            config = self.get_config()
            config["admins"].append(admin)

            with open(config_dir/"bot.json", "w") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)


class Forwarding:
    forwarding = {"forwarders": [], "blocked_images": []}

    async def get_config(self) -> dict:
        """Load the forwarding configuration from the forwarding.json file."""
        if not os.path.exists(config_dir/"forwarding.json"):
            logger.warning("forwarding.json not found")

            with open(config_dir/"forwarding.json", "w") as f:
                json.dump(self.forwarding, f, indent=4, ensure_ascii=False)

        with open(config_dir/"forwarding.json", "r") as f:
            return json.load(f)

    async def get_forwarding_ids(self) -> list:
        """Get the list of forwarding IDs."""
        forwarders = (await self.get_config())["forwarders"]
        forwarding_ids = []

        for forwarder in forwarders:
            for id in forwarder["source"].keys():
                forwarding_ids.append(int(id))

        # Remove duplicates and return the list
        return list(dict.fromkeys(forwarding_ids))

    async def get_forwardings(self) -> list:
        """Get the list of forwarding targets"""
        forwarders = (await self.get_config())["forwarders"]
        forwarding_targets = []

        for forwarder in forwarders:
            forwarding_targets.append(forwarder["target"])

        # Remove duplicates and return the list
        return list(dict.fromkeys(forwarding_targets))

    async def get_forwarder(self, forwarder_id: str) -> dict:
        """Get the forwarder with the given hash ID."""
        forwarders = (await self.get_config())["forwarders"]

        for forwarder in forwarders:
            if str(forwarder["target"]) == forwarder_id:
                return forwarder

    async def update_forwarder(self, forwarder_dict: dict):
        """Update the forwarding configuration."""
        config = await self.get_config()
        target = forwarder_dict["target"]

        for forwarder in config["forwarders"]:
            if forwarder["target"] == target:
                for key, value in forwarder_dict.items():
                    forwarder[key] = value

        with open(config_dir/"forwarding.json", "w") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

    async def add_forwarder(self, name: str, target: str, source: dict):
        """Add a new forwarding rule."""
        config = await self.get_config()
        config["forwarders"].append(
            {
                "name": name,
                "target": int(target),
                "enabled": True,
                "forwarding_mode": "copy",
                "incoming": True,
                "outgoing": True,
                "reply": True,
                "duplicated_text": False,
                "send_text_only": False,
                "translate": False,
                "translate_to": "en",
                "translate_from": "auto",
                "translate_show_original": False,
                "translate_original_prefix": "Original:",
                "translate_translation_prefix": "Translated:",
                "replace_words_mode": "word_boundary_match",
                "replace_words": {},
                "blocked_words": [],
                "source": source,
                "patterns": []
            }
        )

        with open(config_dir/"forwarding.json", "w") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

    async def remove_forwarder(self, forwarder_id: str):
        """Remove a forwarding rule."""
        config = await self.get_config()

        for forwarder in config["forwarders"]:
            if forwarder["target"] == int(forwarder_id):
                config["forwarders"].remove(forwarder)

        with open(config_dir/"forwarding.json", "w") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

    async def get_blocked_images(self) -> list:
        """Get the list of blocked images."""
        config = await self.get_config()
        blocked_images = config["blocked_images"]

        return blocked_images

    async def add_blocked_image(self, image: str):
        """Add a new blocked image."""
        config = await self.get_config()
        config["blocked_images"].append(image)

        with open(config_dir/"forwarding.json", "w") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)


class MessagesIDs:
    async def get_message_ids(self) -> list:
        """Get the list of message IDs."""
        if not os.path.exists(config_dir/"messages.json"):
            logger.warning("messages.json not found")

            with open(config_dir/"messages.json", "w") as f:
                json.dump({}, f, indent=4, ensure_ascii=False)

        with open(config_dir/"messages.json", "r") as f:
            return json.load(f)

    async def add_message_id(self, target: str, source: str, real_id: int,
                             copy_id: int):
        """Add a message ID to the list of IDs."""
        logger.debug(f"Adding message ID {copy_id} to {source} in {target}")
        messages_ids = await self.get_message_ids()

        if target not in messages_ids:
            messages_ids[target] = {}
        if source not in messages_ids[target]:
            messages_ids[target][source] = {}
        messages_ids[target][source][str(real_id)] = copy_id

        with open(config_dir/"messages.json", "w") as f:
            json.dump(messages_ids, f, indent=4, ensure_ascii=False)
