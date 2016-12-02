create table game (
    id integer primary key, 
    start_time integer, 
    end_time integer null);

CREATE TABLE `game_stats` (
    game_id INTEGER, 
    steam TEXT, 
    name TEXT, 
    lastip TEXT, 
    score NUMERIC, 
    kills NUMERIC, 
    deaths NUMERIC, 
    suicides NUMERIC, 
    tk NUMERIC, 
    shots NUMERIC, 
    hits NUMERIC, 
    headshots NUMERIC, 
    connected NUMERIC, rounds_tr NUMERIC, rounds_ct NUMERIC, lastconnect NUMERIC,
    knife NUMERIC,glock NUMERIC,usp NUMERIC,p228 NUMERIC,deagle NUMERIC,
    elite NUMERIC,fiveseven NUMERIC,m3 NUMERIC,xm1014 NUMERIC,mac10 NUMERIC,
    tmp NUMERIC,mp5navy NUMERIC,ump45 NUMERIC,p90 NUMERIC,galil NUMERIC,
    ak47 NUMERIC,sg550 NUMERIC,famas NUMERIC,m4a1 NUMERIC,aug NUMERIC,
    scout NUMERIC,sg552 NUMERIC,awp NUMERIC,g3sg1 NUMERIC,m249 NUMERIC,
    hegrenade NUMERIC,flashbang NUMERIC,smokegrenade NUMERIC, head NUMERIC, 
    chest NUMERIC, stomach NUMERIC, left_arm NUMERIC, right_arm NUMERIC, 
    left_leg NUMERIC, right_leg NUMERIC,c4_planted NUMERIC,c4_exploded NUMERIC,
    c4_defused NUMERIC,ct_win NUMERIC, tr_win NUMERIC, hostages_rescued NUMERIC, 
    vip_killed NUMERIC, vip_escaped NUMERIC, vip_played NUMERIC, 
    FOREIGN KEY(game_id) REFERENCES game(id)
);
