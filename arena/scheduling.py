"""Balanced single round robin with fixed immutable submissions and round barriers."""
from fractions import Fraction
import secrets
import time


def round_robin(teams):
    teams = list(teams)
    n = len(teams)
    if n < 2:
        return []
    position = {team: i for i, team in enumerate(teams)}
    ring = teams + ([None] if n % 2 else [])
    rounds = []
    for _ in range(len(ring)-1):
        matches = []
        for a, b in zip(ring[:len(ring)//2], reversed(ring[len(ring)//2:])):
            if a is None or b is None:
                continue
            # Cyclic orientation: equal first-seat counts for odd n, at most one
            # difference for even n. Independent of the circle's pair order.
            i, j = position[a], position[b]
            if i > j:
                a, b, i, j = b, a, j, i
            if j-i > n//2:
                a, b = b, a
            matches.append((a, b))
        rounds.append(matches)
        ring = [ring[0], ring[-1], *ring[1:-1]]
    return rounds


def start_due(db):
    now = time.time()
    with db.transaction() as con:
        due = con.execute("SELECT * FROM tournaments WHERE status='scheduled' AND starts_at<=?", (now,)).fetchall()
        for tournament in due:
            tid = tournament["id"]
            entries = con.execute("SELECT e.user_id,u.active FROM entries e JOIN users u ON u.id=e.user_id WHERE e.tournament_id=? ORDER BY e.user_id", (tid,)).fetchall()
            teams = [r[0] for r in entries]
            frozen = {uid: db.active_submission(uid, con) for uid in teams}
            if len(teams) < 2 or any(not r['active'] for r in entries) or any(not s for s in frozen.values()):
                con.execute("UPDATE tournaments SET status='failed',error=? WHERE id=?", ("حداقل دو تیم فعال با کد معتبر لازم است؛ کدها را بررسی و تورنمنت تازه ایجاد کنید.", tid))
                continue
            for uid, submission in frozen.items():
                con.execute("UPDATE entries SET submission_id=? WHERE tournament_id=? AND user_id=?", (submission["id"], tid, uid))
            games_per_pair = tournament['games_per_pair']
            for r, pairs in enumerate(round_robin(teams)):
                for leg in range(games_per_pair):
                    if leg % 2 == 0:
                        seeds = [secrets.randbits(63) for _ in pairs]
                    for (a, b), seed in zip(pairs, seeds):
                        if leg % 2:
                            a, b = b, a
                        round_number = r * games_per_pair + leg
                        con.execute("INSERT INTO jobs(kind,p0,p1,s0,s1,seed,tournament_id,round,created) VALUES('tournament',?,?,?,?,?,?,?,?)",
                                    (a, b, frozen[a]["id"], frozen[b]["id"], seed, tid, round_number, now))
            con.execute("UPDATE tournaments SET status='running' WHERE id=?", (tid,))


def claim(db, worker):
    with db.transaction() as con:
        count = int(con.execute("SELECT value FROM meta WHERE key='claim_count'").fetchone()[0])
        # Reserve every third dispatch for waiting friendly games. A tournament
        # round is a matching: no team can run two tournament games concurrently.
        job = con.execute("""SELECT j.* FROM jobs j WHERE j.status='queued' AND
            (j.tournament_id IS NULL OR
             (EXISTS(SELECT 1 FROM tournaments t WHERE t.id=j.tournament_id AND t.status='running')
              AND NOT EXISTS(SELECT 1 FROM jobs k WHERE k.tournament_id=j.tournament_id
              AND k.round<j.round AND k.status IN ('queued','running'))))
            ORDER BY CASE WHEN ? % 3=0 THEN j.kind='tournament' ELSE j.kind!='tournament' END,
            j.created,j.id LIMIT 1""", (count,)).fetchone()
        if not job:
            return None
        con.execute("UPDATE meta SET value=? WHERE key='claim_count'", (str(count+1),))
        con.execute("UPDATE jobs SET status='running',worker=?,started=?,attempt=attempt+1 WHERE id=?", (worker, time.time(), job["id"]))
        return dict(job)


def finish_tournaments(db):
    with db.transaction() as con:
        con.execute("""UPDATE tournaments SET status=CASE WHEN EXISTS(
            SELECT 1 FROM jobs WHERE tournament_id=tournaments.id AND status='failed')
            THEN 'failed' ELSE 'completed' END WHERE status='running' AND NOT EXISTS(
            SELECT 1 FROM jobs WHERE tournament_id=tournaments.id AND status IN ('queued','running'))""")


def team_label(team):
    students = [team.get(key, '') for key in ('student1', 'student2') if team.get(key)]
    return team['name'] + (' (' + '، '.join(students) + ')' if students else '')


def friendly_stats_cutoff(db):
    row = db.one("SELECT value FROM meta WHERE key='friendly_stats_after_id'")
    return int(row['value']) if row else 0


def standings(db, tournament_id):
    if tournament_id is None:
        teams = db.rows("SELECT id,name,student1,student2 FROM users WHERE role='team'")
        jobs = db.rows("SELECT p0,p1,winner,score0,score1 FROM jobs WHERE kind='friendly' AND tournament_id IS NULL AND status='completed' AND id>?", (friendly_stats_cutoff(db),))
    else:
        teams = db.rows("SELECT u.id,u.name,u.student1,u.student2 FROM entries e JOIN users u ON u.id=e.user_id WHERE e.tournament_id=?", (tournament_id,))
        jobs = db.rows("SELECT p0,p1,winner,score0,score1 FROM jobs WHERE tournament_id=? AND status='completed'", (tournament_id,))
    for team in teams:
        team['display_name'] = team_label(team)
    table = {t["id"]: dict(t, played=0, wins=0, draws=0, losses=0, points=0, difference=0) for t in teams}
    for job in jobs:
        for seat in (0, 1):
            row = table[job[f"p{seat}"]]
            row["played"] += 1
            row["difference"] += (job[f"score{seat}"] or 0) - (job[f"score{1-seat}"] or 0)
            if job["winner"] is None:
                row["draws"] += 1
                row["points"] += .5
            elif job["winner"] == seat:
                row["wins"] += 1
                row["points"] += 1
            else:
                row["losses"] += 1
    # Compare fractions exactly; displayed percentages may be rounded.
    for row in table.values():
        row['win_ratio'] = row['wins'] / row['played'] if row['played'] else None
        row['eligible'] = row['played'] >= 3
    rows = sorted(table.values(), key=lambda r: (not r['eligible'],
        -Fraction(r['wins'], r['played'] or 1), -r['wins'], -r['draws'], -r['difference'], r['id']))
    rank = 0
    for row in rows:
        if row['eligible']:
            rank += 1
        row['rank'] = rank if row['eligible'] else None
    if tournament_id is not None:
        top_ten = {row['id'] for row in rows if row['rank'] is not None and row['rank'] <= 10}
        against_top = {uid: [0, 0] for uid in table}
        for job in jobs:
            for seat in (0, 1):
                if job[f'p{1-seat}'] in top_ten:
                    counts = against_top[job[f'p{seat}']]
                    counts[0] += 1
                    counts[1] += job['winner'] == seat
        for row in rows:
            played, wins = against_top[row['id']]
            row['top10_played'] = played
            row['top10_win_ratio'] = wins / played if played else None
    return rows
