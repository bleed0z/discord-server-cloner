import os
import asyncio
import logging
from typing import Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN environment variable is required.")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("server-cloner")

intents = discord.Intents.none()
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)
clone_locks: Dict[int, asyncio.Lock] = {}


def has_source_access(member: discord.Member) -> bool:
    return member.guild_permissions.view_channel


def has_destination_access(member: discord.Member) -> bool:
    p = member.guild_permissions
    return (
        p.view_channel
        and p.manage_channels
        and p.manage_roles
        and p.manage_emojis_and_stickers
    )


def build_overwrites(channel, destination, role_map):
    copied = {}
    for target, overwrite in channel.overwrites.items():
        if isinstance(target, discord.Role):
            mapped = role_map.get(target.id)
            if mapped is not None:
                copied[mapped] = overwrite
        elif isinstance(target, discord.Member):
            member = destination.get_member(target.id)
            if member is not None:
                copied[member] = overwrite
    return copied


async def copy_roles(source: discord.Guild, destination: discord.Guild):
    role_map = {source.default_role.id: destination.default_role}
    source_roles = sorted(
        (r for r in source.roles if not r.is_default() and not r.managed),
        key=lambda r: r.position,
    )
    created = []
    for role in source_roles:
        new_role = await destination.create_role(
            name=role.name,
            permissions=role.permissions,
            colour=role.colour,
            hoist=role.hoist,
            mentionable=role.mentionable,
            reason=f"Authorized structure backup from guild {source.id}",
        )
        role_map[role.id] = new_role
        created.append((role.position, new_role))
    if created:
        try:
            await destination.edit_role_positions(
                positions={role: pos for pos, role in created}
            )
        except discord.HTTPException:
            log.warning("Role positions could not be fully restored.")
    return role_map


async def copy_emojis(source: discord.Guild, destination: discord.Guild):
    copied = skipped = 0
    try:
        emojis = await source.fetch_emojis()
    except (discord.Forbidden, discord.HTTPException):
        return 0, 0
    for emoji in emojis:
        try:
            raw = await emoji.read()
            await destination.create_custom_emoji(
                name=emoji.name,
                image=raw,
                reason=f"Authorized structure backup from guild {source.id}",
            )
            copied += 1
        except (discord.Forbidden, discord.HTTPException, discord.InvalidArgument):
            skipped += 1
            log.warning("Skipped emoji %s", emoji.name)
    return copied, skipped


async def copy_channels(source: discord.Guild, destination: discord.Guild, role_map):
    category_map = {}
    copied = skipped = 0

    for category in sorted(source.categories, key=lambda c: c.position):
        try:
            category_map[category.id] = await destination.create_category(
                name=category.name,
                position=category.position,
                overwrites=build_overwrites(category, destination, role_map),
                reason=f"Authorized structure backup from guild {source.id}",
            )
            copied += 1
        except (discord.Forbidden, discord.HTTPException):
            skipped += 1
            log.exception("Failed category: %s", category.name)

    for channel in sorted(source.channels, key=lambda c: (c.position, c.id)):
        if isinstance(channel, discord.CategoryChannel):
            continue
        category = category_map.get(channel.category_id)
        overwrites = build_overwrites(channel, destination, role_map)
        try:
            if isinstance(channel, discord.TextChannel):
                await destination.create_text_channel(
                    name=channel.name,
                    category=category,
                    topic=channel.topic,
                    nsfw=channel.nsfw,
                    slowmode_delay=channel.slowmode_delay,
                    default_auto_archive_duration=channel.default_auto_archive_duration,
                    overwrites=overwrites,
                    reason=f"Authorized structure backup from guild {source.id}",
                )
            elif isinstance(channel, discord.VoiceChannel):
                await destination.create_voice_channel(
                    name=channel.name,
                    category=category,
                    bitrate=min(channel.bitrate, destination.bitrate_limit),
                    user_limit=channel.user_limit,
                    rtc_region=channel.rtc_region,
                    video_quality_mode=channel.video_quality_mode,
                    overwrites=overwrites,
                    reason=f"Authorized structure backup from guild {source.id}",
                )
            elif isinstance(channel, discord.StageChannel):
                await destination.create_stage_channel(
                    name=channel.name,
                    category=category,
                    bitrate=min(channel.bitrate, destination.bitrate_limit),
                    user_limit=channel.user_limit,
                    rtc_region=channel.rtc_region,
                    video_quality_mode=channel.video_quality_mode,
                    overwrites=overwrites,
                    reason=f"Authorized structure backup from guild {source.id}",
                )
            else:
                skipped += 1
                continue
            copied += 1
        except (discord.Forbidden, discord.HTTPException, TypeError):
            skipped += 1
            log.exception("Failed channel: %s", channel.name)
    return copied, skipped


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        log.info("Synced %d slash commands.", len(synced))
    except discord.HTTPException:
        log.exception("Slash command sync failed.")
    log.info("Bot online as %s (%s)", bot.user, bot.user.id)


@bot.tree.command(name="clone", description="Copy an accessible server structure into this server.")
@app_commands.describe(source_server_id="Source server ID; bot must be a member of that server")
@app_commands.guild_only()
async def clone(interaction: discord.Interaction, source_server_id: str):
    if not source_server_id.isdigit():
        await interaction.response.send_message("Enter a numeric server ID.", ephemeral=True)
        return

    destination = interaction.guild
    source = bot.get_guild(int(source_server_id))
    if destination is None:
        await interaction.response.send_message("Use this command in the destination server.", ephemeral=True)
        return
    if source is None:
        await interaction.response.send_message(
            "I can't access that server. The bot must be invited to the source server too.",
            ephemeral=True,
        )
        return
    if source.id == destination.id:
        await interaction.response.send_message("Choose a different source server.", ephemeral=True)
        return

    if source.me is None or not has_source_access(source.me):
        await interaction.response.send_message(
            "The bot needs View Channels access in the source server.", ephemeral=True
        )
        return
    if destination.me is None or not has_destination_access(destination.me):
        await interaction.response.send_message(
            "Destination permissions needed: View Channels, Manage Channels, Manage Roles, "
            "and Manage Emojis and Stickers. Administrator is not required.",
            ephemeral=True,
        )
        return

    lock = clone_locks.setdefault(destination.id, asyncio.Lock())
    if lock.locked():
        await interaction.response.send_message("A copy is already running here.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    async with lock:
        await interaction.followup.send(
            f"Copying **{source.name}** into **{destination.name}**. "
            "This adds items and does not delete existing destination content.",
            ephemeral=True,
        )
        try:
            role_map = await copy_roles(source, destination)
            channel_count, channel_skipped = await copy_channels(source, destination, role_map)
            emoji_count, emoji_skipped = await copy_emojis(source, destination)
            await interaction.followup.send(
                "**Copy complete**\n"
                f"Roles created: {len(role_map) - 1}\n"
                f"Channels/categories created: {channel_count}\n"
                f"Channels/categories skipped: {channel_skipped}\n"
                f"Emojis copied: {emoji_count}\n"
                f"Emojis skipped: {emoji_skipped}\n\n"
                "Managed roles, messages, attachments, bots, and server-wide settings aren't copied. "
                "Member-specific overwrites are copied only for members also present in the destination.",
                ephemeral=True,
            )
        except Exception:
            log.exception("Clone operation failed.")
            await interaction.followup.send(
                "The copy stopped due to an error. Some items may already have been created; "
                "check Railway logs before retrying.",
                ephemeral=True,
            )


bot.run(TOKEN)
