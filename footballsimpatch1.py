
import random
import unicodedata
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List

# =========================== Team & Player Structures ===========================

@dataclass
class Team:
    name: str
    roster: Dict[str, str]  # positions: QB, RB, WR1, WR2, TE

@dataclass
class PlayerStats:
    # IMPORTANT: These are PLAY yards only (no penalty yards).
    rush_yards: int = 0
    rec_yards: int = 0
    pass_yards: int = 0
    touchdowns: int = 0
    interceptions_thrown: int = 0

StatsType = Dict[str, Dict[str, PlayerStats]]

# =========================== Canonicalization Helpers ===========================

def canonical_name(name: str) -> str:
    s = unicodedata.normalize("NFKC", name or "")
    s = " ".join(s.strip().split())
    return s

def ensure_player(stats: StatsType, team: str, player: str) -> None:
    team_key = team
    player_key = canonical_name(player)
    stats.setdefault(team_key, {})
    stats[team_key].setdefault(player_key, PlayerStats())

# =========================== Config & Effects ===========================

# Formation effects (unchanged)
BASE_SACK_CHANCE = 0.06
BASE_RUN_FUMBLE = 0.02
BASE_REC_FUMBLE = 0.015
BASE_SACK_FUMBLE = 0.03

DEF_EFFECTS = {
    "4-3 Base": {
        "pass_completion_adj": -0.03, "pass_int_adj": 0.00, "sack_adj": 0.00,
        "pass_mean": 8, "pass_std": 6, "pass_big_play_chance": 0.05, "pass_big_play_bonus": (20, 40),
        "run_mean": 3.5, "run_std": 2.5, "tfl_chance": 0.10,
        "run_big_play_chance": 0.04, "run_big_play_bonus": (15, 35)
    },
    "Nickel": {
        "pass_completion_adj": -0.08, "pass_int_adj": 0.01, "sack_adj": 0.02,
        "pass_mean": 8, "pass_std": 5, "pass_big_play_chance": 0.04, "pass_big_play_bonus": (18, 35),
        "run_mean": 5.0, "run_std": 3.5, "tfl_chance": 0.07,
        "run_big_play_chance": 0.05, "run_big_play_bonus": (15, 35)
    },
    "Dime": {
        "pass_completion_adj": -0.12, "pass_int_adj": 0.02, "sack_adj": 0.03,
        "pass_mean": 7, "pass_std": 5, "pass_big_play_chance": 0.03, "pass_big_play_bonus": (15, 30),
        "run_mean": 5.5, "run_std": 4.0, "tfl_chance": 0.06,
        "run_big_play_chance": 0.05, "run_big_play_bonus": (15, 35)
    },
    "Blitz": {
        "pass_completion_adj": -0.15, "pass_int_adj": 0.05, "sack_adj": 0.08,
        "pass_mean": 9, "pass_std": 8, "pass_big_play_chance": 0.10, "pass_big_play_bonus": (25, 45),
        "run_mean": 2.5, "run_std": 4.0, "tfl_chance": 0.15,
        "run_big_play_chance": 0.08, "run_big_play_bonus": (20, 40)
    },
    "Goal Line": {
        "pass_completion_adj": 0.02, "pass_int_adj": 0.00, "sack_adj": -0.02,
        "pass_mean": 12, "pass_std": 8, "pass_big_play_chance": 0.08, "pass_big_play_bonus": (20, 40),
        "run_mean": 2.0, "run_std": 2.0, "tfl_chance": 0.12,
        "run_big_play_chance": 0.02, "run_big_play_bonus": (10, 25)
    },
    "Prevent": {
        "pass_completion_adj": 0.10, "pass_int_adj": -0.01, "sack_adj": -0.03,
        "pass_mean": 6, "pass_std": 4, "pass_big_play_chance": 0.01, "pass_big_play_bonus": (10, 20),
        "run_mean": 6.0, "run_std": 4.0, "tfl_chance": 0.05,
        "run_big_play_chance": 0.06, "run_big_play_bonus": (15, 35)
    },
}
DEF_CHOICES = list(DEF_EFFECTS.keys())

# =========================== Your Teams ===========================

TEAMS = [
    Team("Packers", {"QB": "J. Love", "RB": "J. Jacobs", "WR1": "C. Watson", "WR2": "J. Reed", "TE": "T. Kraft"}),
    Team("Bears", {"QB": "C. Williams", "RB": "D. Swift", "WR1": "D. Moore", "WR2": "R. Odunze","TE": "C. Loveland"}),
    Team("Lions", {"QB": "J. Goff", "RB": "J. Gibbs", "WR1": "A. St. Brown", "WR2": "J. Williams", "TE": "S. Laporta"}),
    Team("Vikings", {"QB": "J. McCarthy", "RB": "A. Jones", "WR1": "J. Jefferson", "WR2": "J. Addison", "TE": "T. Hockenson"}),

    Team("Saints", {"QB": "T. Shough", "RB": "A. Kamara", "WR1": "C. Olave", "WR2": "M. Thomas", "TE": "J. Johnson"}),
    Team("Falcons", {"QB": "M. Penix", "RB": "B. Robinson", "WR1": "D. London", "WR2": "D. Mooney", "TE": "K. Pitts"}),
    Team("Bucaneers", {"QB": "B. Mayfield", "RB": "B. Irving", "WR1": "M. Evans", "WR2": "C. Godwin", "TE": "C. Otton"}),
    Team("Panthers", {"QB": "B. Young", "RB": "C. Hubbard", "WR1": "T. McMillian", "WR2": "X. Leggette", "TE": "J. Sanders"}),

    Team("Eagles", {"QB": "J. Hurts", "RB": "S. Barkley", "WR1": "A. Brown", "WR2": "D. Smith", "TE": "D. Goedert"}),
    Team("Cowboys", {"QB": "D. Prescott", "RB": "J. Williams", "WR1": "C. Lamb", "WR2": "G. Pickens", "TE": "J. Fergeson"}),
    Team("Giants", {"QB": "N. Price", "RB": "E. Cole", "WR1": "B. James", "WR2": "C. Allen", "TE": "T. Grant"}),
    Team("Commanders", {"QB": "J. Daniels", "RB": "J. Croskey-Merrit", "WR1": "T. Mclauren", "WR2": "D. Samuel", "TE": "Z. Ertz"}),

    Team("Seahawks", {"QB": "S. Darnold", "RB": "K. Walker", "WR1": "J. Smith-Njigba", "WR2": "C. Kupp", "TE": "A. Barner"}),
    Team("Rams", {"QB": "M. Stafford", "RB": "K. Williams", "WR1": "P. Nacua", "WR2": "D. Adams", "TE": "T. Fergeson"}),
    Team("49ers", {"QB": "B. Purdy", "RB": "C. McCaffery", "WR1": "R. Pearsall", "WR2": "J. Jennings", "TE": "G. Kittle"}),
    Team("Cardinals", {"QB": "K. Murray", "RB": "J. Conner", "WR1": "M. Harrison", "WR2": "M. Wilson", "TE": "T. McBride"}),

    Team("Steelers", {"QB": "A. Rodgers", "RB": "J. Warren", "WR1": "D. Metcalf", "WR2": "C. Austin", "TE": "P. Freiermuth"}),
    Team("Ravens", {"QB": "L. Jackson", "RB": "D. Henry", "WR1": "Z. Flowers", "WR2": "R. Bateman", "TE": "M. Andrews"}),
    Team("Browns", {"QB": "S. Sanders", "RB": "Q. Judkins", "WR1": "J. Jeudy", "WR2": "C. Tillman", "TE": "H. Fannin"}),
    Team("Bengals", {"QB": "J. Burrow", "RB": "C. Brown", "WR1": "J. Chase", "WR2": "T. Higgins", "TE": "M. Giseki"}),

    Team("Patriots", {"QB": "D. Maye", "RB": "T. Henderson", "WR1": "S. Diggs", "WR2": "D. Douglas", "TE": "H. Henry"}),
    Team("Bills", {"QB": "J. Allen", "RB": "J. Cook", "WR1": "K. Coleman", "WR2": "G. Davis", "TE": "D. Kincaid"}),
    Team("Dolphins", {"QB": "T. Tagovailoa", "RB": "D. Achane", "WR1": "T. Hill", "WR2": "J. Waddle", "TE": "D. Waller"}),
    Team("Jets", {"QB": "J. Fields", "RB": "B. Hall", "WR1": "G. Wilson", "WR2": "A. Mitchell", "TE": "M. Taylor"}),

    Team("Texans", {"QB": "C. Stroud", "RB": "W. Marks", "WR1": "N. Collins", "WR2": "T. Dell", "TE": "D. Shultz"}),
    Team("Colts", {"QB": "D. Jones", "RB": "J. Taylor", "WR1": "M. Pittman", "WR2": "J. Downs", "TE": "T. Warren"}),
    Team("Titans", {"QB": "C. Ward", "RB": "T. Pollard", "WR1": "C. Ridley", "WR2": "E. Ayonmanor", "TE": "C. Okonkwo"}),
    Team("Jaguars", {"QB": "T. Lawrence", "RB": "T. Etienne", "WR1": "B. Thomas", "WR2": "T. Hunter", "TE": "B. Strange"}),

    Team("Broncos", {"QB": "B. Nix", "RB": "R. Harvery", "WR1": "C. Sutton", "WR2": "T. Franklin", "TE": "E. Engram"}),
    Team("Chargers", {"QB": "J. Herbert", "RB": "O. Hampton", "WR1": "K. Allen", "WR2": "L. McKonkey", "TE": "O. Gadsden"}),
    Team("Chiefs", {"QB": "P. Mahomes", "RB": "I. Pacheco", "WR1": "R. Rice", "WR2": "X. Worthy", "TE": "T. Kelce"}),
    Team("Raiders", {"QB": "G. Smith", "RB": "A. Jeanty", "WR1": "T. Lockett", "WR2": "J. Bech", "TE": "B. Bowers"}),
]

# =========================== QB baselines (comp %, INT %) ===========================

QB_INPUT_RATES: Dict[str, Dict[str, float]] = {
    # NFC North
    "Packers": {"comp_pct": 64.3, "int_pct": 2.6},
    "Bears":   {"comp_pct": 60.5, "int_pct": 1.1},
    "Lions":   {"comp_pct": 68.3, "int_pct": 1.3},
    "Vikings": {"comp_pct": 59.6, "int_pct": 3.9},
    # NFC South
    "Saints":    {"comp_pct": 63.7, "int_pct": 1.8},
    "Falcons":   {"comp_pct": 65.4, "int_pct": 2.0},
    "Bucaneers": {"comp_pct": 62.8, "int_pct": 1.9},
    "Panthers":  {"comp_pct": 63.2, "int_pct": 2.3},
    # NFC East
    "Eagles":     {"comp_pct": 64.8, "int_pct": 2.6},
    "Cowboys":    {"comp_pct": 67.4, "int_pct": 1.7},
    "Giants":     {"comp_pct": 62.0, "int_pct": 2.5},
    "Commanders": {"comp_pct": 69.0, "int_pct": 1.9},
    # NFC West
    "Seahawks": {"comp_pct": 67.2, "int_pct": 3.1},
    "Rams":     {"comp_pct": 65.2, "int_pct": 1.4},
    "49ers":    {"comp_pct": 69.3, "int_pct": 3.5},
    "Cardinals": {"comp_pct": 62.8, "int_pct": 2.5},
    # AFC North
    "Steelers": {"comp_pct": 65.6, "int_pct": 1.6},
    "Ravens":   {"comp_pct": 66.7, "int_pct": 0.8},
    "Browns":   {"comp_pct": 57.9, "int_pct": 5.3},
    "Bengals":  {"comp_pct": 70.6, "int_pct": 1.4},
    # AFC East
    "Patriots": {"comp_pct": 71.7, "int_pct": 1.7},
    "Bills":    {"comp_pct": 69.4, "int_pct": 2.2},
    "Dolphins": {"comp_pct": 58.9, "int_pct": 3.8},
    "Jets":     {"comp_pct": 60.8, "int_pct": 1.0},
    # AFC South
    "Texans":  {"comp_pct": 64.8, "int_pct": 2.0},
    "Colts":   {"comp_pct": 68.0, "int_pct": 2.1},
    "Titans":  {"comp_pct": 59.6, "int_pct": 1.3},
    "Jaguars": {"comp_pct": 60.2, "int_pct": 2.3},
    # AFC West
    "Broncos":  {"comp_pct": 63.5, "int_pct": 1.9},
    "Chargers": {"comp_pct": 66.4, "int_pct": 2.5},
    "Chiefs":   {"comp_pct": 67.5, "int_pct": 1.9},
    "Raiders":  {"comp_pct": 67.4, "int_pct": 4.8},
}

# =========================== Utilities ===========================

def clamp(val: float, low: float, high: float) -> float:
    return max(low, min(high, val))

def clamp_int(val: int, low: int, high: int) -> int:
    return max(low, min(high, val))

def clamp_play_spot(x: int) -> int:
    return clamp_int(x, 1, 100)

def clamp_start_spot(x: int) -> int:
    return clamp_int(x, 1, 99)

def to_receiving_spot(offense_spot: int) -> int:
    return clamp_start_spot(100 - offense_spot)

def cap_gain_to_td(ball_on: int, gain: int) -> int:
    if gain <= 0:
        return gain
    remaining = 100 - ball_on
    return min(gain, remaining)

def mmss(seconds: int) -> str:
    m = seconds // 60
    s = seconds % 60
    return f"{m:02d}:{s:02d}"

def sample_yards(mean: float, std: float, allow_negative: bool = True, max_gain: int = 60) -> int:
    y = int(round(random.gauss(mean, std)))
    if not allow_negative:
        return max(0, min(y, max_gain))
    return clamp_int(y, -12, max_gain)

def sample_big_play(bonus_range: Tuple[int, int]) -> int:
    low, high = bonus_range
    return random.randint(low, high)

# =========================== Target Selection ===========================

def choose_run_ballcarrier(roster: Dict[str, str]) -> str:
    choices = [
        (roster["RB"], 0.83),
        (roster["WR1"], 0.06),
        (roster["WR2"], 0.08),
        (roster["QB"], 0.03),
    ]
    r = random.random()
    cum = 0.0
    for name, w in choices:
        cum += w
        if r <= cum:
            return canonical_name(name)
    return canonical_name(roster["RB"])

def choose_receiver(roster: Dict[str, str]) -> str:
    choices = [
        (roster["WR1"], 0.40),
        (roster["WR2"], 0.30),
        (roster["TE"], 0.20),
        (roster["RB"], 0.10),
    ]
    r = random.random()
    cum = 0.0
    for name, w in choices:
        cum += w
        if r <= cum:
            return canonical_name(name)
    return canonical_name(roster["WR1"])

def ai_choose_deep_target(offense: Team, defense_formation: str) -> str:
    wr1 = canonical_name(offense.roster["WR1"])
    wr2 = canonical_name(offense.roster["WR2"])
    te  = canonical_name(offense.roster["TE"])
    rb  = canonical_name(offense.roster["RB"])
    if defense_formation in ("Dime", "Prevent"):
        weights = [(wr1, 0.50), (wr2, 0.25), (te, 0.15), (rb, 0.10)]
    elif defense_formation in ("Blitz",):
        weights = [(wr1, 0.60), (wr2, 0.25), (te, 0.10), (rb, 0.05)]
    else:
        weights = [(wr1, 0.55), (wr2, 0.25), (te, 0.12), (rb, 0.08)]
    r = random.random()
    cum = 0.0
    for name, w in weights:
        cum += w
        if r <= cum:
            return name
    return wr1

# =========================== Penalties ===========================

@dataclass
class PenaltyResult:
    pre_snap: bool
    description: str
    yardage: int
    against_defense: bool
    automatic_first: bool = False

def maybe_penalty(offense: Team, defense: Team, is_pass: bool) -> Optional[PenaltyResult]:
    if random.random() > 0.08:
        return None
    pre = (random.random() < 0.40)
    if pre:
        if random.random() < 0.55:
            return PenaltyResult(True, "False start on offense (-5)", -5, against_defense=False)
        else:
            return PenaltyResult(True, "Offside on defense (+5)", +5, against_defense=True)
    else:
        if is_pass and random.random() < 0.50:
            return PenaltyResult(False, "Defensive pass interference (+15, automatic first down)", +15, True, True)
        else:
            return PenaltyResult(False, "Offensive holding (-10)", -10, False)

# =========================== Team Penalty Totals ===========================

PenaltyTotalsType = Dict[str, Dict[str, int]]

def make_penalty_totals(user_team: Team, cpu_team: Team) -> PenaltyTotalsType:
    return {user_team.name: {"count": 0, "yards": 0}, cpu_team.name: {"count": 0, "yards": 0}}

def accrue_penalty(penalty_totals: PenaltyTotalsType, offense: Team, defense: Team, p: PenaltyResult) -> None:
    penalized = defense.name if p.against_defense else offense.name
    penalty_totals[penalized]["count"] += 1
    penalty_totals[penalized]["yards"] += abs(p.yardage)

def apply_post_play_penalty_for_spot_and_note(play_yards: int, p: PenaltyResult,
                                              offense: Team, defense: Team, penalty_totals: PenaltyTotalsType
                                              ) -> Tuple[int, str]:
    accrue_penalty(penalty_totals, offense, defense, p)
    if p.description.startswith("Offensive holding"):
        return -10, " (holding: -10)"
    sign = "+" if p.yardage >= 0 else ""
    return play_yards + p.yardage, f" (penalty: {sign}{p.yardage})"

# =========================== Stats & Print ===========================

def update_run_stats(stats: StatsType, team: str, runner: str, play_yards: int, td: bool) -> None:
    runner = canonical_name(runner)
    ensure_player(stats, team, runner)
    stats[team][runner].rush_yards += play_yards
    if td:
        stats[team][runner].touchdowns += 1

def update_pass_stats(stats: StatsType, team: str, qb: str, receiver: Optional[str],
                      play_yards: int, completed: bool, intercepted: bool, td: bool) -> None:
    qb = canonical_name(qb)
    ensure_player(stats, team, qb)
    if intercepted:
        stats[team][qb].interceptions_thrown += 1
    if completed:
        stats[team][qb].pass_yards += play_yards
        if receiver:
            receiver = canonical_name(receiver)
            ensure_player(stats, team, receiver)
            stats[team][receiver].rec_yards += play_yards
            if td:
                stats[team][receiver].touchdowns += 1

def coalesce(players: Dict[str, PlayerStats]) -> Dict[str, PlayerStats]:
    merged: Dict[str, PlayerStats] = {}
    for name, ps in players.items():
        key = canonical_name(name)
        if key not in merged:
            merged[key] = PlayerStats()
        m = merged[key]
        m.rush_yards += ps.rush_yards
        m.rec_yards += ps.rec_yards
        m.pass_yards += ps.pass_yards
        m.touchdowns += ps.touchdowns
        m.interceptions_thrown += ps.interceptions_thrown
    return merged

def print_stats(stats: StatsType, penalty_totals: PenaltyTotalsType) -> None:
    print("\n=== Player Stats ===")
    for team, players in stats.items():
        print(f"\nTeam: {team}")
        print("-" * (6 + len(team)))
        merged = coalesce(players)
        for name in sorted(merged.keys()):
            ps = merged[name]
            print(f"{name:20s} | Rush: {ps.rush_yards:3d} | Rec: {ps.rec_yards:3d} | Pass: {ps.pass_yards:3d} | TD: {ps.touchdowns:2d} | INT Thrown: {ps.interceptions_thrown:2d}")
        pt = penalty_totals.get(team, {"count": 0, "yards": 0})
        print(f"Penalties: {pt['count']} for {pt['yards']} yards")
    print("=" * 22 + "\n")

def print_score(scoreboard: Dict[str, int]) -> None:
    print("\n=== Scoreboard ===")
    for team, pts in scoreboard.items():
        print(f"{team}: {pts}")
    print("=" * 22 + "\n")

# =========================== Special Teams ===========================

def punt_result(ball_on: int) -> Tuple[int, str]:
    base = int(round(random.gauss(44, 6)))
    base = clamp_int(base, 28, 65)
    kick_to = ball_on + base
    desc = f"Punt travels {base} yards"
    if kick_to >= 100:
        return 25, desc + " and is a touchback."
    else:
        if random.random() < 0.40:
            ret = 0
            desc += "; fair catch."
        else:
            ret = clamp_int(int(round(random.gauss(8, 5))), 0, 40)
            desc += f"; return of {ret} yards."
        recv_ball_on = clamp_start_spot(100 - kick_to + ret)
        return recv_ball_on, desc + f" Receiving team starts at O-{recv_ball_on}."

def safety_free_kick_result() -> Tuple[int, str]:
    """
    Models the post-safety free kick from the 20 with return yards.
    - Kick distance: ~62 yards (clamped 40..80)
    - 30% fair catch; else return ~18 yards (clamped 0..60)
    - Touchback to O-25
    """
    base_kick = int(round(random.gauss(62, 7)))
    base_kick = clamp_int(base_kick, 40, 80)
    kick_to = 20 + base_kick
    desc = f"Free kick from the 20 travels {base_kick} yards"
    if kick_to >= 100:
        recv_ball_on = 25
        return recv_ball_on, desc + " into the end zone for a touchback."
    else:
        if random.random() < 0.30:
            ret = 0
            desc += "; fair catch."
        else:
            ret = clamp_int(int(round(random.gauss(18, 10))), 0, 60)
            desc += f"; return of {ret} yards."
        recv_ball_on = clamp_start_spot(100 - kick_to + ret)
        return recv_ball_on, desc + f" Receiving team starts at O-{recv_ball_on}."

def field_goal_success_prob(ball_on: int) -> float:
    dist = 100 - ball_on + 17
    if dist <= 35: return 0.95
    if dist <= 40: return 0.90
    if dist <= 45: return 0.80
    if dist <= 50: return 0.70
    if dist <= 55: return 0.55
    if dist <= 60: return 0.40
    if dist <= 66: return 0.30
    if dist <= 70: return 0.05
    return 0.00

# =========================== Team-adjusted Passing ===========================

def get_team_pass_baselines(team_name: str) -> Tuple[float, float]:
    """
    Returns normalized (completion, interception) baselines for a team.
    We clamp to reasonable ranges to keep gameplay stable.
    """
    rates = QB_INPUT_RATES.get(team_name)
    if not rates:
        # Conservative league-average fallback
        return 0.62, 0.023
    comp = clamp(rates["comp_pct"] / 100.0, 0.55, 0.75)
    intr = clamp(rates["int_pct"] / 100.0, 0.008, 0.035)
    return comp, intr

def compute_pass_probs(team_name: str, defense_formation: str) -> Tuple[float, float, float]:
    eff = DEF_EFFECTS[defense_formation]
    base_comp, base_int = get_team_pass_baselines(team_name)
    comp = clamp(base_comp + eff["pass_completion_adj"], 0.30, 0.90)
    inter = clamp(base_int + eff["pass_int_adj"], 0.005, 0.08)
    sack = clamp(BASE_SACK_CHANCE + eff.get("sack_adj", 0.0), 0.01, 0.20)
    return comp, inter, sack

def compute_deep_pass_probs(team_name: str, defense_formation: str) -> Tuple[float, float, float]:
    eff = DEF_EFFECTS[defense_formation]
    base_comp, base_int = get_team_pass_baselines(team_name)
    # Deep baseline tweaks
    comp = clamp(base_comp - 0.12 + eff["pass_completion_adj"], 0.20, 0.85)
    inter = clamp(base_int + 0.01 + eff["pass_int_adj"], 0.006, 0.10)
    sack = clamp(BASE_SACK_CHANCE + 0.03 + eff.get("sack_adj", 0.0), 0.02, 0.25)
    return comp, inter, sack

# =========================== Play Simulation ===========================

def simulate_run(offense: Team, defense_formation: str) -> Tuple[str, int, bool, bool]:
    eff = DEF_EFFECTS[defense_formation]
    runner = choose_run_ballcarrier(offense.roster)
    if random.random() < eff["tfl_chance"]:
        yards = -random.randint(1, 5)
    else:
        yards = sample_yards(eff["run_mean"], eff["run_std"], allow_negative=True)
        if random.random() < eff["run_big_play_chance"]:
            yards += sample_big_play(eff["run_big_play_bonus"])
    fumble_lost = (random.random() < BASE_RUN_FUMBLE) and (random.random() < 0.5)
    return runner, yards, False, fumble_lost

def simulate_pass(offense: Team, defense_formation: str, target: Optional[str] = None
                  ) -> Tuple[str, Optional[str], int, bool, bool, bool, bool]:
    eff = DEF_EFFECTS[defense_formation]
    qb = canonical_name(offense.roster["QB"])
    receiver = canonical_name(target or choose_receiver(offense.roster))

    comp, inter, sack = compute_pass_probs(offense.name, defense_formation)

    if random.random() < sack:
        yards = -clamp_int(int(round(random.gauss(6, 3))), 1, 15)
        fumble_lost = (random.random() < BASE_SACK_FUMBLE) and (random.random() < 0.5)
        return qb, receiver, yards, False, False, True, fumble_lost

    if random.random() < inter:
        return qb, receiver, 0, False, True, False, False

    if random.random() < comp:
        yards = sample_yards(DEF_EFFECTS[defense_formation]["pass_mean"], DEF_EFFECTS[defense_formation]["pass_std"], allow_negative=False)
        if random.random() < DEF_EFFECTS[defense_formation]["pass_big_play_chance"]:
            yards += sample_big_play(DEF_EFFECTS[defense_formation]["pass_big_play_bonus"])
        fumble_lost = (random.random() < BASE_REC_FUMBLE) and (random.random() < 0.5)
        return qb, receiver, yards, True, False, False, fumble_lost

    return qb, receiver, 0, False, False, False, False

def simulate_deep_pass(offense: Team, defense_formation: str, target: Optional[str] = None
                       ) -> Tuple[str, Optional[str], int, bool, bool, bool, bool]:
    qb = canonical_name(offense.roster["QB"])
    receiver = canonical_name(target or ai_choose_deep_target(offense, defense_formation))
    comp, inter, sack = compute_deep_pass_probs(offense.name, defense_formation)

    if random.random() < sack:
        yards = -clamp_int(int(round(random.gauss(7, 3))), 1, 15)
        fumble_lost = (random.random() < BASE_SACK_FUMBLE) and (random.random() < 0.5)
        return qb, receiver, yards, False, False, True, fumble_lost

    if random.random() < inter:
        return qb, receiver, 0, False, True, False, False

    if random.random() < comp:
        yards = max(20, sample_yards(27, 10, allow_negative=False))
        if random.random() < 0.08:
            yards += sample_big_play((18, 35))
        fumble_lost = (random.random() < BASE_REC_FUMBLE) and (random.random() < 0.5)
        return qb, receiver, yards, True, False, False, fumble_lost

    return qb, receiver, 0, False, False, False, False

# =========================== AI Helpers ===========================

@dataclass
class Tendencies:
    recent_offense_calls: List[str]
    def push(self, call: str):
        self.recent_offense_calls.append(call)
        if len(self.recent_offense_calls) > 6:
            self.recent_offense_calls.pop(0)
    def run_ratio(self) -> float:
        if not self.recent_offense_calls:
            return 0.5
        runs = sum(1 for c in self.recent_offense_calls if c == "run")
        return runs / len(self.recent_offense_calls)

def ai_choose_defense(ball_on: int, distance_to_first: int, down: int, seconds_left: int,
                      score_lead: int, offense_run_ratio: float) -> str:
    if seconds_left < 60 and score_lead > 0:
        return random.choices(["Prevent", "Nickel"], weights=[0.7, 0.3])[0]
    yards_to_td = 100 - ball_on
    if yards_to_td <= 5:
        return random.choices(["Goal Line", "Blitz", "4-3 Base"], weights=[0.6, 0.2, 0.2])[0]
    if distance_to_first >= 8:
        return random.choices(["Dime", "Nickel", "Blitz"], weights=[0.5, 0.4, 0.1])[0]
    if offense_run_ratio > 0.65:
        return random.choices(["4-3 Base", "Blitz", "Nickel"], weights=[0.6, 0.3, 0.1])[0]
    return random.choices(["4-3 Base", "Nickel", "Dime", "Blitz"], weights=[0.4, 0.3, 0.2, 0.1])[0]

def ai_choose_offense(distance_to_first: int, down: int, ball_on: int, seconds_left: int,
                      score_trail: int) -> str:
    yards_to_td = 100 - ball_on
    if down == 4:
        fg_prob = field_goal_success_prob(ball_on)
        if yards_to_td <= 35 and fg_prob >= 0.55:
            return "fg"
        if yards_to_td > 20 and distance_to_first > 1:
            return "punt"
        return random.choice(["run", "pass", "deep"])
    if seconds_left < 90 and score_trail > 0:
        return random.choices(["deep", "pass", "run"], weights=[0.4, 0.4, 0.2])[0]
    if distance_to_first >= 8:
        return random.choices(["pass", "deep", "run"], weights=[0.55, 0.25, 0.20])[0]
    if 40 <= ball_on <= 60 and down in (1, 2):
        return random.choices(["run", "pass", "deep"], weights=[0.40, 0.40, 0.20])[0]
    if yards_to_td <= 10:
        return random.choices(["run", "pass", "deep"], weights=[0.55, 0.40, 0.05])[0]
    return random.choices(["run", "pass", "deep"], weights=[0.45, 0.40, 0.15])[0]

def ai_choose_target(offense: Team, defense_formation: str) -> str:
    wr1 = canonical_name(offense.roster["WR1"])
    wr2 = canonical_name(offense.roster["WR2"])
    te  = canonical_name(offense.roster["TE"])
    rb  = canonical_name(offense.roster["RB"])
    if defense_formation in ["Dime"]:
        weights = [(wr1, 0.30), (wr2, 0.25), (te, 0.25), (rb, 0.20)]
    elif defense_formation in ["Blitz"]:
        weights = [(wr1, 0.45), (wr2, 0.35), (te, 0.15), (rb, 0.05)]
    else:
        weights = [(wr1, 0.40), (wr2, 0.30), (te, 0.20), (rb, 0.10)]
    r = random.random()
    cum = 0.0
    for name, w in weights:
        cum += w
        if r <= cum:
            return name
    return wr1

# =========================== UI Helpers ===========================

def select_team(teams: List[Team], prompt: str) -> Team:
    print(prompt)
    for idx, t in enumerate(teams):
        print(f"{idx+1}. {t.name}  (QB: {t.roster['QB']}, RB: {t.roster['RB']}, WR1: {t.roster['WR1']}, WR2: {t.roster['WR2']}, TE: {t.roster['TE']})")
    while True:
        choice = input("Enter team number: ").strip()
        if choice.isdigit():
            i = int(choice) - 1
            if 0 <= i < len(teams):
                return teams[i]
        print("Invalid selection. Try again.")

def user_offense_choice() -> str:
    while True:
        s = input("Your offense: [run/pass/deep/punt/fg] (or 'stats', 'score', 'clock', 'timeout', 'quit'): ").strip().lower()
        if s in ["run", "pass", "deep", "punt", "fg", "stats", "score", "clock", "timeout", "quit"]:
            return s
        print("Invalid choice. Try again.")

def user_defense_choice() -> str:
    print("Your defense: choose formation:")
    for idx, d in enumerate(DEF_CHOICES):
        print(f"{idx+1}. {d}")
    while True:
        choice = input("Enter formation (or 'stats', 'score', 'clock', 'timeout', 'quit'): ").strip().lower()
        if choice in ["stats", "score", "clock", "timeout", "quit"]:
            return choice
        if choice.isdigit():
            i = int(choice) - 1
            if 0 <= i < len(DEF_CHOICES):
                return DEF_CHOICES[i]
        print("Invalid selection. Try again.")

# =========================== Game Loop ===========================

def game():
    random.seed()
    print("Welcome to the Football Simulator. Good Luck!\n")
    user_team = select_team(TEAMS, "Select YOUR TEAM:")
    cpu_team = select_team(TEAMS, "Select the COMPUTER TEAM:")

    print("\nWho receives the opening kickoff?")
    print("1. Your team")
    print("2. Computer team")
    user_receives = (input("Enter 1 or 2: ").strip() == "1")

    initial_receiving_team = user_team if user_receives else cpu_team

    stats: StatsType = {}
    penalty_totals: PenaltyTotalsType = make_penalty_totals(user_team, cpu_team)
    scoreboard = {user_team.name: 0, cpu_team.name: 0}
    tendencies_user = Tendencies(recent_offense_calls=[])
    tendencies_cpu = Tendencies(recent_offense_calls=[])

    QUARTERS = 4
    SECS_PER_Q = 12 * 60
    quarter = 1
    seconds_left = SECS_PER_Q
    timeouts = {user_team.name: 3, cpu_team.name: 3}
    halftime_done = False

    def reset_timeouts():
        timeouts[user_team.name] = 3
        timeouts[cpu_team.name] = 3

    def kickoff_to(team_receives: Team):
        offense = team_receives
        defense = cpu_team if offense is user_team else user_team
        ball_on = 25
        down = 1
        line_to_gain = min(ball_on + 10, 100)
        return offense, defense, ball_on, line_to_gain, down

    offense, defense, ball_on, line_to_gain, down = kickoff_to(initial_receiving_team)

    def distance_to_first():
        return max(1, line_to_gain - ball_on)

    def situation():
        print(f"\nQ{quarter} {mmss(seconds_left)} | {offense.name} ball | {down} & {distance_to_first()} at O-{ball_on}")

    def advance_clock(play_type: str, completed: bool) -> bool:
        nonlocal seconds_left, quarter, halftime_done, offense, defense, ball_on, line_to_gain, down
        halftime_kickoff = False
        if play_type == "run":
            delta = random.randint(28, 42)
        elif play_type == "pass":
            delta = random.randint(30, 40) if completed else random.randint(5, 10)
        else:
            delta = random.randint(8, 15)
        if quarter == QUARTERS:
            delta = min(delta, seconds_left)
        seconds_left -= delta
        while seconds_left <= 0 and quarter < QUARTERS:
            print(f"\n--- End of Q{quarter}. ---")
            quarter += 1
            seconds_left = SECS_PER_Q
            if quarter == 3 and not halftime_done:
                reset_timeouts()
                second_half_receiver = cpu_team if initial_receiving_team is user_team else user_team
                offense, defense, ball_on, line_to_gain, down = kickoff_to(second_half_receiver)
                halftime_done = True
                halftime_kickoff = True
                print("=== Start of Second Half: kickoff (1st & 10 at O-25), 12:00 ===")
            else:
                print(f"Start Q{quarter} — {mmss(seconds_left)}")
        if quarter == QUARTERS and seconds_left < 0:
            seconds_left = 0
        return halftime_kickoff

    def consume_clock(play_type: str, completed: bool) -> bool:
        return advance_clock(play_type, completed)

    def call_timeout(team: Team):
        if timeouts[team.name] > 0:
            timeouts[team.name] -= 1
            print(f"Timeout {team.name}. Timeouts left: {timeouts[team.name]}")
        else:
            print(f"{team.name} has no timeouts remaining.")

    def flip_possession(new_ball_on: int):
        nonlocal offense, defense, ball_on, line_to_gain, down
        offense, defense = defense, offense
        ball_on = clamp_start_spot(new_ball_on)
        down = 1
        line_to_gain = min(ball_on + 10, 100)
        print(f"{offense.name} takes over at O-{ball_on} (1st & {distance_to_first()}).")

    def after_first_down():
        nonlocal down, line_to_gain
        print("First down!")
        down = 1
        line_to_gain = min(ball_on + 10, 100)

    def enforce_penalty_pre(p: PenaltyResult):
        nonlocal ball_on
        print(f"Penalty: {p.description}")
        accrue_penalty(penalty_totals, offense, defense, p)
        ball_on = clamp_play_spot(ball_on + p.yardage)
        if p.automatic_first:
            after_first_down()

    # --- SAFETY helpers --------------------------------------------------------
    def handle_safety(reason: str):
        """Award safety, update score, and restart with a free-kick style possession."""
        nonlocal offense, defense, ball_on, line_to_gain, down
        print(f"SAFETY! {reason} Two points to {defense.name}.")
        scoreboard[defense.name] += 2
        print_score(scoreboard)
        # The team that conceded (current offense) free-kicks; scoring team (current defense) receives
        recv_ball_on, desc = safety_free_kick_result()
        # Switch possession: scoring team on offense
        offense, defense = defense, offense
        ball_on = clamp_start_spot(recv_ball_on)
        down = 1
        line_to_gain = min(ball_on + 10, 100)
        print(desc)

    def check_and_award_safety(net_yards: int, reason: str) -> bool:
        """
        Returns True if a safety occurred.
        We check using raw position change BEFORE clamping, so we catch end-zone outcomes.
        """
        if (ball_on + net_yards) <= 0:
            handle_safety(reason)
            return True
        return False

    def ai_maybe_timeout():
        if seconds_left <= 120 and scoreboard[defense.name] < scoreboard[offense.name] and timeouts[defense.name] > 0:
            if random.random() < 0.5:
                call_timeout(defense)

    print(f"\nKickoff! {offense.name} starts at their 25-yard line.")
    print(f"Quarter {quarter} — {mmss(seconds_left)}")

    # ========== Main Game Loop ==========
    while quarter <= QUARTERS and seconds_left > 0:
        situation()
        user_is_offense = (offense is user_team)

        if user_is_offense:
            selection = user_offense_choice()
            if selection in ["stats", "score", "clock", "timeout", "quit"]:
                if selection == "stats": print_stats(stats, penalty_totals); continue
                if selection == "score": print_score(scoreboard); continue
                if selection == "clock": print(f"Quarter {quarter} — {mmss(seconds_left)}"); continue
                if selection == "timeout": call_timeout(offense); continue
                if selection == "quit": print("\nThanks for playing!"); print_score(scoreboard); print_stats(stats, penalty_totals); return

            pre_pen = maybe_penalty(offense, defense, is_pass=(selection in ("pass","deep")))
            if pre_pen and pre_pen.pre_snap:
                enforce_penalty_pre(pre_pen)
                continue

            defense_formation = ai_choose_defense(
                ball_on, distance_to_first(), down, seconds_left,
                scoreboard[defense.name] - scoreboard[offense.name],
                tendencies_user.run_ratio()
            )
            print(f"Computer defense shows: {defense_formation}")

            clock_play_type = "run"; clock_completed = True

            if selection == "run":
                tendencies_user.push("run")
                runner, play_yards, _, fumble_lost = simulate_run(offense, defense_formation)
                post_pen = maybe_penalty(offense, defense, is_pass=False)
                note = ""
                net_yards = play_yards
                if post_pen and not post_pen.pre_snap:
                    print(f"Penalty after play: {post_pen.description}")
                    net_yards, note = apply_post_play_penalty_for_spot_and_note(play_yards, post_pen, offense, defense, penalty_totals)
                    if post_pen.automatic_first: after_first_down()

                # SAFETY check (run)
                if check_and_award_safety(net_yards, f"{canonical_name(runner)} tackled in own end zone vs {defense_formation}."):
                    if consume_clock(clock_play_type, clock_completed): continue
                    ai_maybe_timeout(); continue

                play_yards = cap_gain_to_td(ball_on, play_yards)
                net_yards = cap_gain_to_td(ball_on, net_yards)
                ball_on = clamp_play_spot(ball_on + net_yards)
                update_run_stats(stats, offense.name, runner, play_yards, False)
                direction = "gains" if net_yards >= 0 else "loses"
                print(f"RUN: {canonical_name(runner)} {direction} {abs(net_yards)} yards vs {defense_formation}{note}.")
                clock_play_type, clock_completed = "run", True

                if fumble_lost:
                    print("FUMBLE! Defense recovers.")
                    flip_possession(to_receiving_spot(ball_on))
                    if consume_clock(clock_play_type, clock_completed): continue
                    ai_maybe_timeout(); continue

                if ball_on >= 100:
                    print(f"TOUCHDOWN {offense.name}!")
                    ensure_player(stats, offense.name, runner)
                    stats[offense.name][canonical_name(runner)].touchdowns += 1
                    scoreboard[offense.name] += 7
                    print_score(scoreboard)
                    offense, defense, ball_on, line_to_gain, down = kickoff_to(defense)
                    consume_clock(clock_play_type, clock_completed)
                    ai_maybe_timeout(); continue

            elif selection == "pass":
                tendencies_user.push("pass")
                qb, receiver, play_yards, completed, intercepted, sacked, fumble_lost = simulate_pass(offense, defense_formation, None)
                clock_play_type, clock_completed = "pass", completed
                note = ""

                if sacked:
                    # SAFETY check (sack)
                    if check_and_award_safety(play_yards, f"Sack in the end zone vs {defense_formation}."):
                        if consume_clock(clock_play_type, False): continue
                        ai_maybe_timeout(); continue

                    ball_on = clamp_play_spot(ball_on + play_yards)
                    print(f"SACK: {canonical_name(qb)} sacked for {abs(play_yards)} yards vs {defense_formation}.")
                    if fumble_lost:
                        print("FUMBLE on the sack! Defense recovers.")
                        flip_possession(to_receiving_spot(ball_on))
                        if consume_clock(clock_play_type, False): continue
                        ai_maybe_timeout(); continue

                elif intercepted:
                    ensure_player(stats, offense.name, qb)
                    stats[offense.name][canonical_name(qb)].interceptions_thrown += 1
                    print(f"PASS: {canonical_name(qb)} throws an INTERCEPTION vs {defense_formation}!")
                    flip_possession(to_receiving_spot(ball_on))
                    if consume_clock(clock_play_type, False): continue
                    ai_maybe_timeout(); continue

                elif completed:
                    post_pen = maybe_penalty(offense, defense, is_pass=True)
                    net_yards = max(0, play_yards)
                    if post_pen and not post_pen.pre_snap:
                        print(f"Penalty after play: {post_pen.description}")
                        net_yards, note = apply_post_play_penalty_for_spot_and_note(net_yards, post_pen, offense, defense, penalty_totals)
                        if post_pen.automatic_first: after_first_down()

                    # SAFETY check (post-play penalty could create safety)
                    if check_and_award_safety(net_yards, f"Penalty enforced in own end zone vs {defense_formation}."):
                        if consume_clock(clock_play_type, True): continue
                        ai_maybe_timeout(); continue

                    play_yards = cap_gain_to_td(ball_on, max(0, play_yards))
                    net_yards = cap_gain_to_td(ball_on, max(0, net_yards))
                    ball_on = clamp_play_spot(ball_on + net_yards)
                    update_pass_stats(stats, offense.name, qb, receiver, play_yards, True, False, False)
                    print(f"PASS: {canonical_name(qb)} completes to {canonical_name(receiver)} for {net_yards} yards vs {defense_formation}{note}.")
                    if fumble_lost:
                        print("FUMBLE after the catch! Defense recovers.")
                        flip_possession(to_receiving_spot(ball_on))
                        if consume_clock(clock_play_type, True): continue
                        ai_maybe_timeout(); continue
                    if ball_on >= 100:
                        print(f"TOUCHDOWN {offense.name}!")
                        if receiver:
                            ensure_player(stats, offense.name, receiver)
                            stats[offense.name][canonical_name(receiver)].touchdowns += 1
                        scoreboard[offense.name] += 7
                        print_score(scoreboard)
                        offense, defense, ball_on, line_to_gain, down = kickoff_to(defense)
                        consume_clock(clock_play_type, True)
                        ai_maybe_timeout(); continue
                else:
                    print(f"PASS: {canonical_name(qb)} to {canonical_name(receiver)} is INCOMPLETE vs {defense_formation}.")

            elif selection == "deep":
                tendencies_user.push("pass")
                target = ai_choose_deep_target(offense, defense_formation)
                qb, receiver, play_yards, completed, intercepted, sacked, fumble_lost = simulate_deep_pass(offense, defense_formation, target)
                clock_play_type, clock_completed = "pass", completed
                note = ""

                if sacked:
                    # SAFETY check (deep sack)
                    if check_and_award_safety(play_yards, f"Sack in the end zone (deep) vs {defense_formation}."):
                        if consume_clock(clock_play_type, False): continue
                        ai_maybe_timeout(); continue

                    net_yards = play_yards
                    ball_on = clamp_play_spot(ball_on + net_yards)
                    print(f"SACK (deep): {canonical_name(qb)} sacked for {abs(net_yards)} yards vs {defense_formation}.")
                    if fumble_lost:
                        print("FUMBLE on the sack! Defense recovers.")
                        flip_possession(to_receiving_spot(ball_on))
                        if consume_clock(clock_play_type, False): continue
                        ai_maybe_timeout(); continue

                elif intercepted:
                    ensure_player(stats, offense.name, qb)
                    stats[offense.name][canonical_name(qb)].interceptions_thrown += 1
                    print(f"DEEP PASS: {canonical_name(qb)} throws an INTERCEPTION vs {defense_formation}!")
                    flip_possession(to_receiving_spot(ball_on))
                    if consume_clock(clock_play_type, False): continue
                    ai_maybe_timeout(); continue

                elif completed:
                    post_pen = maybe_penalty(offense, defense, is_pass=True)
                    net_yards = max(0, play_yards)
                    if post_pen and not post_pen.pre_snap:
                        print(f"Penalty after play: {post_pen.description}")
                        net_yards, note = apply_post_play_penalty_for_spot_and_note(net_yards, post_pen, offense, defense, penalty_totals)
                        if post_pen.automatic_first: after_first_down()

                    # SAFETY check (deep, post-play penalty could force safety)
                    if check_and_award_safety(net_yards, f"Penalty enforced in own end zone (deep) vs {defense_formation}."):
                        if consume_clock(clock_play_type, True): continue
                        ai_maybe_timeout(); continue

                    play_yards = cap_gain_to_td(ball_on, max(0, play_yards))
                    net_yards = cap_gain_to_td(ball_on, max(0, net_yards))
                    ball_on = clamp_play_spot(ball_on + net_yards)
                    update_pass_stats(stats, offense.name, qb, receiver, play_yards, True, False, False)
                    print(f"DEEP PASS: {canonical_name(qb)} hits {canonical_name(receiver)} for {net_yards} yards vs {defense_formation}{note}.")
                    if fumble_lost:
                        print("FUMBLE after the deep catch! Defense recovers.")
                        flip_possession(to_receiving_spot(ball_on))
                        if consume_clock(clock_play_type, True): continue
                        ai_maybe_timeout(); continue
                    if ball_on >= 100:
                        print(f"TOUCHDOWN {offense.name}!")
                        if receiver:
                            ensure_player(stats, offense.name, receiver)
                            stats[offense.name][canonical_name(receiver)].touchdowns += 1
                        scoreboard[offense.name] += 7
                        print_score(scoreboard)
                        offense, defense, ball_on, line_to_gain, down = kickoff_to(defense)
                        consume_clock(clock_play_type, True)
                        ai_maybe_timeout(); continue
                else:
                    print(f"DEEP PASS: {canonical_name(qb)} to {canonical_name(receiver)} is INCOMPLETE vs {defense_formation}.")

            elif selection == "punt":
                recv_ball_on, desc = punt_result(ball_on)
                print(desc)
                flip_possession(recv_ball_on)
                if consume_clock("kick", True): continue
                continue

            elif selection == "fg":
                prob = field_goal_success_prob(ball_on)
                dist = 100 - ball_on + 17
                print(f"Field goal attempt from {dist} yards.")
                if random.random() < prob:
                    print(f"FIELD GOAL is GOOD! {offense.name} +3.")
                    scoreboard[offense.name] += 3
                    print_score(scoreboard)
                    offense, defense, ball_on, line_to_gain, down = kickoff_to(defense)
                else:
                    print("FIELD GOAL is NO GOOD.")
                    flip_possession(to_receiving_spot(ball_on))
                if consume_clock("kick", True): continue
                continue

            if consume_clock(clock_play_type, clock_completed): continue
            ai_maybe_timeout()

            if ball_on >= line_to_gain:
                after_first_down()
            else:
                if down == 4:
                    print("Turnover on downs!")
                    flip_possession(to_receiving_spot(ball_on))
                else:
                    down += 1

        else:
            # ===== CPU Offense =====
            selection = user_defense_choice()
            if selection in ["stats", "score", "clock", "timeout", "quit"]:
                if selection == "stats": print_stats(stats, penalty_totals); continue
                if selection == "score": print_score(scoreboard); continue
                if selection == "clock": print(f"Quarter {quarter} — {mmss(seconds_left)}"); continue
                if selection == "timeout": call_timeout(defense); continue
                if selection == "quit": print("\nThanks for playing!"); print_score(scoreboard); print_stats(stats, penalty_totals); return

            defense_formation = selection
            cpu_call = ai_choose_offense(distance_to_first(), down, ball_on,
                                         seconds_left,
                                         scoreboard[offense.name] - scoreboard[defense.name])
            tendencies_cpu.push(cpu_call)
            print(f"Computer offense calls: {cpu_call}")

            clock_play_type = "run"; clock_completed = True

            if cpu_call == "run":
                runner, play_yards, _, fumble_lost = simulate_run(offense, defense_formation)
                post_pen = maybe_penalty(offense, defense, is_pass=False)
                note = ""
                net_yards = play_yards
                if post_pen and not post_pen.pre_snap:
                    print(f"Penalty after play: {post_pen.description}")
                    net_yards, note = apply_post_play_penalty_for_spot_and_note(play_yards, post_pen, offense, defense, penalty_totals)
                    if post_pen.automatic_first: after_first_down()

                # SAFETY check (CPU run)
                if check_and_award_safety(net_yards, f"{canonical_name(runner)} tackled in own end zone vs your {defense_formation}."):
                    if consume_clock(clock_play_type, clock_completed): continue
                    ai_maybe_timeout(); continue

                play_yards = cap_gain_to_td(ball_on, play_yards)
                net_yards = cap_gain_to_td(ball_on, net_yards)
                ball_on = clamp_play_spot(ball_on + net_yards)
                update_run_stats(stats, offense.name, runner, play_yards, False)
                direction = "gains" if net_yards >= 0 else "loses"
                print(f"RUN: {canonical_name(runner)} {direction} {abs(net_yards)} yards vs your {defense_formation}{note}.")
                clock_play_type, clock_completed = "run", True

                if fumble_lost:
                    print("FUMBLE! Your defense recovers.")
                    flip_possession(to_receiving_spot(ball_on))
                    if consume_clock(clock_play_type, clock_completed): continue
                    ai_maybe_timeout(); continue

                if ball_on >= 100:
                    print(f"TOUCHDOWN {offense.name}!")
                    ensure_player(stats, offense.name, runner)
                    stats[offense.name][canonical_name(runner)].touchdowns += 1
                    scoreboard[offense.name] += 7
                    print_score(scoreboard)
                    offense, defense, ball_on, line_to_gain, down = kickoff_to(defense)
                    consume_clock(clock_play_type, clock_completed)
                    ai_maybe_timeout(); continue

            elif cpu_call == "pass":
                target = ai_choose_target(offense, defense_formation)
                qb, receiver, play_yards, completed, intercepted, sacked, fumble_lost = simulate_pass(offense, defense_formation, target)
                clock_play_type, clock_completed = "pass", completed
                note = ""

                if sacked:
                    # SAFETY check (CPU sack)
                    if check_and_award_safety(play_yards, f"Sack in the end zone vs your {defense_formation}."):
                        if consume_clock(clock_play_type, False): continue
                        ai_maybe_timeout(); continue

                    ball_on = clamp_play_spot(ball_on + play_yards)
                    print(f"SACK: {canonical_name(qb)} sacked for {abs(play_yards)} yards vs your {defense_formation}.")
                    if fumble_lost:
                        print("FUMBLE on the sack! Your defense recovers.")
                        flip_possession(to_receiving_spot(ball_on))
                        if consume_clock(clock_play_type, False): continue
                        ai_maybe_timeout(); continue

                elif intercepted:
                    ensure_player(stats, offense.name, qb)
                    stats[offense.name][canonical_name(qb)].interceptions_thrown += 1
                    print(f"PASS: {canonical_name(qb)} throws an INTERCEPTION vs your {defense_formation}!")
                    flip_possession(to_receiving_spot(ball_on))
                    if consume_clock(clock_play_type, False): continue
                    ai_maybe_timeout(); continue

                elif completed:
                    post_pen = maybe_penalty(offense, defense, is_pass=True)
                    net_yards = max(0, play_yards)
                    if post_pen and not post_pen.pre_snap:
                        print(f"Penalty after play: {post_pen.description}")
                        net_yards, note = apply_post_play_penalty_for_spot_and_note(net_yards, post_pen, offense, defense, penalty_totals)
                        if post_pen.automatic_first: after_first_down()

                    # SAFETY check (CPU pass + penalty)
                    if check_and_award_safety(net_yards, f"Penalty enforced in own end zone vs your {defense_formation}."):
                        if consume_clock(clock_play_type, True): continue
                        ai_maybe_timeout(); continue

                    play_yards = cap_gain_to_td(ball_on, max(0, play_yards))
                    net_yards = cap_gain_to_td(ball_on, max(0, net_yards))
                    ball_on = clamp_play_spot(ball_on + net_yards)
                    update_pass_stats(stats, offense.name, qb, receiver, play_yards, True, False, False)
                    print(f"PASS: {canonical_name(qb)} completes to {canonical_name(receiver)} for {net_yards} yards vs your {defense_formation}{note}.")
                    if fumble_lost:
                        print("FUMBLE after the catch! Your defense recovers.")
                        flip_possession(to_receiving_spot(ball_on))
                        if consume_clock(clock_play_type, True): continue
                        ai_maybe_timeout(); continue
                    if ball_on >= 100:
                        print(f"TOUCHDOWN {offense.name}!")
                        if receiver:
                            ensure_player(stats, offense.name, receiver)
                            stats[offense.name][canonical_name(receiver)].touchdowns += 1
                        scoreboard[offense.name] += 7
                        print_score(scoreboard)
                        offense, defense, ball_on, line_to_gain, down = kickoff_to(defense)
                        consume_clock(clock_play_type, True)
                        ai_maybe_timeout(); continue
                else:
                    print(f"PASS: {canonical_name(qb)} to {canonical_name(receiver)} is INCOMPLETE vs your {defense_formation}.")

            elif cpu_call == "deep":
                target = ai_choose_deep_target(offense, defense_formation)
                qb, receiver, play_yards, completed, intercepted, sacked, fumble_lost = simulate_deep_pass(offense, defense_formation, target)
                clock_play_type, clock_completed = "pass", completed
                note = ""

                if sacked:
                    # SAFETY check (CPU deep sack)
                    if check_and_award_safety(play_yards, f"Sack in the end zone (deep) vs your {defense_formation}."):
                        if consume_clock(clock_play_type, False): continue
                        ai_maybe_timeout(); continue

                    net_yards = play_yards
                    ball_on = clamp_play_spot(ball_on + net_yards)
                    print(f"SACK (deep): {canonical_name(qb)} sacked for {abs(net_yards)} yards vs your {defense_formation}.")
                    if fumble_lost:
                        print("FUMBLE on the sack! Your defense recovers.")
                        flip_possession(to_receiving_spot(ball_on))
                        if consume_clock(clock_play_type, False): continue
                        ai_maybe_timeout(); continue

                elif intercepted:
                    ensure_player(stats, offense.name, qb)
                    stats[offense.name][canonical_name(qb)].interceptions_thrown += 1
                    print(f"DEEP PASS: {canonical_name(qb)} throws an INTERCEPTION vs your {defense_formation}!")
                    flip_possession(to_receiving_spot(ball_on))
                    if consume_clock(clock_play_type, False): continue
                    ai_maybe_timeout(); continue

                elif completed:
                    post_pen = maybe_penalty(offense, defense, is_pass=True)
                    net_yards = max(0, play_yards)
                    if post_pen and not post_pen.pre_snap:
                        print(f"Penalty after play: {post_pen.description}")
                        net_yards, note = apply_post_play_penalty_for_spot_and_note(net_yards, post_pen, offense, defense, penalty_totals)
                        if post_pen.automatic_first: after_first_down()

                    # SAFETY check (CPU deep pass + penalty)
                    if check_and_award_safety(net_yards, f"Penalty enforced in own end zone (deep) vs your {defense_formation}."):
                        if consume_clock(clock_play_type, True): continue
                        ai_maybe_timeout(); continue

                    play_yards = cap_gain_to_td(ball_on, max(0, play_yards))
                    net_yards = cap_gain_to_td(ball_on, max(0, net_yards))
                    ball_on = clamp_play_spot(ball_on + net_yards)
                    update_pass_stats(stats, offense.name, qb, receiver, play_yards, True, False, False)
                    print(f"DEEP PASS: {canonical_name(qb)} completes to {canonical_name(receiver)} for {net_yards} yards vs your {defense_formation}{note}.")
                    if fumble_lost:
                        print("FUMBLE after the deep catch! Your defense recovers.")
                        flip_possession(to_receiving_spot(ball_on))
                        if consume_clock(clock_play_type, True): continue
                        ai_maybe_timeout(); continue
                    if ball_on >= 100:
                        print(f"TOUCHDOWN {offense.name}!")
                        if receiver:
                            ensure_player(stats, offense.name, receiver)
                            stats[offense.name][canonical_name(receiver)].touchdowns += 1
                        scoreboard[offense.name] += 7
                        print_score(scoreboard)
                        offense, defense, ball_on, line_to_gain, down = kickoff_to(defense)
                        consume_clock(clock_play_type, True)
                        ai_maybe_timeout(); continue

                else:
                    print(f"DEEP PASS: {canonical_name(qb)} to {canonical_name(receiver)} is INCOMPLETE vs your {defense_formation}.")

            elif cpu_call == "punt":
                recv_ball_on, desc = punt_result(ball_on)
                print(desc)
                flip_possession(recv_ball_on)
                if consume_clock("kick", True): continue
                continue

            elif cpu_call == "fg":
                prob = field_goal_success_prob(ball_on)
                dist = 100 - ball_on + 17
                print(f"Field goal attempt from {dist} yards (success ~{int(prob*100)}%).")
                if random.random() < prob:
                    print(f"FIELD GOAL is GOOD! {offense.name} +3.")
                    scoreboard[offense.name] += 3
                    print_score(scoreboard)
                    offense, defense, ball_on, line_to_gain, down = kickoff_to(defense)
                else:
                    print("FIELD GOAL is NO GOOD.")
                    flip_possession(to_receiving_spot(ball_on))
                if consume_clock("kick", True): continue
                continue

            if consume_clock(clock_play_type, clock_completed): continue
            ai_maybe_timeout()

            if ball_on >= line_to_gain:
                after_first_down()
            else:
                if down == 4:
                    print("Turnover on downs!")
                    flip_possession(to_receiving_spot(ball_on))
                else:
                    down += 1

    print("\n=== Game Over (End of 4th) ===")
    print_score(scoreboard)
    print_stats(stats, penalty_totals)
    if scoreboard[user_team.name] > scoreboard[cpu_team.name]:
        print(f"{user_team.name} win! Congratulations on the victory!")
    elif scoreboard[user_team.name] < scoreboard[cpu_team.name]:
        print(f"{cpu_team.name} win! Better luck next time.")
    else:
        print("It's a tie.")

if __name__ == "__main__":
    game()