import discord
from discord.compat import create_task
import mysql.connector
import asyncio
import spotify_api as sapi
import os
import signal

## MySQL
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

# Variables
PREF = settingsDict['prefix']
boundChannels = settingsDict['boundChannels']
DISCORDTOKEN = settingsDict['discordToken']
# <----->

# Classes
class GracefulKiller:
    kill_now = False
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracegully)

    def exit_gracefully(self, signum, frame):
        self.kill_now = True 


client = discord.Client()

async def statusChange():
    suffix = ''
    if os.environ['bot-build'] == 'dev':
        suffix = '-dev'
    elif os.environ['bot-build'] == 'stable':
        suffix = '-stable'
    await client.wait_until_ready()
    while not client.is_closed:
        while 1:
            await client.change_presence(game = discord.Game(name='SLAB v0.2.2{}'.format(suffix)))
            await asyncio.sleep(15)
            helpStr = 'Type %shelp for help!' % PREF
            await client.change_presence(game = discord.Game(name=helpStr))
            await asyncio.sleep(15)

@client.event
async def on_message(message):
    global PREF
    global boundChannels
    
    if message.author == client.user:
        return
    if message.author.bot: return

    if message.content.lower().startswith('%sbind' % PREF):
        print('Received command > bind | From {0.author} in {0.server.name}/{0.channel}'.format(message))
        if (message.author.roles[len(message.author.roles)-1].permissions.administrator or message.author.roles[len(message.author.roles)-1].permissions.manage_channels or message.author.roles[len(message.author.roles)-1].permissions.manage_server) or (message.author.id == '312223735505747968') == True:
            if message.channel.id in boundChannels:
                await client.send_message(message.channel, 'Already bound')
            else:
                boundChannels.append(message.channel.id)
                sapi.dbUpdateSettings(['boundChannels', ' '.join(boundChannels)])
                await client.send_message(message.channel, '***Bound to this channel.***')
                return boundChannels
        else:
            await client.send_message(message.channel, ':x:***You are not allowed to execute that command!***')
    
    if message.content.lower().startswith('%sunbind' % PREF):
        print('Received command > unbind | From {0.author} in {0.server.name}/{0.channel}'.format(message))
        if (message.author.roles[len(message.author.roles)-1].permissions.administrator or message.author.roles[len(message.author.roles)-1].permissions.manage_channels or message.author.roles[len(message.author.roles)-1].permissions.manage_server) or (message.author.id == '312223735505747968') == True:
            if message.channel.id not in boundChannels:
                await client.send_message(message.channel, 'Not binded')
            else:
                boundChannels.remove(message.channel.id)
                sapi.dbUpdateSettings(['boundChannels', ' '.join(boundChannels)])
                await client.send_message(message.channel, '***Unbound from this channel.***')
                return boundChannels
        else:
            await client.send_message(message.channel, ':x:***You are not allowed to execute that command!***')

    elif message.channel.id in boundChannels:
        ### ? Should this even be here?
        if message.content.lower().startswith('%shello' % PREF):
            msg = 'Hello {0.author.mention}'.format(message)
            await client.send_message(message.channel, msg)
            print('Received command > hello | From {0.author} in {0.server.name}/{0.channel}'.format(message))
            
        ### TODO: Update search to accomodate URI and adding to playlist with name
        elif message.content.lower().startswith('%ssearch' % PREF):
            msg = message.content.lower()
            msgList = msg.split()
            msgList.pop(0)
            
            if msgList == []:
                await client.send_message(message.channel, ':x:** Proper use:** `%ssearch <query/song URI>`' % PREF)
                return
            
            msg = ' '.join(msgList)
            print('Received command > search >> {1} | From {0.author} in {0.server.name}/{0.channel}'.format(message, msg))
            # await client.send_message(message.channel, msg)
            response = sapi.searchSong(msg)
            
            if response[0] == 1:
                await client.send_message(message.channel, 'Something went wrong. Try again.')
                
            elif response[0] == 2:
                await client.send_message(message.channel, 'No results.')
                
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
                    plName = ans.content
                    plName = plName.split()
                    plName.pop(0)
                    await client.send_message(message.channel, 'Adding to playlist.')
                    addResp = sapi.addToPlaylist(plName, response[2], message.author.id)
                    if addResp[0] == 0:
                        await client.send_message(message.channel, 'Successfully added to playlist `{}`'.format(plName))
                    elif addResp[0] == 1:
                        await client.send_message(message.channel, 'Unable to add to playlist `{}`'.format(plName))
                    elif addResp[0] == 2:
                        await client.send_message(message.channel, 'No playlist named `{}`'.format(plName))
                elif ans.content.lower().startswith == '{}no'.format(PREF):
                    await client.send_message(message.channel, 'Cancelled.')
                else:
                    await client.send_message(message.channel, 'Invalid answer. Cancelling.')
                    
        elif message.content.lower().startswith('%screate' % PREF):
            if (message.author.roles[len(message.author.roles)-1].permissions.administrator or message.author.roles[len(message.author.roles)-1].permissions.manage_channels or message.author.roles[len(message.author.roles)-1].permissions.manage_server) or (message.author.id == '312223735505747968') == True:
                
                msg = message.content.lower()
                msgList = msg.split()
                msgList.pop(0)
                
                if msgList == []:
                    await client.send_message(message.channel, ':x:** Proper use:** `%screate <playlist name>`' % PREF)
                    return
                
                msg = ' '.join(msgList)
                print('Received command > create >> {1} | From {0.author} in {0.server.name}/{0.channel}'.format(message, msg))
                response = sapi.createPlaylist(msg)
                
                if response[0] == 'Error creating playlist.':
                    await client.send_message(message.channel, response[0])
                    
                elif response[0] == 'Playlist already exists.':
                    await client.send_message(message.channel, response[0])
                    
                elif response[0] != 'Error creating playlist.' or 'Playlist already exists.':
                    await client.send_message(message.channel, response[0])
                    await client.send_message(message.channel, response[1]['playlist_url'])
            else:
                await client.send_message(message.channel, ':x:***You are not allowed to execute that command!***')
                
        elif message.content.lower().startswith('%sdeleteplaylist' % PREF):
            print('Received command > delete | From {0.author} in {0.server.name}/{0.channel}'.format(message))
            if (message.author.roles[len(message.author.roles)-1].permissions.administrator or message.author.roles[len(message.author.roles)-1].permissions.manage_channels or message.author.roles[len(message.author.roles)-1].permissions.manage_server) or (message.author.id == '312223735505747968') == True:
                response = sapi.removePlaylist()
                
                if response == 'Deleted successfully.':
                    await client.send_message(message.channel, response)
                else:
                    await client.send_message(message.channel, response)
            else:
                await client.send_message(message.channel, ':x:***You are not allowed to execute that command!***')
        
        ### TODO: Update for accomodating multiple playlists
        elif message.content.lower().startswith('%splaylist' % PREF):
            print('Received command > playlist | From {0.author} in {0.server.name}/{0.channel}'.format(message))
            response = sapi.getPlaylist()
            await client.send_message(message.channel, response)
            
        elif message.content.lower().startswith('%sprefix' % PREF):
            if (message.author.roles[len(message.author.roles)-1].permissions.administrator or message.author.roles[len(message.author.roles)-1].permissions.manage_channels or message.author.roles[len(message.author.roles)-1].permissions.manage_server) or (message.author.id == '312223735505747968') == True:
                msg = message.content.lower()
                msgList = msg.split()
                msgList.pop(0)
                
                if msgList == []:
                    await client.send_message(message.channel, ':x:** Proper use:** `%sprefix <prefix>`' % PREF)
                    return
                
                msg = ' '.join(msgList)
                print('Received command > prefix >> {1} | From {0.author} in {0.server.name}/{0.channel}'.format(message, msg))
                PREF = msg
                await client.send_message(message.channel, 'Changed prefix to `%s`' % PREF)
                sapi.dbUpdateSettings((['prefix', PREF]))
                return PREF
            else:
                await client.send_message(message.channel, ':x:***You are not allowed to execute that command!***')
                
        elif message.content.lower().startswith('%shelp' % PREF):
            print('Received command > help | From {0.author} in {0.server.name}/{0.channel}'.format(message))
            helpEmbed = discord.Embed(
                color = discord.Color.green()
            )
            helpEmbed.set_author(name='SLAB Help', icon_url=client.connection.user.avatar_url)
            helpEmbed.add_field(name='%shelp'%PREF, value='Shows this help', inline=True)
            helpEmbed.add_field(name='%sverify'%PREF, value='Allows you to obtain Premium:star: role', inline=False)
            helpEmbed.add_field(name='%ssearch <query>'%PREF, value='~Not yet available~ Allows you to search for a song to add to playlist', inline=False)
            helpEmbed.add_field(name='%splaylists'%PREF, value='~Not yet available~ Shows list of available playlists', inline=True)
            helpEmbed.add_field(name='%splaylist <name>'%PREF, value='~Not yet available~ Shows the requested playlist', inline=True)
            helpEmbed.add_field(name='%screate <name>'%PREF, value='~Not yet available~ Creates playlist with name <name>', inline=True)
            helpEmbed.add_field(name='%sdelete <name>'%PREF, value='~Not yet available~ Deletes playlist with name <name>', inline=True)
            helpEmbed.add_field(name='%sprefix'%PREF, value='Sets new prefix for commands', inline=True)
            helpEmbed.add_field(name='%sbind'%PREF, value='Binds bot to current channel', inline=True)
            helpEmbed.add_field(name='%sunbind'%PREF, value='Unbinds bot from current channel', inline=True)
            await client.send_message(message.channel, embed=helpEmbed)

        elif message.content.lower().startswith('%sverify' % PREF):
            print('Received command > verify | From {0.author} in {0.server.name}/{0.channel}'.format(message))
            serverObj = client.get_server(message.server.id)
            memberObj = message.author
            response = sapi.verifyPremiumStep1()
            await client.send_message(message.author, ('To verify the account go to the following page and paste in the token:\n' + response))
            answ = await client.wait_for_message(author=message.author, timeout=60)
            authResponse = sapi.verifyPremiumStep2(answ.content)
            if authResponse == True:
                await client.send_message(message.author, 'You have premium subscription. You just got `PREMIUM ⭐` role')
                role = discord.utils.get(serverObj.roles, name='PREMIUM ⭐')
                await client.add_roles(memberObj, role)
            elif authResponse == False:
                await client.send_message(message.author, 'You don\'t have a premium subscribtion')
            else:
                await client.send_message(message.author, authResponse)

    
@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')

client.loop.create_task(statusChange())
client.run(DISCORDTOKEN)