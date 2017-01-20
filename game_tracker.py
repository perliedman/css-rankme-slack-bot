import time

class GameTracker(object):
    def __init__(self, connection):
        self._connection = connection
        self._last_score = None
        self._last_active = None
        self._is_active = False

    def check_active(self):
        cursor = self._connection.cursor()
        score = cursor.execute('select sum(score) from rankme').fetchone()[0]
        now = time.time()

        if not self._last_score is None and score != self._last_score:
            if not self._is_active:
                self._is_active = True
                self._create_game(now)
                self.on_game_started()

            self._last_active = now
        elif not self._last_active is None and now - self._last_active > 120:
            if self._is_active:
                self._is_active = False
                self._complete_game(now)
                self.on_game_ended()

        self._last_score = score

    def on_game_started(self):
        pass

    def on_game_ended(self):
        pass

    def _create_game(self, start_time):
        cursor = self._connection.cursor()

        cursor.execute('insert into game (start_time) values (?)', (start_time,))
        game_id = cursor.lastrowid

        cursor.execute("""insert into game_stats (game_id, steam,
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
        self._connection.commit()

    def _complete_game(self, end_time):
        cursor = self._connection.cursor()
        last_game_id = cursor.execute('select max(id) from game').fetchone()[0]
        cursor.execute('update game set end_time=? where id=?', (end_time, last_game_id))
        self._connection.commit()
