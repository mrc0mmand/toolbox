#!/bin/env python3

import discord
import asyncio
import random

bee_emoji = "🐝"
quotes = {
    "Ray Bradbury" : "Bees do have a smell, you know, and if they don’t they should, for their feet are dusted with spices from a million flowers.",
    "Muriel Barbery" : "iWe think we can make honey without sharing in the fate of bees, but we are in truth nothing but poor bees, destined to accomplish our task and then die.",
    "William Longgood" : "The bee is domesticated but not tamed.",
    "Marcus Aurelius" : "That which is not good for the bee-hive cannot be good for the bees.",
    "William Blake" : "The busy bee has no time for sorrow.",
    "Brother Adam" : "Listen to the bees and let them guide you.",
    "St John Chrysostom" : "The bee is more honoured than other animals,not because she labors,but because she labours for others.",
    "Congolese" : "When the bee comes to your house, let her have beer; you may want to visit the bee’s house some day.",
    "Eddie Izzard" : "I'm covered in bees!",
}

with open(".token") as fp:
    token = fp.readline().strip()

client = discord.Client()

@client.event
async def on_ready():
    print("Logged in ({}/{})".format(client.user.name, client.user.id))
    await client.change_presence(game=discord.Game(name="with a bee"))

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if "bee" in message.content.lower():
        await client.add_reaction(message, bee_emoji)

    if message.content.lower() == "bee":
        author, quote = random.choice(list(quotes.items()))
        await client.send_message(message.channel, "*\"{}\"* - {}".format(quote, author))

client.run(token)
