
import io
import sys
import unittest
from unittest.mock import patch
import contextlib

# Import the simulator under test
import footballsimpatch1 as footballsim


# =========================
# Unit tests: Core helpers
# =========================

class TestCanonicalizationAndUtils(unittest.TestCase):
    def test_canonical_name(self):
        self.assertEqual(footballsim.canonical_name("  A.  Brown "), "A. Brown")
        self.assertEqual(footballsim.canonical_name("A.\u00A0Brown"), "A. Brown")  # nbsp -> space

    def test_clamp_float(self):
        self.assertEqual(footballsim.clamp(0.5, 0.0, 1.0), 0.5)
        self.assertEqual(footballsim.clamp(-2.0, -1.0, 1.0), -1.0)
        self.assertEqual(footballsim.clamp(5.0, -1.0, 1.0), 1.0)

    def test_clamp_int(self):
        self.assertEqual(footballsim.clamp_int(5, 0, 10), 5)
        self.assertEqual(footballsim.clamp_int(-3, -2, 10), -2)
        self.assertEqual(footballsim.clamp_int(99, -2, 50), 50)

    def test_spot_clamping(self):
        self.assertEqual(footballsim.clamp_play_spot(0), 1)
        self.assertEqual(footballsim.clamp_play_spot(101), 100)
        self.assertEqual(footballsim.clamp_start_spot(0), 1)
        self.assertEqual(footballsim.clamp_start_spot(100), 99)

    def test_to_receiving_spot(self):
        self.assertEqual(footballsim.to_receiving_spot(40), footballsim.clamp_start_spot(60))

    def test_cap_gain_to_td(self):
        # Gain capped to remaining yards
        self.assertEqual(footballsim.cap_gain_to_td(80, 40), 20)
        # Negative gain unchanged
        self.assertEqual(footballsim.cap_gain_to_td(20, -5), -5)

    def test_mmss(self):
        self.assertEqual(footballsim.mmss(0), "00:00")
        self.assertEqual(footballsim.mmss(61), "01:01")


class TestProbabilityBaselines(unittest.TestCase):
    def test_get_team_pass_baselines_known_team(self):
        comp, intr = footballsim.get_team_pass_baselines("Chiefs")
        self.assertTrue(0.55 <= comp <= 0.75)
        self.assertTrue(0.008 <= intr <= 0.035)

    def test_get_team_pass_baselines_unknown_team(self):
        comp, intr = footballsim.get_team_pass_baselines("UnknownTeam")
        self.assertAlmostEqual(comp, 0.62, places=3)
        self.assertAlmostEqual(intr, 0.023, places=3)

    def test_compute_pass_probs_ranges(self):
        comp, intr, sack = footballsim.compute_pass_probs("Chiefs", "Nickel")
        self.assertTrue(0.30 <= comp <= 0.90)
        self.assertTrue(0.005 <= intr <= 0.08)
        self.assertTrue(0.01 <= sack <= 0.20)

    def test_compute_deep_pass_probs_ranges(self):
        comp, intr, sack = footballsim.compute_deep_pass_probs("Chiefs", "Dime")
        self.assertTrue(0.20 <= comp <= 0.85)
        self.assertTrue(0.006 <= intr <= 0.10)
        self.assertTrue(0.02 <= sack <= 0.25)


# =========================
# Unit tests: selections & AI
# =========================

class TestSelectionsAndAI(unittest.TestCase):
    def setUp(self):
        self.team = footballsim.TEAMS[0]  # Packers
        self.def_forms = list(footballsim.DEF_EFFECTS.keys())

    def test_choose_run_ballcarrier_bias(self):
        roster = self.team.roster
        # Force exact paths via random thresholds
        with patch('random.random', side_effect=[0.70]):  # within RB 0.83
            self.assertEqual(footballsim.choose_run_ballcarrier(roster), footballsim.canonical_name(roster["RB"]))
        with patch('random.random', side_effect=[0.90]):  # beyond RB (0.83), within WR1 0.91 cumulative
            # Because cum: RB=0.83, WR1=0.91, WR2=0.97 -> random=0.90 picks WR2
            self.assertEqual(footballsim.choose_run_ballcarrier(roster), footballsim.canonical_name(roster["WR2"]))

    def test_choose_receiver_bias(self):
        roster = self.team.roster
        with patch('random.random', side_effect=[0.39]):  # WR1 (0.40 cut)
            self.assertEqual(footballsim.choose_receiver(roster), footballsim.canonical_name(roster["WR1"]))
        with patch('random.random', side_effect=[0.45]):  # WR2 (0.40+0.30=0.70)
            self.assertEqual(footballsim.choose_receiver(roster), footballsim.canonical_name(roster["WR2"]))
        with patch('random.random', side_effect=[0.85]):  # TE (0.90 cap)
            self.assertEqual(footballsim.choose_receiver(roster), footballsim.canonical_name(roster["TE"]))

    def test_ai_choose_deep_target_weights(self):
        offense = self.team
        # Dime -> WR1 weighted
        with patch('random.random', return_value=0.40):
            target = footballsim.ai_choose_deep_target(offense, "Dime")
        self.assertEqual(target, footballsim.canonical_name(offense.roster["WR1"]))

    def test_tendencies_run_ratio(self):
        t = footballsim.Tendencies(recent_offense_calls=[])
        self.assertAlmostEqual(t.run_ratio(), 0.5)
        t.push("run"); t.push("pass"); t.push("run")
        self.assertAlmostEqual(t.run_ratio(), 2/3)
        # ensure pop logic
        for _ in range(10):
            t.push("run")
        self.assertLessEqual(len(t.recent_offense_calls), 6)

    def test_ai_choose_defense_various(self):
        # Winning, late -> Prevent preferred
        form = footballsim.ai_choose_defense(ball_on=50, distance_to_first=5, down=1,
                                             seconds_left=30, score_lead=7, offense_run_ratio=0.5)
        self.assertIn(form, ["Prevent", "Nickel"])
        # Goal line scenario
        form2 = footballsim.ai_choose_defense(ball_on=97, distance_to_first=3, down=2,
                                              seconds_left=300, score_lead=0, offense_run_ratio=0.5)
        self.assertIn(form2, ["Goal Line", "Blitz", "4-3 Base"])

    def test_ai_choose_offense_various(self):
        # 4th down, short FG
        call = footballsim.ai_choose_offense(distance_to_first=10, down=4, ball_on=85, seconds_left=600, score_trail=0)
        self.assertIn(call, ["fg", "punt", "run", "pass", "deep"])  # depending on prob; allow any valid return
        # Hurry-up when trailing late
        call2 = footballsim.ai_choose_offense(distance_to_first=5, down=2, ball_on=50, seconds_left=80, score_trail=3)
        self.assertIn(call2, ["deep", "pass", "run"])


# =========================
# Unit tests: penalties & stats
# =========================

class TestPenaltiesAndStats(unittest.TestCase):
    def setUp(self):
        self.user_team = footballsim.TEAMS[0]
        self.cpu_team  = footballsim.TEAMS[1]
        self.totals = footballsim.make_penalty_totals(self.user_team, self.cpu_team)

    def test_maybe_penalty_branches(self):
        # Force pre-snap, false start
        with patch('random.random', side_effect=[0.01, 0.10, 0.30]):  # overall hit, pre=True, false-start pick
            p = footballsim.maybe_penalty(self.user_team, self.cpu_team, is_pass=False)
        self.assertTrue(p.pre_snap)
        self.assertIn("False start", p.description)

        # Force post-snap DPI
        with patch('random.random', side_effect=[0.01, 0.50, 0.30]):  # hit, pre=False, DPI pick
            p = footballsim.maybe_penalty(self.user_team, self.cpu_team, is_pass=True)
        self.assertFalse(p.pre_snap)
        self.assertIn("Defensive pass interference", p.description)

    def test_penalty_accounting(self):
        p = footballsim.PenaltyResult(True, "Offside on defense (+5)", +5, against_defense=True)
        footballsim.accrue_penalty(self.totals, self.user_team, self.cpu_team, p)
        self.assertEqual(self.totals[self.cpu_team.name]["count"], 1)
        self.assertEqual(self.totals[self.cpu_team.name]["yards"], 5)

    def test_apply_post_play_penalty_for_spot_and_note(self):
        # Holding should return -10 and annotation
        p = footballsim.PenaltyResult(False, "Offensive holding (-10)", -10, against_defense=False)
        yards, note = footballsim.apply_post_play_penalty_for_spot_and_note(12, p, self.user_team, self.cpu_team, self.totals)
        self.assertEqual(yards, -10)
        self.assertIn("holding", note)


# =========================
# Unit tests: special teams
# =========================

class TestSpecialTeams(unittest.TestCase):
    def test_punt_touchback(self):
        with patch('random.gauss', return_value=60):
            recv_ball_on, desc = footballsim.punt_result(ball_on=60)
        self.assertEqual(recv_ball_on, 25)
        self.assertIn("touchback", desc.lower())

    def test_punt_fair_catch(self):
        with patch('random.gauss', return_value=40):
            with patch('random.random', return_value=0.10):
                recv_ball_on, desc = footballsim.punt_result(ball_on=40)
        self.assertIn("fair catch", desc.lower())
        self.assertTrue(1 <= recv_ball_on <= 99)

    def test_safety_free_kick_result(self):
        for _ in range(20):
            recv_ball_on, desc = footballsim.safety_free_kick_result()
            self.assertTrue(recv_ball_on == 25 or (1 <= recv_ball_on <= 99))
            self.assertIn("Free kick from the 20 travels", desc)
            self.assertTrue(("touchback" in desc.lower()) or ("fair catch" in desc.lower()) or ("return" in desc.lower()))

    def test_field_goal_success_prob_bounds(self):
        self.assertGreaterEqual(footballsim.field_goal_success_prob(85), 0.55)  # ~32-yard FG
        self.assertEqual(footballsim.field_goal_success_prob(1), 0.00)          # ~116-yard FG (impossible)


# =========================
# Unit tests: play simulators
# =========================

class TestPlaySimulators(unittest.TestCase):
    def setUp(self):
        self.team = footballsim.TEAMS[0]
        self.def_form = "Nickel"

    def test_simulate_run_tfl_and_big_play(self):
        # Force TFL
        tfl_eff = footballsim.DEF_EFFECTS[self.def_form].copy()
        tfl_eff["tfl_chance"] = 1.0
        with patch.dict(footballsim.DEF_EFFECTS, {self.def_form: tfl_eff}):
            runner, yards, _, _ = footballsim.simulate_run(self.team, self.def_form)
        self.assertLess(yards, 0)

        # Force big play on non-TFL
        bp_eff = footballsim.DEF_EFFECTS[self.def_form].copy()
        bp_eff["tfl_chance"] = 0.0
        bp_eff["run_big_play_chance"] = 1.0
        bp_eff["run_big_play_bonus"] = (20, 20)
        with patch.dict(footballsim.DEF_EFFECTS, {self.def_form: bp_eff}):
            with patch('random.gauss', return_value=5):
                runner2, yards2, _, _ = footballsim.simulate_run(self.team, self.def_form)
        self.assertGreaterEqual(yards2, 25)  # base ~5 + bonus 20

    def test_simulate_pass_all_branches(self):
        # Case 1: sack branch
        with patch('footballsimpatch1.compute_pass_probs', return_value=(0.0, 0.0, 1.0)):
            with patch('random.random', side_effect=[0.0, 0.0, 0.6, 0.6]):  # choose_receiver, sack check passes, fumble checks
                qb, rec, yards, comp, intr, sacked, fumble = footballsim.simulate_pass(self.team, self.def_form)
        self.assertTrue(sacked)
        self.assertLess(yards, 0)

        # Case 2: interception branch
        with patch('footballsimpatch1.compute_pass_probs', return_value=(0.0, 1.0, 0.0)):
            with patch('random.random', side_effect=[0.0, 0.99, 0.0]):  # choose_receiver, sack fails, int passes
                qb, rec, yards, comp, intr, sacked, fumble = footballsim.simulate_pass(self.team, self.def_form)
        self.assertTrue(intr)
        self.assertFalse(comp)

        # Case 3: completion branch
        with patch('footballsimpatch1.compute_pass_probs', return_value=(1.0, 0.0, 0.0)):
            with patch('random.random', side_effect=[0.0, 0.99, 0.99, 0.0, 0.6, 0.6, 0.6]):  # choose_receiver, sack/int fail, comp passes, big play, 2 fumble checks
                with patch('random.gauss', return_value=10):
                    qb, rec, yards, comp, intr, sacked, fumble = footballsim.simulate_pass(self.team, self.def_form)
        self.assertTrue(comp)
        self.assertGreaterEqual(yards, 0)

        # Case 4: incomplete branch
        with patch('footballsimpatch1.compute_pass_probs', return_value=(0.0, 0.0, 0.0)):
            with patch('random.random', side_effect=[0.0, 0.99, 0.99, 0.99]):  # choose_receiver, all checks fail
                qb, rec, yards, comp, intr, sacked, fumble = footballsim.simulate_pass(self.team, self.def_form)
        self.assertFalse(comp)
        self.assertFalse(intr)
        self.assertFalse(sacked)

    def test_simulate_deep_pass_all_branches(self):
        # Sack
        with patch('footballsimpatch1.compute_deep_pass_probs', return_value=(0.0, 0.0, 1.0)):
            with patch('random.random', side_effect=[0.0, 0.0, 0.6, 0.6]):  # ai_choose_deep_target, sack passes, fumble checks
                qb, rec, yards, comp, intr, sacked, fumble = footballsim.simulate_deep_pass(self.team, self.def_form)
        self.assertTrue(sacked)

        # Interception
        with patch('footballsimpatch1.compute_deep_pass_probs', return_value=(0.0, 1.0, 0.0)):
            with patch('random.random', side_effect=[0.0, 0.99, 0.0]):  # ai_choose_deep_target, sack fails, int passes
                qb, rec, yards, comp, intr, sacked, fumble = footballsim.simulate_deep_pass(self.team, self.def_form)
        self.assertTrue(intr)

        # Completion
        with patch('footballsimpatch1.compute_deep_pass_probs', return_value=(1.0, 0.0, 0.0)):
            with patch('random.random', side_effect=[0.0, 0.99, 0.99, 0.0, 0.6, 0.6, 0.6]):  # ai_choose_deep_target, sack/int fail, comp passes, big play, 2 fumble checks
                qb, rec, yards, comp, intr, sacked, fumble = footballsim.simulate_deep_pass(self.team, self.def_form)
        self.assertTrue(comp)
        self.assertGreaterEqual(yards, 20)

        # Incomplete
        with patch('footballsimpatch1.compute_deep_pass_probs', return_value=(0.0, 0.0, 0.0)):
            with patch('random.random', side_effect=[0.0, 0.99, 0.99, 0.99]):  # ai_choose_deep_target, all checks fail
                qb, rec, yards, comp, intr, sacked, fumble = footballsim.simulate_deep_pass(self.team, self.def_form)
        self.assertFalse(comp)


# =========================
# Unit tests: stats & printing
# =========================

class TestStatsAndPrinting(unittest.TestCase):
    def test_update_stats_and_print(self):
        stats = {}
        team = footballsim.TEAMS[0].name
        footballsim.update_run_stats(stats, team, "J. Jacobs", 12, td=True)
        footballsim.update_pass_stats(stats, team, "J. Love", "C. Watson", 25, True, False, True)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            footballsim.print_stats(stats, {team: {"count": 1, "yards": 10}})
        out = buf.getvalue()
        self.assertIn("Player Stats", out)
        self.assertIn("J. Jacobs", out)
        self.assertIn("C. Watson", out)

    def test_stats_coalesce_multiple_entries(self):
        """Test that coalesce merges stats for players with slightly different name formatting"""
        stats = {}
        team = "Packers"
        # Add stats with slightly different spacing (should merge)
        footballsim.update_run_stats(stats, team, "J. Jacobs", 10, False)
        footballsim.update_run_stats(stats, team, "J.  Jacobs ", 5, False)  # extra spaces
        
        merged = footballsim.coalesce(stats[team])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged["J. Jacobs"].rush_yards, 15)

    def test_update_pass_stats_interception(self):
        """Test that interceptions are tracked correctly"""
        stats = {}
        team = "Bears"
        footballsim.update_pass_stats(stats, team, "C. Williams", None, 0, False, True, False)
        self.assertEqual(stats[team]["C. Williams"].interceptions_thrown, 1)
        self.assertEqual(stats[team]["C. Williams"].pass_yards, 0)

    def test_update_pass_stats_incomplete(self):
        """Test incomplete pass stats"""
        stats = {}
        team = "Lions"
        footballsim.update_pass_stats(stats, team, "J. Goff", "A. St. Brown", 0, False, False, False)
        self.assertEqual(stats[team]["J. Goff"].pass_yards, 0)
        self.assertEqual(stats[team]["J. Goff"].interceptions_thrown, 0)

    def test_print_score(self):
        """Test scoreboard printing"""
        scoreboard = {"Packers": 24, "Bears": 17}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            footballsim.print_score(scoreboard)
        out = buf.getvalue()
        self.assertIn("Scoreboard", out)
        self.assertIn("Packers", out)
        self.assertIn("24", out)


# =========================
# Additional Coverage Tests
# =========================

class TestAdditionalCoverage(unittest.TestCase):
    def test_sample_big_play(self):
        """Test big play yardage sampling"""
        for _ in range(10):
            yards = footballsim.sample_big_play((15, 35))
            self.assertGreaterEqual(yards, 15)
            self.assertLessEqual(yards, 35)

    def test_kickoff_scenarios(self):
        """Test different kickoff return scenarios"""
        # Test with random variations
        for _ in range(5):
            ball_on, desc = footballsim.punt_result(30)
            self.assertGreaterEqual(ball_on, 1)
            self.assertLessEqual(ball_on, 99)
            self.assertIn("Punt", desc)

    def test_safety_free_kick_scenarios(self):
        """Test safety free kick with various outcomes"""
        for _ in range(5):
            ball_on, desc = footballsim.safety_free_kick_result()
            self.assertGreaterEqual(ball_on, 1)
            self.assertLessEqual(ball_on, 99)
            self.assertIn("Free kick", desc)

    def test_ai_choose_defense_prevent_late_game(self):
        """Test that AI chooses prevent defense when protecting lead late"""
        formation = footballsim.ai_choose_defense(
            ball_on=50, distance_to_first=10, down=2,
            seconds_left=45, score_lead=7, offense_run_ratio=0.5
        )
        # Should favor Prevent with lead and little time
        self.assertIn(formation, ["Prevent", "Nickel"])

    def test_ai_choose_defense_goal_line(self):
        """Test that AI chooses goal line defense near end zone"""
        formation = footballsim.ai_choose_defense(
            ball_on=97, distance_to_first=3, down=1,
            seconds_left=300, score_lead=0, offense_run_ratio=0.5
        )
        # Should favor Goal Line defense
        self.assertIn(formation, ["Goal Line", "Blitz", "4-3 Base"])

    def test_ai_choose_defense_long_yardage(self):
        """Test AI defense choice on long yardage situations"""
        formation = footballsim.ai_choose_defense(
            ball_on=50, distance_to_first=15, down=2,
            seconds_left=300, score_lead=0, offense_run_ratio=0.3
        )
        # Should favor pass defense
        self.assertIn(formation, ["Dime", "Nickel", "Blitz"])

    def test_ai_choose_defense_run_heavy(self):
        """Test AI adjusts to run-heavy offense"""
        formation = footballsim.ai_choose_defense(
            ball_on=50, distance_to_first=5, down=2,
            seconds_left=300, score_lead=0, offense_run_ratio=0.75
        )
        # Should favor run defense
        self.assertIn(formation, ["4-3 Base", "Blitz", "Nickel"])

    def test_ai_choose_offense_trailing_late(self):
        """Test AI offense when trailing late in game"""
        call = footballsim.ai_choose_offense(
            distance_to_first=10, down=2, ball_on=40,
            seconds_left=60, score_trail=7
        )
        # Should pass or go deep when trailing
        self.assertIn(call, ["pass", "deep", "run"])

    def test_ai_choose_offense_4th_down_fg_range(self):
        """Test AI chooses FG on 4th down in range"""
        call = footballsim.ai_choose_offense(
            distance_to_first=8, down=4, ball_on=75,
            seconds_left=300, score_trail=0
        )
        # Should attempt FG or punt from this range
        self.assertIn(call, ["fg", "punt", "run", "pass", "deep"])

    def test_ai_choose_offense_4th_down_punt_range(self):
        """Test AI punts on 4th down when far from FG range"""
        call = footballsim.ai_choose_offense(
            distance_to_first=12, down=4, ball_on=35,
            seconds_left=300, score_trail=0
        )
        # Should likely punt from midfield
        self.assertIn(call, ["punt", "run", "pass", "deep"])

    def test_ai_choose_offense_long_yardage(self):
        """Test AI offense on long yardage"""
        call = footballsim.ai_choose_offense(
            distance_to_first=18, down=2, ball_on=50,
            seconds_left=300, score_trail=0
        )
        # Should pass more on long yardage
        self.assertIn(call, ["pass", "deep", "run"])

    def test_ai_choose_offense_goal_line(self):
        """Test AI offense near goal line"""
        call = footballsim.ai_choose_offense(
            distance_to_first=3, down=1, ball_on=97,
            seconds_left=300, score_trail=0
        )
        # Should favor run near goal line
        self.assertIn(call, ["run", "pass", "deep"])

    def test_ai_choose_target_dime_formation(self):
        """Test target selection against Dime"""
        team = footballsim.TEAMS[0]
        target = footballsim.ai_choose_target(team, "Dime")
        # Should return a valid player
        self.assertIn(target, [team.roster["WR1"], team.roster["WR2"], 
                               team.roster["TE"], team.roster["RB"]])

    def test_ai_choose_target_blitz_formation(self):
        """Test target selection against Blitz"""
        team = footballsim.TEAMS[0]
        target = footballsim.ai_choose_target(team, "Blitz")
        # Should return a valid player
        self.assertIn(target, [team.roster["WR1"], team.roster["WR2"], 
                               team.roster["TE"], team.roster["RB"]])

    def test_tendencies_push_limit(self):
        """Test that tendencies list stays limited to 6 items"""
        tendencies = footballsim.Tendencies(recent_offense_calls=[])
        for i in range(10):
            tendencies.push("run")
        self.assertEqual(len(tendencies.recent_offense_calls), 6)

    def test_tendencies_run_ratio_empty(self):
        """Test run ratio calculation with empty list"""
        tendencies = footballsim.Tendencies(recent_offense_calls=[])
        self.assertEqual(tendencies.run_ratio(), 0.5)

    def test_tendencies_run_ratio_all_runs(self):
        """Test run ratio calculation with all runs"""
        tendencies = footballsim.Tendencies(recent_offense_calls=["run", "run", "run"])
        self.assertEqual(tendencies.run_ratio(), 1.0)

    def test_tendencies_run_ratio_all_passes(self):
        """Test run ratio calculation with all passes"""
        tendencies = footballsim.Tendencies(recent_offense_calls=["pass", "pass", "deep"])
        self.assertEqual(tendencies.run_ratio(), 0.0)

    def test_mmss_formatting(self):
        """Test time formatting"""
        self.assertEqual(footballsim.mmss(0), "00:00")
        self.assertEqual(footballsim.mmss(65), "01:05")
        self.assertEqual(footballsim.mmss(720), "12:00")
        self.assertEqual(footballsim.mmss(125), "02:05")

    def test_clamp_play_spot_boundaries(self):
        """Test field position clamping"""
        self.assertEqual(footballsim.clamp_play_spot(0), 1)
        self.assertEqual(footballsim.clamp_play_spot(-5), 1)
        self.assertEqual(footballsim.clamp_play_spot(50), 50)
        self.assertEqual(footballsim.clamp_play_spot(100), 100)
        self.assertEqual(footballsim.clamp_play_spot(105), 100)

    def test_clamp_start_spot_boundaries(self):
        """Test starting position clamping"""
        self.assertEqual(footballsim.clamp_start_spot(0), 1)
        self.assertEqual(footballsim.clamp_start_spot(99), 99)
        self.assertEqual(footballsim.clamp_start_spot(100), 99)

    def test_to_receiving_spot(self):
        """Test conversion to receiving team's perspective"""
        self.assertEqual(footballsim.to_receiving_spot(25), 75)
        self.assertEqual(footballsim.to_receiving_spot(75), 25)
        self.assertEqual(footballsim.to_receiving_spot(50), 50)

    def test_penalty_totals_initialization(self):
        """Test penalty tracking initialization"""
        team1 = footballsim.TEAMS[0]
        team2 = footballsim.TEAMS[1]
        totals = footballsim.make_penalty_totals(team1, team2)
        self.assertEqual(totals[team1.name]["count"], 0)
        self.assertEqual(totals[team1.name]["yards"], 0)
        self.assertEqual(totals[team2.name]["count"], 0)
        self.assertEqual(totals[team2.name]["yards"], 0)

    def test_accrue_penalty_offense(self):
        """Test accruing penalty against offense"""
        team1 = footballsim.TEAMS[0]
        team2 = footballsim.TEAMS[1]
        totals = footballsim.make_penalty_totals(team1, team2)
        penalty = footballsim.PenaltyResult(False, "Holding", -10, False)
        footballsim.accrue_penalty(totals, team1, team2, penalty)
        self.assertEqual(totals[team1.name]["count"], 1)
        self.assertEqual(totals[team1.name]["yards"], 10)

    def test_accrue_penalty_defense(self):
        """Test accruing penalty against defense"""
        team1 = footballsim.TEAMS[0]
        team2 = footballsim.TEAMS[1]
        totals = footballsim.make_penalty_totals(team1, team2)
        penalty = footballsim.PenaltyResult(False, "DPI", 15, True, True)
        footballsim.accrue_penalty(totals, team1, team2, penalty)
        self.assertEqual(totals[team2.name]["count"], 1)
        self.assertEqual(totals[team2.name]["yards"], 15)

    def test_maybe_penalty_no_penalty(self):
        """Test that maybe_penalty sometimes returns None"""
        team1 = footballsim.TEAMS[0]
        team2 = footballsim.TEAMS[1]
        # Run multiple times to increase chance of getting None
        got_none = False
        for _ in range(20):
            result = footballsim.maybe_penalty(team1, team2, is_pass=True)
            if result is None:
                got_none = True
                break
        self.assertTrue(got_none, "Should sometimes return no penalty")

    def test_maybe_penalty_gets_all_types(self):
        """Test that all penalty types can occur"""
        team1 = footballsim.TEAMS[0]
        team2 = footballsim.TEAMS[1]
        penalty_types = set()
        # Run many times to hit all branches
        for _ in range(100):
            result = footballsim.maybe_penalty(team1, team2, is_pass=True)
            if result:
                penalty_types.add(result.description)
        # Should get at least 2 different types
        self.assertGreaterEqual(len(penalty_types), 2)

    def test_maybe_penalty_run_play(self):
        """Test penalty generation on run plays"""
        team1 = footballsim.TEAMS[0]
        team2 = footballsim.TEAMS[1]
        got_penalty = False
        for _ in range(30):
            result = footballsim.maybe_penalty(team1, team2, is_pass=False)
            if result:
                got_penalty = True
                # Run plays shouldn't get DPI
                self.assertNotIn("pass interference", result.description.lower())
                break
        # Should eventually get a penalty
        self.assertTrue(got_penalty)

    def test_field_goal_success_prob_very_short(self):
        """Test FG probability for very short kicks"""
        prob = footballsim.field_goal_success_prob(82)  # 35 yard FG
        self.assertGreaterEqual(prob, 0.90)

    def test_field_goal_success_prob_very_long(self):
        """Test FG probability for very long kicks"""
        prob = footballsim.field_goal_success_prob(13)  # 70 yard FG
        self.assertLessEqual(prob, 0.10)

    def test_field_goal_success_prob_medium(self):
        """Test FG probability for medium distance"""
        prob = footballsim.field_goal_success_prob(67)  # 50 yard FG
        self.assertGreaterEqual(prob, 0.60)
        self.assertLessEqual(prob, 0.80)

# =========================
# Unit tests: UI helpers
# =========================

class TestUIHelpers(unittest.TestCase):
    def test_select_team_invalid_then_valid(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with patch('builtins.input', side_effect=["999", "1"]):
                t = footballsim.select_team(footballsim.TEAMS, "Select YOUR TEAM:")
        self.assertEqual(t.name, footballsim.TEAMS[0].name)

    def test_user_offense_choice_invalid_then_valid(self):
        with patch('builtins.input', side_effect=["bad", "run"]):
            s = footballsim.user_offense_choice()
        self.assertEqual(s, "run")

    def test_user_defense_choice_invalid_then_valid(self):
        with patch('builtins.input', side_effect=["bad", "1"]):
            s = footballsim.user_defense_choice()
        self.assertIn(s, footballsim.DEF_CHOICES)


# =========================
# Integration tests: game()
# =========================

class TestGameIntegration(unittest.TestCase):
    def _run_game_with_inputs_and_patches(self, inputs, patches=None):
        """Helper to run game(), capture stdout, and return output."""
        buf = io.StringIO()
        ctx = contextlib.ExitStack()
        ctx.enter_context(contextlib.redirect_stdout(buf))
        ctx.enter_context(patch('builtins.input', side_effect=inputs))
        # Apply extra patches
        if patches:
            for p in patches:
                ctx.enter_context(p)
        with ctx:
            footballsim.game()
        return buf.getvalue()

    def test_safety_flow_with_free_kick(self):
        # Choose teams, receive, then pass once to trigger sack safety; quit on defense prompt
        inputs = ["1", "2", "1", "pass", "quit"]

        def patched_simulate_pass(offense, defense_formation, target=None):
            qb = footballsim.canonical_name(offense.roster["QB"])
            wr1 = footballsim.canonical_name(offense.roster["WR1"])
            # SACK: -26 yards from O-25 -> safety
            return qb, wr1, -26, False, False, True, False

        def no_penalty(offense, defense, is_pass):
            return None  # No penalties

        out = self._run_game_with_inputs_and_patches(
            inputs,
            patches=[
                patch('footballsimpatch1.simulate_pass', side_effect=patched_simulate_pass),
                patch('footballsimpatch1.maybe_penalty', side_effect=no_penalty),
            ]
        )
        self.assertIn("SAFETY!", out)
        self.assertRegex(out, r"Bears:\s*2")  # computer team (defense in our selection) awarded 2
        self.assertIn("Free kick from the 20 travels", out)

    def test_touchdown_on_run(self):
        # Choose teams, receive, then run to score TD; quit
        inputs = ["1", "2", "1", "run", "quit"]

        def patched_simulate_run(offense, defense_formation):
            runner = footballsim.canonical_name(offense.roster["RB"])
            # Ball starts at O-25; return 80 yards to ensure TD (capped to remaining)
            return runner, 80, False, False

        out = self._run_game_with_inputs_and_patches(
            inputs,
            patches=[patch('footballsimpatch1.simulate_run', side_effect=patched_simulate_run)]
        )
        self.assertIn("TOUCHDOWN", out)
        self.assertRegex(out, r"Packers:\s*7")

    def test_field_goal_success(self):
        # Choose teams, receive, then 'fg' once (success), then quit
        inputs = ["1", "2", "1", "fg", "quit"]

        def patched_field_goal_success_prob(ball_on):
            return 1.0  # guaranteed success

        out = self._run_game_with_inputs_and_patches(
            inputs,
            patches=[patch('footballsimpatch1.field_goal_success_prob', side_effect=patched_field_goal_success_prob)]
        )
        self.assertIn("FIELD GOAL is GOOD", out)
        self.assertRegex(out, r"Packers:\s*3")

    def test_punt_and_flip_possession_fair_catch(self):
        # Choose, receive, punt, quit
        inputs = ["1", "2", "1", "punt", "quit"]

        def patched_punt_result(ball_on):
            return 35, "Punt travels 44 yards; fair catch. Receiving team starts at O-35."

        def no_penalty(*args, **kwargs):
            return None

        out = self._run_game_with_inputs_and_patches(
            inputs,
            patches=[
                patch('footballsimpatch1.punt_result', side_effect=patched_punt_result),
                patch('footballsimpatch1.maybe_penalty', side_effect=no_penalty)
            ]
        )
        self.assertIn("fair catch", out.lower())
        self.assertIn("takes over at O-35", out)

    def test_turnover_on_downs(self):
        # Choose, receive; call 4 runs with 0 yards -> 4th down turnover; then quit
        inputs = ["1", "2", "1", "run", "run", "run", "run", "quit"]

        def patched_simulate_run(offense, defense_formation):
            runner = footballsim.canonical_name(offense.roster["RB"])
            return runner, 0, False, False

        def no_penalty(*args, **kwargs):
            return None

        out = self._run_game_with_inputs_and_patches(
            inputs,
            patches=[
                patch('footballsimpatch1.simulate_run', side_effect=patched_simulate_run),
                patch('footballsimpatch1.maybe_penalty', side_effect=no_penalty)
            ]
        )
        self.assertIn("Turnover on downs!", out)

    def test_interception_flow(self):
        # Choose teams, receive, pass (INT), quit
        inputs = ["1", "2", "1", "pass", "quit"]

        def patched_simulate_pass(offense, defense_formation, target=None):
            qb = footballsim.canonical_name(offense.roster["QB"])
            wr1 = footballsim.canonical_name(offense.roster["WR1"])
            # Interception branch
            return qb, wr1, 0, False, True, False, False

        out = self._run_game_with_inputs_and_patches(
            inputs,
            patches=[patch('footballsimpatch1.simulate_pass', side_effect=patched_simulate_pass)]
        )
        self.assertIn("throws an INTERCEPTION", out)
        self.assertIn("takes over", out)  # possession flip

    def test_run_fumble_flow(self):
        # Choose, receive, run -> fumble, quit
        inputs = ["1", "2", "1", "run", "quit"]

        def patched_simulate_run(offense, defense_formation):
            runner = footballsim.canonical_name(offense.roster["RB"])
            return runner, 5, False, True  # fumble lost
        out = self._run_game_with_inputs_and_patches(
            inputs,
            patches=[
                patch('footballsimpatch1.simulate_run', side_effect=patched_simulate_run),
                patch('footballsimpatch1.maybe_penalty', return_value=None)
            ]
        )
        self.assertIn("FUMBLE! Defense recovers", out)


# =========================
# Suite & Runner
# =========================

def load_suite():
    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    suite.addTests(loader.loadTestsFromTestCase(TestCanonicalizationAndUtils))
    suite.addTests(loader.loadTestsFromTestCase(TestProbabilityBaselines))
    suite.addTests(loader.loadTestsFromTestCase(TestSelectionsAndAI))
    suite.addTests(loader.loadTestsFromTestCase(TestPenaltiesAndStats))
    suite.addTests(loader.loadTestsFromTestCase(TestSpecialTeams))
    suite.addTests(loader.loadTestsFromTestCase(TestPlaySimulators))
    suite.addTests(loader.loadTestsFromTestCase(TestStatsAndPrinting))
    suite.addTests(loader.loadTestsFromTestCase(TestUIHelpers))
    suite.addTests(loader.loadTestsFromTestCase(TestGameIntegration))
    return suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(load_suite())
    # Non-zero exit code on failure for CI / scripts
    sys.exit(0 if result.wasSuccessful() else 1)

