""" Example of how to use slash commands to use /bump command """


import discord
from discord.ext import commands, tasks
import asyncio
from dotenv import load_dotenv
import os
import random
import time

load_dotenv()

# Initialize the bot
bot = commands.Bot(command_prefix=';', case_insensitive=True, self_bot=True, chunk_guilds_at_startup=False, request_guilds=False)
bot.remove_command('help')

# Load environment variables
token = os.getenv("JIA")

# Bump channels 
channel_ids = [1364364743766442004, 1269617846627860651]
command_id = 947088344167366698
# cooldown
cooldown = 10
# Bump history
bump_history = {}

name = "Ji-A"

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    auto_bump.start()


@tasks.loop(minutes=cooldown)
async def auto_bump():
    global cooldown, bump_history
    try:
        await asyncio.sleep(random.randint(23, 41))
        is_bumped = False
        for channel_id in channel_ids:
            
            channel = bot.get_channel(channel_id)
            if not channel:
                print(f"🚫 {name} | Channel with ID {channel_id} not found.")
                return
    
            # check if it's on cooldown
            if channel_id in bump_history:
                last_bump_time = bump_history[channel_id].get('last_bump', 0)
                time_now = time.time()
                if time_now - last_bump_time < (2 * 60 * 60):
                    print(f"⏳ {name} | {channel.name} still on cooldown.")
                    continue 
                
            commands = await channel.application_commands()
            for command in commands:
                if command.id == command_id:
                    try:
                        response = await command.__call__(channel=channel)
                        if not response.message.flags.ephemeral:
                            print(f"✅ {name} | Successfully bumped in {channel.name}.")
                            bump_history[channel_id] = {'last_bump': time.time()}
                            is_bumped = True
                            await asyncio.sleep(2100)
                        else:
                            print(f"❌ {name} | Failed to bump in {channel.name}, still on cooldown.")
                            is_bumped = False
                        break
                    except Exception as e:
                        is_bumped = False
                        print(f"❗{name} | Error executing bump command: {e}")
                        break 
            if is_bumped:
                return 
            else:
                await asyncio.sleep(10)
    except Exception as e:
        print(f"Error in auto_bump: {e}")

async def run_bot():
    await bot.start(token, reconnect=True)
