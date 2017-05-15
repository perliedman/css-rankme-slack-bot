import sqlite3
import time
import os
import sys
import traceback

from slackclient import SlackClient
from game_tracker import GameTracker
import handlers

def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                # return text after the @ mention, whitespace removed
                return output['text'].split(AT_BOT)[1].strip().lower(), \
                    output['channel']
    return None, None

def cleanup(slack_client, connection):
    cursor = connection.cursor()
    invalids = cursor.execute('select name from rankme where steam=?',
                              ('STEAM_ID_STOP_IGNORING_RETVALS',)).fetchall()

    if len(invalids):
        cursor.execute('delete from rankme where steam=?', ('STEAM_ID_STOP_IGNORING_RETVALS',))
        cursor.execute('delete from game_stats where steam=?', ('STEAM_ID_STOP_IGNORING_RETVALS',))

        slack_client.api_call('chat.postMessage', channel=CHANNEL,
                              text='I cleaned up these FAKE USERS: ' +
                              ', '.join([i[0] for i in invalids]) +
                              '. SAD!',
                              as_user=True)

class SlackGameTracker(GameTracker):
    def __init__(self, slack_client, db_connection):
        GameTracker.__init__(self, db_connection)
        self._slack_client = slack_client

    def on_game_started(self):
        print 'The game has begun'
        self._slack_client.api_call("chat.postMessage", channel=CHANNEL,
                                    text='The game is on! :c4:', as_user=True)

    def on_game_ended(self):
        print 'The game has ended'
        self._slack_client.api_call("chat.postMessage", channel=CHANNEL,
                                    text='Game over man! Game over!\n\n' +
                                    handlers.last_game('', self._connection) + '\n',
                                    as_user=True)

HANDLERS = {
    'ranking': handlers.ranking,
    'headshots': handlers.headshots,
    'last': handlers.last_game,
    'team': handlers.make_teams,
    'history': handlers.history,
    'skill': handlers.skill,
    'killers': handlers.killers,
    'smokes': handlers.smokes,
    'flashbangs': handlers.flashbangs,
    'hes': handlers.hes,
    'bombplants': handlers.bomb_plants,
    'bombdefuses': handlers.bomb_defuses,
    'blinds': handlers.blinds,
    'jumps': handlers.jumps,
    'radios': handlers.radios,
}

class Bot(object):
    def __init__(self, bot_token, db_path, log_db_path):
        self._slack_client = SlackClient(bot_token)
        self._db_connection = sqlite3.connect(db_path)
        self._log_db_connection = sqlite3.connect(log_db_path)
        self._game_tracker = SlackGameTracker(self._slack_client, self._db_connection)

    def run(self):
        if self._slack_client.rtm_connect():
            count = 0
            while True:
                if count % 10 == 0:
                    self._game_tracker.check_active()
                    cleanup(self._slack_client, self._db_connection)

                count += 1

                command, channel = parse_slack_output(self._slack_client.rtm_read())
                if command and channel:
                    self._handle_command(command, channel)
                time.sleep(READ_WEBSOCKET_DELAY)
        else:
            raise Exception('Connection failed. Invalid Slack token or bot ID?')

    def _handle_command(self, command, channel):
        response = None
        try:
            for (command_prefix, handler) in HANDLERS.items():
                if command.startswith(command_prefix):
                    response = handler(command, self._db_connection, log_db_connection=self._log_db_connection)
                    break
        except Exception, e:
            print traceback.format_exc()
            response = 'Uhm, that did not go as planned: ' + str(e)

        if not response:
            response = 'Huh? Try one of ' + ', '.join(['*' + cmd + '*' for cmd in HANDLERS.keys()])

        if isinstance(response, basestring):
            self._slack_client.api_call("chat.postMessage", channel=channel,
                                        text=response, as_user=True)
        else:
            self._slack_client.api_call("chat.postMessage", channel=channel,
                                        attachments=response, as_user=True)


if __name__ == "__main__":
    # constants
    BOT_ID = os.environ.get("BOT_ID")
    BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
    AT_BOT = "<@" + BOT_ID + ">"
    CHANNEL = '#lanparty'
    READ_WEBSOCKET_DELAY = 1  # 1 second delay between reading from firehose

    while True:
        try:
            Bot(BOT_TOKEN, sys.argv[1], sys.argv[2]).run()
        except:
            print 'Unexpected error; sleeping one minute.'
            print traceback.format_exc()
            time.sleep(60)
