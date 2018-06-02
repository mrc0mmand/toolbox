#!/bin/env python3

import asyncio
import discord
import logging
import random
import re
import requests
from discord.ext.commands import Bot
from discord.ext import commands
from weather import Unit, Weather

bee_emoji = "🐝"
poop_emoji = "💩"
quotes = {
    "Ray Bradbury" : "Bees do have a smell, you know, and if they don’t they should, for their feet are dusted with spices from a million flowers.",
    "Muriel Barbery" : "We think we can make honey without sharing in the fate of bees, but we are in truth nothing but poor bees, destined to accomplish our task and then die.",
    "William Longgood" : "The bee is domesticated but not tamed.",
    "Marcus Aurelius" : "That which is not good for the bee-hive cannot be good for the bees.",
    "William Blake" : "The busy bee has no time for sorrow.",
    "Brother Adam" : "Listen to the bees and let them guide you.",
    "St John Chrysostom" : "The bee is more honoured than other animals,not because she labors,but because she labours for others.",
    "Congolese" : "When the bee comes to your house, let her have beer; you may want to visit the bee’s house some day.",
    "Eddie Izzard" : "I'm covered in bees!",
    "Ralph Waldo Emerson" : "God will not have his work made manifest by cowards.",
    "Miloš Zeman" : "Kunda sem, kunda tam...",
}

ah_quotes = [
    "Das bolschewistische {}, dem sie die europäischen Nationen ausliefern wollen, wird sie und ihre Völker dereinst selbst zerfetzen!",
    "Wir sind uns im klaren, daß dieser Krieg ja nur damit enden könnte, daß {} ausgerottet wird!",
    "Mit jedem Kind, das sie {} zur Welt bringt, kämpft sie ihren Kampf für die Nation!",
    "Polen hat nun heute nacht zum erstenmal auf unserem eigenen Territorium auch durch reguläre {} geschossen!",
    "Toter {}, geh ein in Walhall!",
]

with open(".token") as fp:
    token = fp.readline().strip()

bot = Bot(description="BeeBot", command_prefix="?")
weather_ = Weather(unit=Unit.CELSIUS)

### COMMANDS ###

@bot.command()
async def weather(ctx, *location):
    raw_location = " ".join(location)
    response = weather_.lookup_by_location(raw_location)
    if response is None:
        await ctx.send(f"Unknown location '{raw_location}'")
        return

    condition = response.condition()

    await ctx.send("Weather for {}, {}: {}, {}°C, wind: {:.2f} km/h".format(
        response.location().city(), response.location().country(),
        condition.text(), condition.temp(), float(response.wind()["speed"])))

@bot.command()
async def shoot(ctx, target):
    await ctx.send("\**Bang bang* \* \n \** {} drops dead* \*".format(target))

@bot.command()
async def insult(ctx, target : discord.Member):
    try:
        url = "https://evilinsult.com/generate_insult.php?lang=en"
        res = requests.get(url)
        insult = str(res.content, encoding="utf-8")
    except:
        logging.exception("Insult fetching failed")
        return

    await ctx.send(f"{target.mention}: {insult}")

@bot.command()
async def gas(ctx, target):
    quote = random.choice(ah_quotes)
    await ctx.send(quote.format(target));

@bot.command()
@commands.is_owner()
async def purge(ctx, number : int):
    await ctx.channel.purge(limit=number)

@bot.event
async def on_ready():
    print("Logged in ({}/{})".format(bot.user.name, bot.user.id))
    await bot.change_presence(game=discord.Game(name="with a bee"))

@bot.listen()
async def on_message(message):
    if message.author == bot.user:
        return

    channel = message.channel

    if "bee" in message.content.lower():
        await message.add_reaction(bee_emoji)

    if message.content.lower() == "bee":
        author, quote = random.choice(list(quotes.items()))
        await channel.send("*\"{}\"* - {}".format(quote, author))

    if any(x == message.content for x in ['J', 'j']):
        await channel.send(message.content)

    m = re.search("store.steampowered.com/app/([0-9]+)", message.content)
    if m:
        await channel.send("steam://store/{}".format(m[1]))

@bot.listen()
async def on_message_delete(message):
    if message.author == bot.user:
        return

    await message.channel.send("{}: u little piece of shit >:("
            .format(message.author.mention))

bot.run(token)
