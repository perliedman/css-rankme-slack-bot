import sqlite3
import time
import os
import sys
import random
import re
import traceback
import json
from collections import defaultdict

from slackclient import SlackClient
from pack import bestPack
from game_tracker import GameTracker
import linegraph
from skill import get_skill_ranking

def format_list(connection, query, header, format_str, params=()):
    cursor = connection.cursor()
    i = 1
    lines = [header]
    for row in cursor.execute(query, params):
        lines.append(format_str % ((i,) + row))
        i += 1

    return '\n'.join(lines)


def ranking(_, connection, **kwargs):
    score_table = format_list(connection, """
        select
            name, 
            case
                when rounds_tr + rounds_ct > 0 then (cast(score as float) - 1000) / (rounds_tr + rounds_ct)
                else 0 
            end as spr,
            score, 
            case
                when deaths > 0 then cast(kills as float)/deaths 
                else 0
            end as kdr
        from rankme 
        order by score desc""",
                              '%23s%8s%6s%6s' % ('Nick', 'Score/r', 'Score', 'KDR'),
                              '%2d.%20s%8.02f%6d%6.02f')
    return '```\n' + score_table + '```\n:cs: :c4: :cs:'


def headshots(_, connection, **kwargs):
    headshots_table = format_list(connection, """
        select
            name, 
            case
                when kills > 0 then (cast(headshots as float) / kills * 100)
                else 0
            end as percentage, 
            case
                when rounds_tr + rounds_ct > 0 then cast(headshots as float) / (rounds_tr + rounds_ct)
                else 0
            end as spr,
            headshots 
        from rankme 
        order by percentage desc""",
                                  '%23s%6s%8s%6s' % ('Nick', '%', 'HShot/r', 'Total'),
                                  '%d. %20s%6.01f%8.02f%6d')
    return '```\n' + headshots_table + '```\n:disappointed_relieved::gun:'


def last_game(command, connection, **kwargs):
    parts = command.split(' ')
    try:
        rel = int(parts[-1])
    except ValueError:
        rel = 1

    table = format_list(connection, """
                        select
                            lg.name,
                            lg.rounds_tr-pg.rounds_tr+lg.rounds_ct-pg.rounds_ct as rounds,
                            lg.kills-pg.kills as kills,
                            lg.deaths-pg.deaths as deaths,
                            case
                                when lg.deaths-pg.deaths > 0 then (cast(lg.kills as float)-pg.kills)/(lg.deaths - pg.deaths)
                                else 0
                            end as kdr,
                            case
                                when lg.hits-pg.hits > 0 then (cast(lg.hits as float)-pg.hits)/(lg.shots - pg.shots)*100
                                else 0
                            end as hits,
                            lg.score-pg.score as score
                        from rankme as lg
                        inner join game_stats as pg on lg.steam=pg.steam
                        where
                            pg.game_id=(select id from game order by id desc limit 100 offset ?)
                            and rounds > 0
                        order by score desc""",
                        '%23s%7s%6s%7s%6s%5s%6s' % \
                        ('Nick', 'Rounds', 'Kills', 'Deaths', 'KDR', 'Hit%', 'Score'),
                        '%d. %20s%7d%6d%7d%6.02f%5.0f%6d',
                        (rel-1,))

    return '```\n' + table + '```\n:c4:'


def history(_, connection, **kwargs):
    cursor = connection.cursor()
    game_scores = cursor.execute("""
        select rankme.name, IFNULL(game_stats.score, 1000)
        from rankme, game
        left outer join game_stats on rankme.steam=game_stats.steam and game.id=game_stats.game_id
        order by rankme.name, game_id
        """).fetchall()

    games = defaultdict(list)
    for name, score in game_scores:
        games[name].append(score)
    series = games.items()

    graph_url = linegraph.get_chart_url(series)

    return [
        {
            "fallback": "Score History - %s" % graph_url,
            "title": "Score History",
            "title_link": graph_url,
            "text": "Score development over time",
            "image_url": graph_url
        }
    ]


def skill(_, connection, log_db_connection):
    cursor = log_db_connection.cursor()
    rounds = cursor.execute('select win_team, lose_team from rounds order by id').fetchall()
    rounds = [(json.loads(win_team.decode('utf-8')), json.loads(lose_team.decode('utf-8'))) for (win_team, lose_team) in rounds]

    skills = get_skill_ranking(rounds)
    players = dict(cursor.execute('select steam_id, name from players').fetchall())
    leaderboard = zip(range(1, len(skills) + 1), skills)

    return '```' + \
        '%23s%11s' % ('Nick', 'Skill') + '\n' + \
        '\n'.join(['%2d.%20s%5.1f (%3.0f)' % (i, players[steam_id], rating.mu, rating.sigma) for (i, (steam_id, rating)) in leaderboard]) + \
        '```'


def make_teams(command, connection):
    def parse_guests(guests_str):
        guests = []
        for guest in re.split(',\\s*', guests_str):
            match = re.match('(\\S+)\\s*(\\d*)', guest)
            if match:
                try:
                    score = int(match.group(2))
                except ValueError:
                    score = 1000

                guests.append((match.group(1), score))
            else:
                raise 'Could not make sense of guest ```%s```.' % guest

        return guests

    excludes = re.search('exclude(s|) (([^,;]+,*\\s*)+)', command)
    includes = re.search('include(s|) (([^,;]+,*\\s*)+)', command)
    guests = re.search('guest(s|) (([^,;]+,*\\s*)+)', command)
    if excludes:
        params = re.split(',\\s*', excludes.group(2))
        sql = 'select name, score from rankme where name not in (' + \
             ','.join('?'*len(params)) + ')'
    elif includes:
        params = re.split(',\\s*', includes.group(2))
        sql = 'select name, score from rankme where name in (' + \
             ','.join('?'*len(params)) + ')'
    else:
        sql = 'select name, score from rankme'
        params = []

    cursor = connection.cursor()
    nicks = cursor.execute(sql, params).fetchall()

    if guests:
        guests = parse_guests(guests.group(2))
        print guests
        nicks = nicks + guests

    unfiltered_candidates = bestPack(nicks)
    candidates = [(teams, d) for (teams, d) in unfiltered_candidates if d < len(nicks) * 20]
    if len(candidates) == 0:
        candidates = [unfiltered_candidates[0]]

    ((team1, team2), team_diff) = random.choice(candidates)
    sides = ['Terrorists', 'Counter Terrorists']
    side1 = random.choice(sides)
    side2 = [s for s in sides if s != side1][0]

    def print_team(side, team):
        return '*%s*:\n\n%s\n\n' % (side, '\n'.join(['* ' + n for n in team]))

    return print_team(side1, team1) + '\n' + print_team(side2, team2) + \
        '\n\nTeam difference: ' + str(team_diff)


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
                                    last_game('', self._connection) + '\n',
                                    as_user=True)

HANDLERS = {
    'ranking': ranking,
    'headshots': headshots,
    'last': last_game,
    'team': make_teams,
    'history': history,
    'skill': skill
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
