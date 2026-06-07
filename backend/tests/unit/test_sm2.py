"""Unit tests for the SM-2 spaced repetition algorithm."""
from datetime import date, timedelta
from app.routers.review import sm2_calculate, MIN_EF


class TestSM2Algorithm:
    """Test the SM-2 algorithm implementation."""

    # --- Quality 3 (Good) progression ---
    def test_good_first_time__interval_1_reps_1(self):
        """First correct answer should set interval=1, reps=1."""
        new_ef, new_interval, new_reps, next_date = sm2_calculate(
            quality=3,
            easiness_factor=2.5,
            interval_days=1,
            repetitions=0,
        )
        assert new_interval == 1
        assert new_reps == 1
        assert next_date == date.today() + timedelta(days=1)

    def test_good_second_time__interval_6_reps_2(self):
        """Second correct answer should set interval=6, reps=2."""
        new_ef, new_interval, new_reps, next_date = sm2_calculate(
            quality=3,
            easiness_factor=2.5,
            interval_days=1,
            repetitions=1,
        )
        assert new_interval == 6
        assert new_reps == 2
        assert next_date == date.today() + timedelta(days=6)

    def test_good_third_time__interval_grows(self):
        """Third correct answer should grow interval by EF."""
        new_ef, new_interval, new_reps, next_date = sm2_calculate(
            quality=3,
            easiness_factor=2.5,
            interval_days=6,
            repetitions=2,
        )
        # EF is updated first: 2.5 + (0.1 - (5-3)*(0.08+(5-3)*0.02)) = 2.36
        # Then interval = round(6 * 2.36) = round(14.16) = 14
        assert new_interval == 14
        assert new_reps == 3
        assert next_date == date.today() + timedelta(days=14)

    # --- Quality 5 (Easy) ---
    def test_easy_increases_easiness_factor(self):
        """Easy should increase easiness factor."""
        new_ef, _, _, _ = sm2_calculate(
            quality=5,
            easiness_factor=2.5,
            interval_days=1,
            repetitions=0,
        )
        assert new_ef > 2.5

    def test_easy_grows_interval_faster(self):
        """Easy should grow interval faster than good."""
        _, good_interval, _, _ = sm2_calculate(
            quality=3, easiness_factor=2.5, interval_days=6, repetitions=2,
        )
        _, easy_interval, _, _ = sm2_calculate(
            quality=5, easiness_factor=2.5, interval_days=6, repetitions=2,
        )
        assert easy_interval > good_interval

    # --- Quality 1-2 (Again/Hard) ---
    def test_again_resets_interval_to_1(self):
        """Quality < 3 should reset interval to 1."""
        new_ef, new_interval, new_reps, next_date = sm2_calculate(
            quality=1,
            easiness_factor=2.5,
            interval_days=15,
            repetitions=3,
        )
        assert new_interval == 1
        assert new_reps == 0
        assert next_date == date.today()  # No future date for failed reviews

    def test_hard_resets_interval_to_1(self):
        """Quality = 2 should reset interval to 1."""
        new_ef, new_interval, new_reps, _ = sm2_calculate(
            quality=2,
            easiness_factor=2.5,
            interval_days=15,
            repetitions=3,
        )
        assert new_interval == 1
        assert new_reps == 0

    # --- Easiness Factor bounds ---
    def test_easiness_factor_minimum_1_3(self):
        """Easiness factor should not go below 1.3."""
        # Quality 0 repeatedly should approach MIN_EF
        ef = 2.5
        for _ in range(10):
            ef, _, _, _ = sm2_calculate(
                quality=0, easiness_factor=ef, interval_days=1, repetitions=0,
            )
        assert ef == MIN_EF

    def test_easiness_factor_decreases_on_hard(self):
        """Hard quality should decrease easiness factor."""
        new_ef, _, _, _ = sm2_calculate(
            quality=2,
            easiness_factor=2.5,
            interval_days=1,
            repetitions=0,
        )
        assert new_ef < 2.5

    def test_easiness_factor_stays_at_min_1_3(self):
        """Easiness factor should stay at 1.3 when already at minimum."""
        new_ef, _, _, _ = sm2_calculate(
            quality=0,
            easiness_factor=1.3,
            interval_days=1,
            repetitions=0,
        )
        assert new_ef == 1.3

    # --- Quality 0 (Complete blackout) ---
    def test_quality_0_resets_everything(self):
        """Quality 0 should reset interval to 1 and reps to 0."""
        _, new_interval, new_reps, _ = sm2_calculate(
            quality=0,
            easiness_factor=3.0,
            interval_days=30,
            repetitions=10,
        )
        assert new_interval == 1
        assert new_reps == 0

    # --- Interval calculation edge cases ---
    def test_interval_rounds_to_nearest_integer(self):
        """Interval should be rounded to nearest integer."""
        # 6 * 2.56 = 15.36 -> round to 15
        _, new_interval, _, _ = sm2_calculate(
            quality=3,
            easiness_factor=2.7,
            interval_days=6,
            repetitions=2,
        )
        assert new_interval == 15

    def test_next_date_is_today_on_failed_review(self):
        """Failed review should have next_date as today (no future date)."""
        _, _, _, next_date = sm2_calculate(
            quality=1,
            easiness_factor=2.5,
            interval_days=1,
            repetitions=0,
        )
        assert next_date == date.today()

    # --- Full progression simulation ---
    def test_full_progression_good_three_times(self):
        """Simulate three consecutive 'good' reviews."""
        ef = 2.5
        interval = 1
        reps = 0

        # First good
        ef, interval, reps, _ = sm2_calculate(3, ef, interval, reps)
        assert interval == 1
        assert reps == 1

        # Second good
        ef, interval, reps, _ = sm2_calculate(3, ef, interval, reps)
        assert interval == 6
        assert reps == 2

        # Third good
        ef, interval, reps, _ = sm2_calculate(3, ef, interval, reps)
        assert interval == round(6 * ef)
        assert reps == 3

    def test_progression_then_reset(self):
        """Simulate good progression then 'again' reset."""
        ef = 2.5
        interval = 1
        reps = 0

        # Build up
        for _ in range(3):
            ef, interval, reps, _ = sm2_calculate(3, ef, interval, reps)

        assert interval > 1
        assert reps > 0

        # Reset with 'again'
        _, interval, reps, _ = sm2_calculate(1, ef, interval, reps)
        assert interval == 1
        assert reps == 0
