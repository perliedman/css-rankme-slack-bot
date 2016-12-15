import sqlite3
from slackclient import SlackClient
import time
import os
import sys


def format_list(query, header, format, params=()):
    c = conn.cursor()
    i = 1
    lines = [header]
    for row in c.execute(query, params):
        lines.append(format % ((i,) + row))
        i += 1

    return '\n'.join(lines)


def print_score():
    return format_list('select name, (cast(score as float) - 1000) / (rounds_tr + rounds_ct) as spr, score, cast(kills as float)/deaths from rankme order by spr desc',
                       '%23s%8s%6s%6s' % ('Nick', 'Score/r', 'Score', 'KDR'),
                       '%2d.%20s%8.02f%6d%6.02f')


def print_headshots():
    return format_list('select name, cast(headshots as float) / (rounds_tr + rounds_ct) as spr, headshots from rankme order by spr desc',
                       '%23s%8s%6s' % ('Nick', 'HShot/r', 'Total'),
                       '%d. %20s%8.02f%6d')


def print_last_game(rel=1):
    return format_list("""
                        select
                            lg.name,
                            lg.rounds_tr-pg.rounds_tr+lg.rounds_ct-pg.rounds_ct as rounds,
                            lg.kills-pg.kills as kills,
                            lg.deaths-pg.deaths as deaths,
                            case
                                when lg.deaths-pg.deaths > 0 then (cast(lg.kills as float)-pg.kills)/(lg.deaths - pg.deaths)
                                else 0
                            end as kdr,
                            lg.score-pg.score as score
                        from rankme as lg
                        inner join game_stats as pg on lg.steam=pg.steam
                        where
                            pg.game_id=(select id from game order by id desc limit 100 offset ?)
                            and rounds > 0
                        order by score desc""",
                       '%23s%7s%6s%7s%6s%6s' % ('Nick', 'Rounds', 'Kills', 'Deaths', 'KDR', 'Score'),
                       '%d. %20s%7d%6d%7d%6.02f%6d',
                       (rel-1,))

# constants
BOT_ID = os.environ.get("BOT_ID")
AT_BOT = "<@" + BOT_ID + ">"
CHANNEL = '#lanparty'


def handle_command(command, channel):
    response = "Not sure what you mean. Try *ranking* or *headshots*."
    if command.startswith('ranking'):
        response = '```\n' + print_score() + '```\n:cs: :c4: :cs:'
    elif command.startswith('headshots'):
        response = '```\n' + print_headshots() + '```\n:disappointed_relieved::gun:'
    elif command.startswith('last'):
        parts = command.split(' ')
        try:
            rel = int(parts[-1])
        except ValueError:
            rel = 1
        response = '```\n' + print_last_game(rel) + '```\n:c4:'
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True)


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


last_score = None
last_active = None
is_active = False


def check_active():
    global last_score, last_active, is_active
    c = conn.cursor()
    score = c.execute('select sum(score) from rankme').fetchone()[0]
    now = time.time()

    print 'Score is %d; last score is %d at % .0f' % (score, last_score if not last_score is None else -1, now)

    if not last_score is None and score != last_score:
        if not is_active:
            is_active = True
            print 'The game has begun'
            slack_client.api_call("chat.postMessage", channel=CHANNEL,
                                  text='The game is on! :c4:', as_user=True)
            c = conn.cursor()
            c.execute('insert into game (start_time) values (?)', (now,))
            game_id = c.lastrowid
            c.execute("""insert into game_stats (game_id, steam,
                name, lastip, score, kills, deaths, suicides, tk, shots, hits, headshots, connected, rounds_tr, rounds_ct, lastconnect,
                knife,glock,usp,p228,deagle,
                elite ,fiveseven ,m3 ,xm1014 ,mac10 ,
                tmp ,mp5navy ,ump45 ,p90 ,galil ,
                ak47 ,sg550 ,famas ,m4a1 ,aug ,
                scout ,sg552 ,awp ,g3sg1 ,m249 ,
                hegrenade ,flashbang ,smokegrenade , head ,
                chest , stomach , left_arm , right_arm ,
                left_leg , right_leg ,c4_planted ,c4_exploded ,
                c4_defused ,ct_win , tr_win , hostages_rescued ,
                vip_killed , vip_escaped , vip_played) select ?, steam,
                name, lastip, score, kills, deaths, suicides, tk, shots, hits, headshots, connected, rounds_tr, rounds_ct, lastconnect,
                knife,glock,usp,p228,deagle,
                elite ,fiveseven ,m3 ,xm1014 ,mac10 ,
                tmp ,mp5navy ,ump45 ,p90 ,galil ,
                ak47 ,sg550 ,famas ,m4a1 ,aug ,
                scout ,sg552 ,awp ,g3sg1 ,m249 ,
                hegrenade ,flashbang ,smokegrenade , head ,
                chest , stomach , left_arm , right_arm ,
                left_leg , right_leg ,c4_planted ,c4_exploded ,
                c4_defused ,ct_win , tr_win , hostages_rescued ,
                vip_killed , vip_escaped , vip_played from rankme""", (game_id,))
            conn.commit()

        last_active = now
    elif not last_active is None and now - last_active > 120:
        if is_active:
            is_active = False
            print 'The game has ended'
            slack_client.api_call("chat.postMessage", channel=CHANNEL,
                                  text='Game over man! Game over!\n\n```' + print_last_game() + '```\nhttp://giphy.com/gifs/arnold-schwarzenegger-windows-cs-CFjw7eSxjJL8I', as_user=True)
            c = conn.cursor()
            last_game_id = c.execute('select max(id) from game').fetchone()[0]
            c.execute('update game set end_time=? where id=?', (now, last_game_id))
            conn.commit()

    last_score = score

if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1  # 1 second delay between reading from firehose

    while True:
        try:
            slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
            conn = sqlite3.connect(sys.argv[1])
            if slack_client.rtm_connect():
                print("Bot connected and running.")
                count = 0
                while True:
                    if count % 10 == 0:
                        check_active()

                    count += 1

                    command, channel = parse_slack_output(slack_client.rtm_read())
                    if command and channel:
                        print 'Received "%s" on channel %s' % (command, channel)
                        handle_command(command, channel)
                    time.sleep(READ_WEBSOCKET_DELAY)
            else:
                print("Connection failed. Invalid Slack token or bot ID?")
        except Exception, e:
            print 'Unexpected error; sleeping one minute', e
            time.sleep(60)
