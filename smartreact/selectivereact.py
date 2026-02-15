import discord
import re
from redbot.core import Config, commands, checks
from redbot.core.utils.chat_formatting import pagify, warning
from typing import Literal

URL_REGEX = re.compile(r"https?://\S+")


class SelectiveReact(commands.Cog):
    """Create automatic reactions when trigger words are typed in chat"""

    default_guild_settings = {"reactions": {}, "react_role": None}

    __version__ = "1.0.0"

    def __init__(self, bot):
        self.bot = bot
        self.conf = Config.get_conf(self, identifier=825495246)
        self.conf.register_guild(**self.default_guild_settings)

    @staticmethod
    def get_pattern(word: str):
        return re.compile(rf"\b{re.escape(word)}\b", flags=re.IGNORECASE)

    # -------------------- COMMANDS --------------------

    @checks.mod_or_permissions(administrator=True)
    @commands.guild_only()
    @commands.command(name="addreact")
    async def addreact(self, ctx, word, emoji):
        """Add an auto reaction to a word"""
        emoji = self.fix_custom_emoji(emoji)
        await self.create_reaction(ctx.guild, word, emoji, ctx.message)

    @checks.mod_or_permissions(administrator=True)
    @commands.guild_only()
    @commands.command(name="delreact")
    async def delreact(self, ctx, word, emoji):
        """Delete an auto reaction to a word"""
        emoji = self.fix_custom_emoji(emoji)
        await self.remove_reaction(ctx.guild, word, emoji, ctx.message)

    @checks.mod_or_permissions(administrator=True)
    @commands.guild_only()
    @commands.command(name="listreact")
    async def listreact(self, ctx):
        """List reactions for this server"""
        emojis = await self.conf.guild(ctx.guild).reactions()
        if not emojis:
            await ctx.send(warning("There are no automatic reactions set in your server!"), delete_after=30)
            return

        msg = f"# Reactions for {ctx.guild.name}:\n"
        for emoji in emojis:
            for word in emojis[emoji]:
                msg += f"- {emoji}: {word}\n"

        for page in pagify(msg, delims=["\n"]):
            await ctx.send(page)

    @checks.mod_or_permissions(administrator=True)
    @commands.guild_only()
    @commands.command(name="setreactrole")
    async def setreactrole(self, ctx, role: discord.Role):
        """Set a role that is the ONLY one the bot reacts to"""
        await self.conf.guild(ctx.guild).react_role.set(role.id)
        await ctx.send(f"✅ Automatic reactions will now only trigger for **{role.name}**.")

    @checks.mod_or_permissions(administrator=True)
    @commands.guild_only()
    @commands.command(name="clearreactrole")
    async def clearreactrole(self, ctx):
        """Remove the role restriction for automatic reactions"""
        await self.conf.guild(ctx.guild).react_role.set(None)
        await ctx.send("✅ Automatic reactions will now trigger for everyone.")

    # -------------------- INTERNAL HELPERS --------------------

    def fix_custom_emoji(self, emoji):
        if emoji[:2] not in ["<:", "<a"]:
            return emoji
        for guild in self.bot.guilds:
            for e in guild.emojis:
                if str(e.id) == emoji.split(":")[2][:-1]:
                    return e
        return None

    async def create_reaction(self, guild, word, emoji, message):
        try:
            await message.add_reaction(emoji)
            emoji = str(emoji)

            reactions = await self.conf.guild(guild).reactions()
            reactions.setdefault(emoji, [])

            if word.lower() in reactions[emoji]:
                await message.channel.send("This automatic reaction already exists.")
                return

            reactions[emoji].append(word.lower())
            await self.conf.guild(guild).reactions.set(reactions)
            await message.channel.send("Successfully added this automatic reaction.")

        except (discord.errors.HTTPException, TypeError, ValueError):
            await message.channel.send("That's not an emoji I recognize.")

    async def remove_reaction(self, guild, word, emoji, message):
        try:
            await message.add_reaction(emoji)
            emoji = str(emoji)

            reactions = await self.conf.guild(guild).reactions()
            if emoji not in reactions or word.lower() not in reactions[emoji]:
                await message.channel.send("That automatic reaction does not exist.")
                return

            reactions[emoji].remove(word.lower())
            if not reactions[emoji]:
                del reactions[emoji]

            await self.conf.guild(guild).reactions.set(reactions)
            await message.channel.send("Removed this automatic reaction.")

        except (discord.errors.HTTPException, TypeError, ValueError):
            await message.channel.send("That's not an emoji I recognize.")

    async def clean_dead_emojis(self, guild):
        reacts = await self.conf.guild(guild).reactions()
        to_delete = []

        for emoji in reacts:
            if not self.fix_custom_emoji(emoji):
                to_delete.append(emoji)

        for emoji in to_delete:
            del reacts[emoji]

        await self.conf.guild(guild).reactions.set(reacts)

    # -------------------- LISTENER --------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        if message.author.bot:
            return
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return
        if URL_REGEX.search(message.content):
            return

        react_role_id = await self.conf.guild(message.guild).react_role()
        if react_role_id is not None:
            if not any(role.id == react_role_id for role in message.author.roles):
                return

        reacts = await self.conf.guild(message.guild).reactions()
        if not reacts:
            return

        for emoji in reacts:
            for word in reacts[emoji]:
                if self.get_pattern(word).search(message.content):
                    emoji_obj = self.fix_custom_emoji(emoji)
                    if not emoji_obj:
                        await self.clean_dead_emojis(message.guild)
                        return
                    try:
                        await message.add_reaction(emoji_obj)
                        return
                    except discord.errors.Forbidden:
                        return

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ):
        pass
