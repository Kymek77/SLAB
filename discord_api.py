import asyncio
import logging
import os
import signal
import threading
import colorama
import discord
import mysql.connector
from discord.compat import create_task
from spotify_api import *
colorama.init(autoreset=True)
# MySQL
database = mysql.connector.connect(
    host=os.environ['db-host'],
    user=os.environ['db-user'],
    passwd=os.environ['db-passwd'],
    database=os.environ['db-dbname']
)
botCursor = database.cursor()

botCursor.execute('SELECT * FROM bot_settings')
settings = botCursor.fetchone()
fields = [item[0] for item in botCursor.description]
settingsDict = {}
for i in range(len(settings)):
    extendDict = {fields[i]: settings[i]}
    settingsDict.update(extendDict)
boundChannelsStr = settingsDict['boundChannels']
boundChannelsList = boundChannelsStr.split()
settingsDict['boundChannels'] = boundChannelsList

# Variables & classes
class MyFormatter(logging.Formatter):
    info_fmt = ('%(name)s || %(levelname)s: %(message)s')
    warn_fmt = ('\033[36m%(name)s || %(levelname)s: %(message)s')
    err_fmt = ('\033[33m%(name)s || %(levelname)s: %(message)s')
    crit_fmt = ('\033[31m%(name)s || %(levelname)s: %(message)s')
    def __init__(self):
        super().__init__(fmt='%(levelno)d: %(msg)s', datefmt=None, style='%')
    def format(self, record):
        format_orig = self._style._fmt
        if record.levelno == logging.INFO:
            self._style._fmt = MyFormatter.info_fmt
        elif record.levelno == logging.WARNING:
            self._style._fmt = MyFormatter.warn_fmt
        elif record.levelno == logging.ERROR:
            self._style._fmt = MyFormatter.err_fmt
        elif record.levelno == logging.CRITICAL:
            self._style._fmt = MyFormatter.crit_fmt
        result = logging.Formatter.format(self, record)
        self._style_fmt = format_orig
        return result
stopCode = False
formInst = MyFormatter()
logger = logging.getLogger('DiscordAPI')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formInst)
logger.addHandler(ch)
PREF = settingsDict['prefix']
boundChannels = settingsDict['boundChannels']
DISCORDTOKEN = settingsDict['discordToken']
clamp = lambda n, minn, maxn: max(min(maxn, n), minn)
# <----->

client = discord.Client()


async def statusChange():
    global statusRun
    if os.environ['bot-build'] == 'dev':
        suffix = '-dev'
    elif os.environ['bot-build'] == 'stable':
        suffix = '-stable'
    await client.wait_until_ready()
    botVersion = os.environ['botVersion']
    while 1:
        try:
            await client.wait_until_ready()
            await client.change_presence(game=discord.Game(name='SLAB v{}{}'.format(botVersion, suffix)))
            await asyncio.sleep(15)
            helpStr = 'Type %shelp for help!' % PREF
            await client.change_presence(game=discord.Game(name=helpStr))
            await asyncio.sleep(15)
        except BaseException as err:
            logger.critical('Exception occurred: {} '.format(err))
            break

@client.event
async def on_message(message):
    global PREF
    global boundChannels

    if message.author == client.user:
        return
    if message.author.bot:
        return

    if message.content.lower().startswith('%sbind' % PREF):
        logger.info(
            ('Received command > bind | From {0.author} in {0.server.name}/{0.channel}'.format(message)))
        if (message.author.roles[len(message.author.roles)-1].permissions.administrator or message.author.roles[len(message.author.roles)-1].permissions.manage_channels or message.author.roles[len(message.author.roles)-1].permissions.manage_server) or (message.author.id == '312223735505747968') == True:
            if message.channel.id in boundChannels:
                await client.send_message(message.channel, 'Already bound')
            else:
                boundChannels.append(message.channel.id)
                await dbUpdateSettings(
                    ['boundChannels', ' '.join(boundChannels)])
                await client.send_message(message.channel, '***Bound to this channel.***')
                return boundChannels
        else:
            await client.send_message(message.channel, ':x:***You are not allowed to execute that command!***')

    if message.content.lower().startswith('%sunbind' % PREF):
        logger.info((
            'Received command > unbind | From {0.author} in {0.server.name}/{0.channel}'.format(message)))
        if (message.author.roles[len(message.author.roles)-1].permissions.administrator or message.author.roles[len(message.author.roles)-1].permissions.manage_channels or message.author.roles[len(message.author.roles)-1].permissions.manage_server) or (message.author.id == '312223735505747968') == True:
            if message.channel.id not in boundChannels:
                await client.send_message(message.channel, 'Not binded')
            else:
                boundChannels.remove(message.channel.id)
                await dbUpdateSettings(
                    ['boundChannels', ' '.join(boundChannels)])
                await client.send_message(message.channel, '***Unbound from this channel.***')
                return boundChannels
        else:
            await client.send_message(message.channel, ':x:***You are not allowed to execute that command!***')

    elif message.channel.id in boundChannels:
        # ? Should this even be here?
        if message.content.lower().startswith('%shello' % PREF):
            msg = 'Hello {0.author.mention}'.format(message)
            await client.send_message(message.channel, msg)
            logger.info(
                ('Received command > hello | From {0.author} in {0.server.name}/{0.channel}'.format(message)))

        elif message.content.lower().startswith('%ssearch' % PREF):
            msg = message.content
            msgList = msg.split()
            msgList.pop(0)

            if msgList == []:
                await client.send_message(message.channel, ':x:** Proper use:** `%ssearch <query/song URI>`' % PREF)
                return

            msg = ' '.join(msgList)
            logger.info(
                ('Received command > search >> {1} | From {0.author} in {0.server.name}/{0.channel}'.format(message, msg)))
            # await client.send_message(message.channel, msg)
            response = await searchSong(msg)

            if response[0] == 1:
                await client.send_message(message.channel, 'Something went wrong. Try again.')

            elif response[0] == 2:
                await client.send_message(message.channel, 'No results.')

            elif response[0] == 3:
                await client.send_message(message.channel, 'Invalid URI. Try copying/pasting it again.')

            elif response[0] == 4:
                await client.send_message(message.channel, 'No track with that URI. Try copying/pasting it again.')

            elif response[0] == 0:
                await client.send_message(message.channel, 'Is this the song you are looking for?')
                await client.send_message(message.channel, response[1])
                await client.send_message(message.channel, 'If yes, type `{0}yes <playlist\'s name>` to add to playlist or `{0}no` to cancel'.format(PREF))

                def agreement(ans):
                    if ans.content.lower().startswith('%syes' % PREF):
                        return('yes')
                    else:
                        return('no')

                ans = await client.wait_for_message(author=message.author, check=agreement, timeout=30)

                if ans.content.lower().startswith('{}yes'.format(PREF)):
                    plName = ' '.join(ans.content.split()[1:])
                    admin = False
                    if (message.author.roles[len(message.author.roles)-1].permissions.administrator or message.author.roles[len(message.author.roles)-1].permissions.manage_channels or message.author.roles[len(message.author.roles)-1].permissions.manage_server) or (message.author.id == '312223735505747968') == True: admin = True
                    addResp = await addToPlaylist(plName, response[2], message.author.id, admin)
                    if addResp[0] == 0:
                        await client.send_message(message.channel, 'Successfully added to playlist `{}`'.format(plName))
                    elif addResp[0] == 1:
                        await client.send_message(message.channel, 'Unable to add to playlist `{}`'.format(plName))
                    elif addResp[0] == 2:
                        await client.send_message(message.channel, 'No playlist named `{}` or no playlists'.format(plName))
                    elif addResp[0] == 3:
                        await client.send_message(message.channel, 'You already done your part creating the playlist')
                elif ans.content.lower().startswith('{}no'.format(PREF)):
                    await client.send_message(message.channel, 'Cancelled.')
                else:
                    await client.send_message(message.channel, 'Invalid answer. Cancelling.')

        elif message.content.lower().startswith('%screateplaylist' % PREF):
            if (message.author.roles[len(message.author.roles)-1].permissions.administrator or message.author.roles[len(message.author.roles)-1].permissions.manage_channels or message.author.roles[len(message.author.roles)-1].permissions.manage_server) or (message.author.id == '312223735505747968') == True:

                msg = message.content.lower()
                msgList = msg.split()
                msgList.pop(0)

                if msgList == []:
                    await client.send_message(message.channel, ':x:** Proper use:** `%screateplaylist <playlist name>`' % PREF)
                    return

                msg = ' '.join(msgList)
                logger.info(
                    ('Received command > create >> {1} | From {0.author} in {0.server.name}/{0.channel}'.format(message, msg)))
                response = await createPlaylist(msg)

                if response[0] == 1:
                    await client.send_message(message.channel, 'Error creating playlist.')

                elif response[0] == 2:
                    await client.send_message(message.channel, 'Playlist with that name already exists.')

                elif response[0] == 3:
                    await client.send_message(message.channel, 'Invalid character(s). Remove or replace any non-ascii characters.')

                elif response[0] == 0:
                    await client.send_message(message.channel, 'Successfully created playlist `{}`'.format(msg))
                    await client.send_message(message.channel, response[1])
            else:
                await client.send_message(message.channel, ':x:***You are not allowed to execute that command!***')

        elif message.content.lower().startswith('%sdeleteplaylist' % PREF):
            msg = message.content.lower()
            msgList = msg.split()
            msgList.pop(0)

            if msgList == []:
                await client.send_message(message.channel, ':x:** Proper use:** `%sdeleteplaylist <playlist name>`' % PREF)
                return

            msg = ' '.join(msgList)
            logger.info(
                ('Received command > delete >> {1} | From {0.author} in {0.server.name}/{0.channel}'.format(message, msg)))
            if (message.author.roles[len(message.author.roles)-1].permissions.administrator or message.author.roles[len(message.author.roles)-1].permissions.manage_channels or message.author.roles[len(message.author.roles)-1].permissions.manage_server) or (message.author.id == '312223735505747968') == True:

                response = await removePlaylist(msg)

                if response[0] == 1:
                    await client.send_message(message.channel, 'Error deleting playlist.')

                elif response[0] == 2:
                    await client.send_message(message.channel, 'No playlist with that name.')

                elif response[0] == 3:
                    await client.send_message(message.channel, 'Invalid character(s). Remove or replace any non-ascii characters.')

                elif response[0] == 0:
                    await client.send_message(message.channel, 'Successfully deleted playlist `{}`'.format(msg))
            else:
                await client.send_message(message.channel, ':x:***You are not allowed to execute that command!***')

        elif message.content.lower().startswith('%splaylists' % PREF):
            logger.info(
                ('Received command > playlists | From {0.author} in {0.server.name}/{0.channel}'.format(message)))
            response = await getPlaylists()
            if response[0] == 1:
                await client.send_message(message.channel, 'Error getting playlists.')
            if response[0] == 2:
                await client.send_message(message.channel, 'No playlists.')
            elif response[0] == 0:
                user = await client.get_user_info('312223735505747968')
                playlistsEmbed = discord.Embed(color=discord.Color.green())
                playlistsEmbed.set_author(
                    name='SLAB playlists', icon_url=client.connection.user.avatar_url)
                for item in response[1]:
                    playlistsEmbed.add_field(
                        name=item[0], value=item[1], inline=True)
                playlistsEmbed.set_footer(text='Made with 💖 by {0.name}#{0.discriminator}'.format(
                    user), icon_url=user.avatar_url)
                await client.send_message(message.channel, embed=playlistsEmbed)

        elif message.content.lower().startswith('%sprefix' % PREF):
            if (message.author.roles[len(message.author.roles)-1].permissions.administrator or message.author.roles[len(message.author.roles)-1].permissions.manage_channels or message.author.roles[len(message.author.roles)-1].permissions.manage_server) or (message.author.id == '312223735505747968') == True:
                msg = message.content.lower()
                msgList = msg.split()
                msgList.pop(0)

                if msgList == []:
                    await client.send_message(message.channel, ':x:** Proper use:** `%sprefix <prefix>`' % PREF)
                    return

                msg = ' '.join(msgList)
                logger.info(
                    ('Received command > prefix >> {1} | From {0.author} in {0.server.name}/{0.channel}'.format(message, msg)))
                PREF = msg
                await client.send_message(message.channel, 'Changed prefix to `%s`' % PREF)
                await dbUpdateSettings((['prefix', PREF]))
                return PREF
            else:
                await client.send_message(message.channel, ':x:***You are not allowed to execute that command!***')

        elif message.content.lower().startswith('%shelp' % PREF):
            logger.info(
                ('Received command > help | From {0.author} in {0.server.name}/{0.channel}'.format(message)))
            user = await client.get_user_info('312223735505747968')
            helpEmbed = discord.Embed(
                color=discord.Color.green()
            )
            helpEmbed.set_author(
                name='SLAB Help', icon_url=client.connection.user.avatar_url)
            helpEmbed.add_field(name='%shelp' %
                                PREF, value='Shows this help', inline=True)
            helpEmbed.add_field(
                name='%sverify' % PREF, value='Allows you to obtain Premium:star: role', inline=False)
            helpEmbed.add_field(name='%ssearch <query>' % PREF,
                                value='Allows you to search for a song to add to playlist', inline=True)
            helpEmbed.add_field(name='%sdelete <uri> <playlist>' % PREF,
                                value='Deletes song with <uri> from <playlist>', inline=True)
            helpEmbed.add_field(
                name='%splaylists' % PREF, value='Shows list of available playlists', inline=True)
            helpEmbed.add_field(name='%splaylist <name>' % PREF,
                                value='Shows the requested playlist', inline=True)
            helpEmbed.add_field(name='%screateplaylist <name>' % PREF,
                                value='Creates playlist with name <name>', inline=True)
            helpEmbed.add_field(name='%sdeleteplaylist <name>' % PREF,
                                value='Deletes playlist with name <name>', inline=True)
            helpEmbed.add_field(name='%sprefix <prefix>' % PREF,
                                value='Sets new <prefix> for commands', inline=True)
            helpEmbed.add_field(
                name='%sbind' % PREF, value='Binds bot to current channel', inline=True)
            helpEmbed.add_field(
                name='%sunbind' % PREF, value='Unbinds bot from current channel', inline=True)
            helpEmbed.add_field(
                name='%sclear <number>'%PREF, value='Clears number of messages in current channel', inline=True)
            helpEmbed.set_footer(text='Made with 💖 by {0.name}#{0.discriminator}'.format(
                user), icon_url=user.avatar_url)
            await client.send_message(message.channel, embed=helpEmbed)

        elif message.content.lower().startswith('%sverify' % PREF):
            logger.info(
                ('Received command > verify | From {0.author} in {0.server.name}/{0.channel}'.format(message)))
            serverObj = client.get_server(message.server.id)
            memberObj = message.author
            response = await verifyPremiumStep1()
            await client.send_message(message.author, ('To verify the account go to the following page and paste in the token:\n' + response))
            answ = await client.wait_for_message(author=message.author, timeout=600)
            authResponse = await verifyPremiumStep2(answ.content)
            if authResponse == True:
                await client.send_message(message.author, 'You have premium subscription. You just got `PREMIUM ⭐` role')
                role = discord.utils.get(serverObj.roles, name='PREMIUM ⭐')
                await client.add_roles(memberObj, role)
            elif authResponse == False:
                await client.send_message(message.author, 'You don\'t have a premium subscribtion')
            else:
                await client.send_message(message.author, authResponse)

        elif message.content.lower().startswith('%sdelete' % PREF):
            if (message.author.roles[len(message.author.roles)-1].permissions.administrator or message.author.roles[len(message.author.roles)-1].permissions.manage_channels or message.author.roles[len(message.author.roles)-1].permissions.manage_server) or (message.author.id == '312223735505747968') == True:
                msg = message.content
                msgList = msg.split()
                msgList.pop(0)

                if msgList == []:
                    await client.send_message(message.channel, ':x:** Proper use:** `%sdelete <song URI> <playlist name>`' % PREF)
                    return

                playlistName = ' '.join(msgList[1:])
                logger.info(('Received command > delete >> {1} - {2} | From {0.author} in {0.server.name}/{0.channel}'.format(message, msgList[0], playlistName)))
                response = await removeSong(msgList[0], playlistName)

                if response[0] == 1:
                    await client.send_message(message.channel, 'Error deleting song.')
                elif response[0] == 2:
                    await client.send_message(message.channel, 'No playlists')
                elif response[0] == 3:
                    await client.send_message(message.channel, 'Invalid character(s). Remove or replace any non-ascii characters.')
                elif response[0] == 4:
                    await client.send_message(message.channel, 'No playlists with name `{}`'.format(msg[0]))
                elif response[0] == 0:
                    await client.send_message(message.channel, 'Song successfully removed.')
            else:
                await client.send_message(message.channel, ':x:***You are not allowed to execute that command!***')

        elif message.content.lower().startswith('%splaylist' % PREF):
            msg = message.content.lower()
            msgList = msg.split()
            msgList.pop(0)

            if msgList == []:
                await client.send_message(message.channel, ':x:** Proper use:** `%splaylist <playlist\'s name>`' % PREF)
                return

            msg = ' '.join(msgList)
            logger.info(
                ('Received command > playlist >> {1} | From {0.author} in {0.server.name}/{0.channel}'.format(message, msg)))

            response = await getPlaylist(msg)

            if response[0] == 1:
                await client.send_message(message.channel, 'No playlist with name `{}`'.format(msg))
            elif response[0] == 2:
                await client.send_message(message.channel, 'No playlists.')
            elif response[0] == 3:
                await client.send_message(message.channel, 'Invalid character(s). Remove or replace any non-ascii characters.')
            elif response[0] == 0:
                await client.send_message(message.channel, response[1])

        elif message.content.lower().startswith('%sclear' % PREF):
            if (message.author.roles[len(message.author.roles)-1].permissions.administrator or message.author.roles[len(message.author.roles)-1].permissions.manage_channels or message.author.roles[len(message.author.roles)-1].permissions.manage_server) or (message.author.id == '312223735505747968') == True:
                msg = message.content.lower()
                msgList = msg.split()
                msgList.pop(0)
                if msgList == []:
                    return
                limit = int(msgList[0])
                limit + 1
                limit = clamp(n=limit, minn=2, maxn=100)
                channel = message.channel
                messages = []
                async for message in client.logs_from(channel, limit=limit):
                    messages.append(message)
                await client.delete_messages(messages)

    elif message.content.lower().startswith('%sdebug' % PREF):
        for role in message.author.roles:
            await client.send_message(message.author, ', '.join(str(x) for x in [role, role.id, role.name, role.permissions, role.server, role.color, role.hoist, role.position, role.managed, role.mentionable, role.is_everyone, role.created_at, role.mention]))
            await client.send_message(message.author, '=====')
        await client.send_message(message.author, 'Finished')

@client.event
async def on_ready():
    logger.info(('Logging in as:'))
    logger.info((client.user.name))
    logger.info((client.user.id))
    logger.info(('------'))

@client.event
async def on_resumed():
    logger.info('Reconnected')

@client.event
async def on_member_update(bef, aft):
    if '408991159990616074' in [y.id for y in bef.roles]:
        if '408991159990616074' not in [y.id for y in aft.roles]:
            await client.send_message(discord.Object(id='409023617549205515'), '{0}, if you want to obtain PREMIUM ⭐ role, type in `{1}verify` in {2}'.format(aft.mention, PREF, aft.server._channels['409066385453613079'].mention))

if __name__ == "__main__":
    logger.info(('Starting code...'))
    client.loop.create_task(statusChange())
    while True:
        try:
            client.loop.run_until_complete(client.start(DISCORDTOKEN))
        except SystemExit as err:
            logger.info('Stopping code... (SystemExit)')
            stopCode = True
            client.logout()
            logger.info('Stopped code')
        except KeyboardInterrupt as err:
            logger.info('Stopping code... (KeyboardInterrupt)')
            stopCode = True
            client.logout()
            logger.info('Stopped code')
        except RuntimeError as err:
            logger.critical('Exception occurred: {} '.format(err))
            client.close()
        except BaseException as err:
            logger.critical('Exception occurred: {} '.format(err))
            logger.info('Trying to reconnect...')
            client.logout()
        if stopCode:
            break
    exit(0)
