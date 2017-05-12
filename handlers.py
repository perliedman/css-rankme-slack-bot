import sqlite3
import sys
import random
import re
import json

from collections import defaultdict
from collections import Counter
from pack import bestPack
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
                                  '%2d. %19s%6.01f%8.02f%6d')
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
                        '%2d. %19s%7d%6d%7d%6.02f%5.0f%6d',
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


def skill(_, __, log_db_connection):
    cursor = log_db_connection.cursor()
    rounds = cursor.execute("""
        select win_team, lose_team 
        from rounds 
        where win_team is not null and lose_team is not null 
        order by id""").fetchall()
    rounds = [(json.loads(win_team.decode('utf-8')), json.loads(lose_team.decode('utf-8'))) for (win_team, lose_team) in rounds]

    skills = get_skill_ranking(rounds)
    players = dict(cursor.execute('select steam_id, name from players').fetchall())
    leaderboard = zip(range(1, len(skills) + 1), skills)

    return '```' + \
        '%23s%6s' % ('Nick', 'Skill') + '\n' + \
        '\n'.join(['%2d.%20s%6.0f' % (i, players[steam_id], rating.mu - 3 * rating.sigma) for (i, (steam_id, rating)) in leaderboard]) + \
        '```'

def killers(_, __, log_db_connection):
    cursor = log_db_connection.cursor()
    killers = cursor.execute("""
        select killer.name, (
            select killed.steam_id
            from players as killed
            inner join events on subject_id=killed.steam_id
            where events.type='player_death' and indirect_id=killer.steam_id
            group by killed.name
            order by count(events.id) desc
            limit 1
           ) as killed_id, killed.name, count(events.id) as kills
        from players as killer
        inner join events on type='player_death' and subject_id=killed_id and indirect_id=killer.steam_id
        inner join players as killed on killed.steam_id=killed_id
        group by killer.name, killed.name
        order by kills desc
        """).fetchall()

    return '```' + \
        '%16s%13s%6s' % ('Killer', 'Killed', 'Kills') + '\n' + \
        '\n'.join(['%2d.%13s%13s%6d' % (i, killer, killed, kills) for (i, (killer, ___, killed, kills)) in zip(range(1, len(killers)), killers)]) + \
        '```'

def smokes(command, __, log_db_connection):
    return _events(command, __, log_db_connection, 'smokegrenade_detonate', 'No. Smokes', 'Smokes/round')

def hes(command, __, log_db_connection):
    return _events(command, __, log_db_connection, 'hegrenade_detonate', 'No. HEs', 'HEs/round')

def flashbangs(command, __, log_db_connection):
    return _events(command, __, log_db_connection, 'flashbang_detonate', 'No. Flashes', 'Flashes/round')

def bomb_plants(command, __, log_db_connection):
    return _events(command, __, log_db_connection, 'bomb_planted', 'No. Plants', 'Plants/round')

def bomb_defuses(command, __, log_db_connection):
    return _events(command, __, log_db_connection, 'bomb_defused', 'No. Defuses', 'Defuses/round')

def _events(command, __, log_db_connection, event, event_col_name, events_per_round_col_name):
    args = command.split(' ')

    start = args[1] if len(args) > 1 and args[1] is not '' > 0 else '2017-01-01'
    end = args[2] if len(args) > 2 else '2100-01-01'

    sql = """
        select 
            name,
            count(*),
            cast(count(*) as float) / (select count(*) from (select 1 from events where subject_id=players.steam_id group by subject_id, round_id))
        from events as e
        inner join players on steam_id = subject_id
        where
        type = ?
        and date(time) between ? and ?
        group by name
        order by count(*) desc
        """

    table = format_list(log_db_connection, sql,
            '%20s%12s%14s' % ('Nick', event_col_name, events_per_round_col_name),
            '%2d. %16s%12d%14.2f', (event, start, end))

    return '```\n' + table + '\n```'

def weapons(command, _, log_db_connection):
    cursor = log_db_connection.cursor()

    kills = cursor.execute("""
        select
            data
        from events
        inner join players on steam_id = indirect_id
        where
            type = 'player_death'
            and name = '""" + command + """';
    """).fetchall()

    weapons =  [json.loads(data[0].decode('utf-8'))['weapon'] for data in kills]

    print dict(Counter(weapons))

def make_teams(command, connection, **kwargs):
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
        params = [s.lower() for s in re.split(',\\s*', excludes.group(2))]
        sql = 'select name, score from rankme where lower(name) not in (' + \
             ','.join('?'*len(params)) + ')'
    elif includes:
        params = [s.lower() for s in re.split(',\\s*', includes.group(2))]
        sql = 'select name, score from rankme where lower(name) in (' + \
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

if __name__ == "__main__":
    db_connection = sqlite3.connect('sample_db.sq3')
    log_db_connection = sqlite3.connect('sample-log.db.sq3')
    command, arguments = sys.argv[1], ' '.join(sys.argv[1:])

    print locals()[command](arguments, db_connection, log_db_connection=log_db_connection)