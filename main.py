import asyncio
import contextlib2
import random
import sus
import traceback
import typing

import discord
from discord.ext import commands

from utils import *

# ##############
# ### Events ###
# ##############


@bot.event
async def on_ready():
    print('Ready')

    await bot.change_presence(
        activity=discord.Activity(
            name="from above",
            type=discord.ActivityType.watching
        )
    )


@bot.listen("on_message")
async def void_talk_on_message(message):
    """Event listener that handles void talk channels."""

    await bot.wait_until_ready()

    ctx = await bot.get_context(message)

    # Cases where void talk doesn't need to trigger:
    #  - the message is a command
    #  - the message author is a bot
    #  - channel is not a void talk channel
    #  - message is a non-triggering message
    if (
        ctx.valid or
        message.author.bot or
        message.channel.id not in void_talk_channels or
        message.content.startswith("# ")
    ):
        return

    perms = ctx.guild.me.permissions_in(message.channel) if ctx.guild else None
    if (message.guild and not perms.read_message_history):
        with contextlib2.suppress(discord.Forbidden):
            await message.channel.send(
                "I need the `Read Message History` "
                "permission to collect messages."
            )
        return
    if message.guild and not perms.manage_messages:
        with contextlib2.suppress(discord.Forbidden):
            await message.channel.send(
                "I need the `Manage Messages` permission to delete "
                "no-message triggering ('#') "
                "and forced prompt ('$ ') messages."
            )
        return

    # Whether void Bot will reply to the message or not.
    # If void Bot doesn't reply, the message is also deleted.
    reference = None if (
        (
            message.content == "#" or
            message.content.startswith("$ ")
        ) and not message.guild
    ) else message

    if reference is None:
        with contextlib2.suppress(discord.Forbidden):
            await message.delete()

    forced_prompt = f" {message.content[1:].lstrip()}" if (
        message.content.startswith("$ ")
    ) else ""

    try:
        await message.channel.trigger_typing()
    except discord.Forbidden:
        return

    async with message.channel.typing():

        collected_messages = await collect_messages(
            message.channel,
            mode=MessageCollectionType.void_TALK,
            before=message
        )
        # If the message doesn't get deleted, include it in the prompt.
        if reference is not None:
            collected_messages.append(
                f"{message.author.name}: "
                f"{message.content}"
            )
        collected_messages = '\n'.join(collected_messages)

        prompt = (
            f"{collected_messages}\n"
            f"{message.author.name}: {forced_prompt}"
        )
        try:
            response_text = await send_prompt(
                prompt,
                100,
                void_talk_channels[message.channel.id]/50,
                ["\n"]
            )
        except (IndexError, KeyError):
            # The API didn't return any text.
            return

    with contextlib2.suppress(discord.Forbidden):
        await ctx.void_send(
            f"{forced_prompt}{response_text}",
            reference=reference
        )


@bot.listen("on_message")
async def void_reply_on_message(message):
    """Event listener that handles void reply channels."""

    await bot.wait_until_ready()

    ctx = await bot.get_context(message)

    # Cases where void reply doesn't need to trigger:
    #  - the message is a command
    #  - the message author is a bot
    #  - messsage doesn't reply to anyone
    #  - message is in a void Talk channel
    #  - message is not in a void reply channel
    #  - message doesn't reply to void Bot
    if (
        ctx.valid or
        message.author.bot or
        not message.reference or
        message.channel.id in void_talk_channels or
        message.channel.id not in void_reply_channels
    ):
        return
    ref_message = message.reference.resolved if message.reference else None
    if ref_message is None or (
        isinstance(ref_message, discord.DeletedReferencedMessage) or
        ref_message.author != bot.user
    ):
        return

    perms = ctx.guild.me.permissions_in(message.channel) if ctx.guild else None
    if message.guild and not perms.read_message_history:
        with contextlib2.suppress(discord.Forbidden):
            await message.channel.send(
                "I need the `Read Message History` "
                "permission to collect messages."
            )
            return
    if message.guild and not perms.manage_messages:
        with contextlib2.suppress(discord.Forbidden):
            await message.channel.send(
                "I need the `Manage Messages` permission to delete "
                "no-message triggering ('#') and "
                "forced prompt ('$ ') messages."
            )
            return

    # Whether void Bot will reply to the message or not.
    # If void Bot doesn't reply, the message is also deleted.
    reference = None if (
        message.content == "#" or
        message.content.startswith("$ ")
    ) else message
    if reference is None:
        with contextlib2.suppress(discord.Forbidden):
            await message.delete()

    forced_prompt = f" {message.content[1:].lstrip()}" if (
        message.content.startswith("$ ")
    ) else ""

    try:
        await message.channel.trigger_typing()
    except discord.Forbidden:
        return

    async with message.channel.typing():

        collected_messages = await collect_messages(
            message.channel,
            mode=MessageCollectionType.void_REPLY,
            before=message,
        )
        # If the message doesn't get deleted, include it in the prompt.
        if reference is not None:
            collected_messages.append(
                f"{message.author.name}: "
                f"{message.content}"
            )
        collected_messages = '\n'.join(collected_messages)

        prompt = (
            f"{collected_messages}\n"
            f"{NAME}: {forced_prompt}"
        )
        try:
            response_text = await send_prompt(
                prompt,
                100,
                void_reply_channels[message.channel.id]/50,
                ["\n"]
            )
        except IndexError:
            # The API didn't return any text.
            return

    with contextlib2.suppress(discord.Forbidden):
        await ctx.void_send(
            f"{forced_prompt}{response_text}",
            reference=reference
        )


@bot.listen("on_message")
async def void_random_on_message(message):
    """Event listener that handles void random channels."""

    await bot.wait_until_ready()

    ctx = await bot.get_context(message)

    # Cases where void random doesn't need to trigger:
    #  - the message is a command
    #  - the message author is a bot
    #  - message is in a void talk channel
    #  - message is not in a void random channel
    #  - message replies to void Bot in a void reply channel
    #  - random check fails (check done after permission check)
    if (
        ctx.valid or
        ctx.author.bot or
        ctx.channel.id in void_talk_channels or
        ctx.channel.id not in void_random_channels
    ):
        return
    ref_message = message.reference.resolved if message.reference else None
    if ctx.channel.id in void_reply_channels and ref_message is not None and (
        not isinstance(ref_message, discord.DeletedReferencedMessage) and
        ref_message.author == bot.user
    ):
        return

    perms = ctx.guild.me.permissions_in(ctx.channel) if ctx.guild else None
    if ctx.guild and not perms.read_message_history:
        with contextlib2.suppress(discord.Forbidden):
            await ctx.send(
                "I need the `Read Message History` "
                "permission to collect messages."
            )
            return

    if random.uniform(0, 100) >= float(str(void_random_channels[ctx.channel.id])[1]):
        return

    try:
        await ctx.channel.trigger_typing()
    except discord.Forbidden:
        return

    async with ctx.channel.typing():

        collected_messages = await collect_messages(
            ctx.channel,
            mode=MessageCollectionType.TRIGGER_OR_void_RANDOM
        )
        collected_messages = '\n'.join(collected_messages)

        prompt = (
            f"{collected_messages}\n"
            f"{NAME}: {message.content}"
        )
        try:
            response_text = await send_prompt(
                prompt,
                100,
                void_random_channels[message.channel.id][0]/50,
                ["\n"]
            )
        except IndexError:
            # The API didn't return any text.
            return

    with contextlib2.suppress(discord.Forbidden):
        await ctx.void_send(
            response_text,
            reference=message
        )


# ################
# ### Commands ###
# ################

# ### Basic Commands ###
@bot.command(name="help", ignore_extra=False)
async def bot_help(ctx, category=''):
    """The help command. Help text is stored in help_text.txt."""
    try:
        await ctx.author.send(
            help_categories[category].format(
                prefix=ctx.prefix
            )
        )
    except discord.Forbidden:
        await ctx.send(
            "Please allow void Bot to "
            "DM you so you can recieve the help. "
            "The help text is very large, "
            "and it would be spammy to send it in a server."
        )
    except KeyError:
        await ctx.send(
            f"Invalid help category. Please use "
            f"{ctx.prefix}help to see all categories."
        )


@bot.command(name="reset", ignore_extra=False)
async def reset_cmd(ctx):
    """Reset command that doesn't actually do anything.
    Only exists to get detected by the message collector.
    Allows you to delete the invoke message to undo the reset."""


@bot.command(name="echo")
async def echo_cmd(ctx, *, text):
    """This command simply echoes text back to you,
    while also applying void Bot's filters"""
    await ctx.void_send(text)


# ### API Commands ###
@bot.command(name="trigger")
async def bot_trigger(
    ctx,
    max_size: typing.Optional[int] = 80,
    randomness: typing.Optional[float_nan_converter] = 45,
    *,
    text=""
):
    """Sends messages as a prompt to the OpenAI API to autocomplete."""

    if randomness > 100 or randomness < 0:
        await ctx.send("Randomness has to be between 0 and 100.")
        return
    if max_size not in range(1, TOKEN_LIMIT+1):
        await ctx.send(f"Max size has to be between 1 and {TOKEN_LIMIT}.")
        return

    perms = ctx.guild.me.permissions_in(ctx.channel) if ctx.guild else None
    if ctx.guild and not perms.read_message_history:
        await ctx.channel.send(
            "I need the `Read Message History` "
            "permission to collect messages."
        )
        return

    async with ctx.channel.typing():
        collected_messages = await collect_messages(
            ctx.channel,
            mode=MessageCollectionType.TRIGGER_OR_void_RANDOM
        )
        collected_messages = '\n'.join(collected_messages)
        prompt = f"{collected_messages}\n{NAME}: {' ' if text else ''}{text}"
        try:
            response_text = await send_prompt(
                prompt,
                max_size,
                randomness/50,
                ["\n"]
            )
        except (IndexError, KeyError):
            # In case we get no text from the API.
            response_text = ""

    await ctx.void_send(f"{text}{response_text}", reference=ctx.message)


@bot.command(name="generate")
async def bot_generate(
    ctx,
    max_size: typing.Optional[int] = 80,
    randomness: typing.Optional[float_nan_converter] = 45,
    *,
    text=""
):
    """Generates text using the OpenAI API."""

    if randomness > 100 or randomness < 0:
        await ctx.send("Randomness has to be between 0 and 100.")
        return
    if max_size not in range(1, TOKEN_LIMIT+1):
        await ctx.send(f"Max size has to be between 1 and {TOKEN_LIMIT}.")
        return

    async with ctx.channel.typing():
        try:
            response_text = await send_prompt(
                text,
                max_size, randomness/50,
                decrease_max=True,
                first_line=False
            )
        except (IndexError, KeyError):
            # In case we get no text from the API.
            response_text = ""

    await ctx.void_send(f"{text}{response_text}", reference=ctx.message)


# ### void Talk Commands ###
@bot.group(name="voidtalk", ignore_extra=False, invoke_without_command=True)
async def void_talk(ctx):
    """Adding/removing/listing void reply channels."""

    if ctx.guild:
        channels = '\n'.join([
            f"{channel.mention} ({channel.id})\n"
            f"  randomness: {void_talk_channels[channel.id]}" for
            channel in
            ctx.guild.text_channels if
            channel.id in void_talk_channels
        ])
        if channels:
            await ctx.send(f"List of void talk channels:\n\n{channels}")
            return
        await ctx.send("This server doesn't have any void talk channels.")
        return
    elif ctx.channel.id in void_talk_channels:
        await ctx.send(
            f"This DM channel is a void talk channel with "
            f"randomness {void_talk_channels[ctx.channel.id]}."
        )
        return
    await ctx.send("This DM channel is not a void talk channel.")


@permissions_or_dm(manage_channels=True)
@void_talk.command(name="set", ignore_extra=False)
async def void_talk_set(
    ctx,
    randomness: typing.Optional[float_nan_converter] = 45.0,
    channel: discord.TextChannel = None
):
    """Puts channel in queue for adding to void talk channels."""

    if randomness < 0 or randomness > 100:
        await ctx.send("Randomness needs to be between 0 and 100.")
        return

    channel = channel or ctx.channel

    await void_queue.put((
        "SET_void_TALK",
        channel.id,
        randomness,
        None
    ))

    channelstr = f" for {channel.mention}" if channel != ctx.channel else ""
    await ctx.send(f"void talk randomness{channelstr} set to {randomness}%.")


@permissions_or_dm(manage_channels=True)
@void_talk.command(name="unset", ignore_extra=False)
async def void_talk_unset(ctx, channel: discord.TextChannel = None):
    """Puts channel in queue for removal from void talk channels."""

    channel = channel or ctx.channel
    channelstr = channel.mention if channel != ctx.channel else "This channel"

    if channel.id not in void_talk_channels:
        await ctx.send(f"{channelstr} is not a void talk channel.")
        return

    await void_queue.put((
        "UNSET_void_TALK",
        channel.id,
        None,
        None
    ))

    channelstr = f" for {channel.mention}" if channel != ctx.channel else ""
    await ctx.send(f"void talk turned off{channelstr}.")


# ### void Reply Commands ###
@bot.group(name="voidreply", ignore_extra=False, invoke_without_command=True)
async def void_reply(ctx):
    """Adding/removing/listing void reply channels."""

    if ctx.guild:
        channels = '\n'.join([
            f"{channel.mention} ({channel.id})\n"
            f"  randomness: {void_reply_channels[channel.id]}%" for
            channel in
            ctx.guild.text_channels if
            channel.id in void_reply_channels
        ])
        if channels:
            await ctx.send(f"List of void reply channels:\n\n{channels}")
            return
        await ctx.send("This server doesn't have any void reply channels.")
        return
    elif ctx.channel.id in void_reply_channels:
        await ctx.send(
            f"This DM channel is a void reply channel with "
            f"randomness {void_reply_channels[ctx.channel.id]}%."
        )
        return
    await ctx.send("This DM channel is not a void reply channel.")


@permissions_or_dm(manage_channels=True)
@void_reply.command(name="set", ignore_extra=False)
async def void_reply_set(
    ctx,
    randomness: typing.Optional[float_nan_converter] = 45.0,
    channel: discord.TextChannel = None
):
    """Puts channel in queue for adding to void reply channels."""

    if randomness < 0 or randomness > 100:
        await ctx.send("Randomness needs to be between 0 and 100.")
        return

    channel = channel or ctx.channel

    await void_queue.put((
        "SET_void_REPLY",
        channel.id,
        randomness,
        None
    ))

    channelstr = f" for {channel.mention}" if channel != ctx.channel else ""
    await ctx.send(f"void reply randomness{channelstr} set to {randomness}%.")


@permissions_or_dm(manage_channels=True)
@void_reply.command(name="unset", ignore_extra=False)
async def void_reply_unset(ctx, channel: discord.TextChannel = None):
    """Puts channel in queue for removal from void reply channels."""

    channel = channel or ctx.channel
    channelstr = channel.mention if channel != ctx.channel else "This channel"

    if channel.id not in void_reply_channels:
        await ctx.send(f"{channelstr} is not a void reply channel.")
        return

    await void_queue.put((
        "UNSET_void_REPLY",
        channel.id,
        None,
        None
    ))

    channelstr = f" for {channel.mention}" if channel != ctx.channel else ""
    await ctx.send(f"void reply turned off{channelstr}.")


# ### void Random Commands ###
@bot.group(name="voidrandom", ignore_extra=False, invoke_without_command=True)
async def void_random(ctx):
    """Adding/removing/listing void random channels."""

    if ctx.guild:
        channels = '\n'.join([
            f"{channel.mention} ({channel.id})\n"
            f"  randomness: {void_random_channels[channel.id][0]}%\n"
            f"  chance: {void_random_channels[channel.id][1]}%" for
            channel in
            ctx.guild.text_channels if
            channel.id in void_random_channels
        ])
        if channels:
            await ctx.send(f"List of void random channels:\n\n{channels}")
            return
        await ctx.send("This server doesn't have any void random channels.")
        return
    elif ctx.channel.id in void_random_channels:
        await ctx.send(
            f"This DM channel is a void random channel with "
            f"randomness {void_random_channels[ctx.channel.id][0]}% and "
            f"chance {void_random_channels[ctx.channel.id][1]}%."
        )
        return
    await ctx.send("This DM channel is not a void random channel.")


@permissions_or_dm(manage_channels=True)
@void_random.command(name="set", ignore_extra=False)
async def void_random_set(
    ctx,
    randomness: typing.Optional[float_nan_converter] = 45.0,
    chance: typing.Optional[float_nan_converter] = 5.0,
    channel: discord.TextChannel = None
):
    """Puts channel in queue for adding to void random channels."""

    if randomness < 0 or randomness > 100:
        await ctx.send("Randomness needs to be between 0 and 100.")
        return
    if chance < 0 or chance > 100:
        await ctx.send("Chance needs to be between 0 and 100.")
        return

    channel = channel or ctx.channel

    await void_queue.put((
        "SET_void_RANDOM",
        channel.id,
        randomness,
        chance
    ))

    channelstr = f" for {channel.mention}" if channel != ctx.channel else ""
    await ctx.send(
        f"void random{channelstr} set to\n"
        f"  randomness: {randomness}%\n"
        f"  chance: {chance}%"
    )


@permissions_or_dm(manage_channels=True)
@void_random.command(name="unset", ignore_extra=False)
async def void_random_unset(ctx, channel: discord.TextChannel = None):
    """Puts channel in queue for removal from void random channels."""

    channel = channel or ctx.channel
    channelstr = channel.mention if channel != ctx.channel else "This channel"

    if channel.id not in void_random_channels:
        await ctx.send(f"{channelstr} is not a void random channel.")
        return

    await void_queue.put((
        "UNSET_void_RANDOM",
        channel.id,
        None,
        None
    ))

    channelstr = f" for {channel.mention}" if channel != ctx.channel else ""
    await ctx.send(f"void random turned off{channelstr}.")


# ### Link Commands ###
@bot.group(name="links", ignore_extra=False, invoke_without_command=True)
async def links(ctx):
    """Uncensoring links or listing channels with uncensored links."""

    if ctx.guild:
        channels = '\n'.join([
            f"  {channel.mention} ({channel.id})" for
            channel in
            ctx.guild.text_channels if
            channel.id in uncensored_link_channels
        ])
        if channels:
            await ctx.send(f"Channels with uncensored links:\n{channels}")
            return
        await ctx.send(
            "This server doesn't have any "
            "channels with uncensored links."
        )
        return
    elif ctx.channel.id in uncensored_link_channels:
        await ctx.send(f"This DM channel has uncensored links.")
        return
    await ctx.send("This DM channel has censored links.")


@permissions_or_dm(manage_channels=True)
@links.command(name="toggle", ignore_extra=False)
async def links_toggle(ctx, channel: discord.TextChannel = None):
    """Puts channel in the queue for toggling censoring channels."""

    channel = channel or ctx.channel
    channelstr = channel.mention if channel != ctx.channel else "This channel"

    if channel.id in uncensored_link_channels:
        op = "CENSOR_LINKS"
    else:
        op = "UNCENSOR_LINKS"

    await void_queue.put((
        op,
        channel.id,
        None,
        None
    ))

    channelstr = f" for {channel.mention}" if channel != ctx.channel else ""
    if op == "CENSOR_LINKS":
        await ctx.send(f"Links censored{channelstr}.")
        return
    await ctx.send(f"Links uncensored{channelstr}.")


# ######################
# ### Error Handlers ###
# ######################

@bot.event
async def on_command_error(ctx, error):
    error = getattr(error, "original", error)
    ignored = (
        commands.CommandNotFound,
        commands.TooManyArguments,
        discord.Forbidden,
        discord.HTTPException
    )
    if hasattr(ctx.command, 'on_error'):
        pass
    elif isinstance(error, ignored):
        pass
    else:
        print(f"Ignoring exception in command {ctx.command}:", file=sys.stderr)
        traceback.print_exception(
            type(error),
            error,
            error.__traceback__,
            file=sys.stderr
        )


@void_talk_set.error
async def error__void_talk_set(ctx, error):
    await handle_set_error(ctx, error, "randomness")


@void_talk_unset.error
async def error__void_talk_unset(ctx, error):
    await handle_unset_or_toggle_error(ctx, error)


@void_reply_set.error
async def error__void_reply_set(ctx, error):
    await handle_set_error(ctx, error, "randomness")


@void_reply_unset.error
async def error__void_reply_unset(ctx, error):
    await handle_unset_or_toggle_error(ctx, error)


@void_random_set.error
async def error__void_random_set(ctx, error):
    await handle_set_error(ctx, error, "randomness or chance")


@void_random_unset.error
async def error__void_reply_unset(ctx, error):
    await handle_unset_or_toggle_error(ctx, error)


@links_toggle.error
async def error__links_toggle(ctx, error):
    await handle_unset_or_toggle_error(ctx, error)


# #######################
# ### Running The Bot ###
# #######################


clean_unused_channels.start()
loop = asyncio.get_event_loop()
try:
    loop.run_until_complete(bot.start(TOKEN))
except KeyboardInterrupt:
    loop.run_until_complete(bot.close())
    update_data_files.stop()
    clean_unused_channels.stop()
finally:
    discord.client._cleanup_loop(loop)
