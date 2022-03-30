import json
import os

from logger import logger


class Bot:
    bot = {
        "api_id": 1234567,
        "api_hash": "0123456789abcdef0123456789abcdef"
    }

    def get_config(self) -> dict:
        """Load the bot configuration from the bot.json file."""
        if not os.path.exists("bot.json"):
            logger.error("bot.json not found")

            with open("bot.json", "w") as f:
                json.dump(self.bot, f, indent=4, ensure_ascii=False)
            exit(1)

        with open("bot.json", "r") as f:
            return json.load(f)


class Forwarding:
    forwarding = {"forwarders": []}

    async def get_config(self) -> dict:
        """Load the forwarding configuration from the forwarding.json file."""
        if not os.path.exists("forwarding.json"):
            logger.error("forwarding.json not found")

            with open("forwarding.json", "w") as f:
                json.dump(self.forwarding, f, indent=4, ensure_ascii=False)
            exit(1)

        with open("forwarding.json", "r") as f:
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

        with open("forwarding.json", "w") as f:
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
                "replace_words_mode": "word_boundary_match",
                "replace_words": {},
                "blocked_words": [],
                "source": source,
                "patterns": {}
            }
        )

        with open("forwarding.json", "w") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

    async def remove_forwarder(self, forwarder_id: str):
        """Remove a forwarding rule."""
        config = await self.get_config()

        for forwarder in config["forwarders"]:
            if forwarder["target"] == int(forwarder_id):
                config["forwarders"].remove(forwarder)

        with open("forwarding.json", "w") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)


class MessagesIDs:
    async def get_message_ids(self) -> list:
        """Get the list of message IDs."""
        if not os.path.exists("messages.json"):
            logger.error("messages.json not found")

            with open("messages.json", "w") as f:
                json.dump({}, f, indent=4, ensure_ascii=False)
            exit(1)

        with open("messages.json", "r") as f:
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

        with open("messages.json", "w") as f:
            json.dump(messages_ids, f, indent=4, ensure_ascii=False)
