from collections import defaultdict
import trueskill

def get_skill_ranking(rounds):
    """
    Returns an array of player rankings from calculated skill.

    rounds is an iterable of pairs, where first element is a list of winning team members,
    and seconds is a list of losing team members
    """
    skiller = trueskill.TrueSkill(draw_probability=0)

    players = defaultdict(skiller.create_rating)

    for (winners, losers) in rounds:
        if len(winners.intersection(losers)) > 0:
            raise Exception('Teams have overlapping members:\n%s\n%s' % (winners, losers))
        win_team = [players[p] for p in winners]
        lose_team = [players[p] for p in losers]

        if len(win_team) and len(lose_team):
            (win_team_rated, lose_team_rated) = skiller.rate([win_team, lose_team], [0, 1])

            for (player_id, rating) in zip(winners, win_team_rated):
                players[player_id] = rating

            for (player_id, rating) in zip(losers, lose_team_rated):
                players[player_id] = rating

    leaderboard = [p for p in players.items()]
    leaderboard.sort(key=lambda x: skiller.expose(x[1]), reverse=True)

    return leaderboard
