/**
 * Unit tests for the SM-2 spaced repetition library.
 */
import { describe, it, expect } from 'vitest';
import { sm2, type Rating } from '@/lib/sm2';

describe('sm2()', () => {
  describe('quality=good (3) progression', () => {
    it('first good review: interval=1, reps=1', () => {
      const result = sm2('good', {
        easinessFactor: 2.5,
        intervalDays: 1,
        repetitions: 0,
      });
      expect(result.newIntervalDays).toBe(1);
      expect(result.newRepetitions).toBe(1);
    });

    it('second good review: interval=6, reps=2', () => {
      const result = sm2('good', {
        easinessFactor: 2.5,
        intervalDays: 1,
        repetitions: 1,
      });
      expect(result.newIntervalDays).toBe(6);
      expect(result.newRepetitions).toBe(2);
    });

    it('third good review: interval grows by EF', () => {
      const result = sm2('good', {
        easinessFactor: 2.5,
        intervalDays: 6,
        repetitions: 2,
      });
      // EF updated first: 2.5 + (0.1 - 2*(0.08+2*0.02)) = 2.5 + (0.1 - 0.24) = 2.36
      // interval = round(6 * 2.36) = round(14.16) = 14
      expect(result.newIntervalDays).toBe(14);
      expect(result.newRepetitions).toBe(3);
    });
  });

  describe('quality=easy (5)', () => {
    it('increases easiness factor', () => {
      const result = sm2('easy', {
        easinessFactor: 2.5,
        intervalDays: 1,
        repetitions: 0,
      });
      expect(result.newEasinessFactor).toBeGreaterThan(2.5);
    });

    it('grows interval faster than good', () => {
      const goodResult = sm2('good', {
        easinessFactor: 2.5,
        intervalDays: 6,
        repetitions: 2,
      });
      const easyResult = sm2('easy', {
        easinessFactor: 2.5,
        intervalDays: 6,
        repetitions: 2,
      });
      expect(easyResult.newIntervalDays).toBeGreaterThan(goodResult.newIntervalDays);
    });
  });

  describe('quality=again (1)', () => {
    it('resets interval to 1', () => {
      const result = sm2('again', {
        easinessFactor: 2.5,
        intervalDays: 15,
        repetitions: 3,
      });
      expect(result.newIntervalDays).toBe(1);
      expect(result.newRepetitions).toBe(0);
    });

    it('sets next review to today (no future date)', () => {
      const result = sm2('again', {
        easinessFactor: 2.5,
        intervalDays: 15,
        repetitions: 3,
      });
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      expect(result.nextReviewDate.toDateString()).toBe(today.toDateString());
    });
  });

  describe('quality=hard (2)', () => {
    it('decreases easiness factor', () => {
      const result = sm2('hard', {
        easinessFactor: 2.5,
        intervalDays: 1,
        repetitions: 0,
      });
      expect(result.newEasinessFactor).toBeLessThan(2.5);
    });

    it('resets interval to 1', () => {
      const result = sm2('hard', {
        easinessFactor: 2.5,
        intervalDays: 15,
        repetitions: 3,
      });
      expect(result.newIntervalDays).toBe(1);
      expect(result.newRepetitions).toBe(0);
    });
  });

  describe('easiness factor bounds', () => {
    it('minimum EF is 1.3', () => {
      // Quality 0 should approach minimum EF
      let ef = 2.5;
      for (let i = 0; i < 10; i++) {
        const result = sm2('again', {
          easinessFactor: ef,
          intervalDays: 1,
          repetitions: 0,
        });
        ef = result.newEasinessFactor;
      }
      expect(ef).toBe(1.3);
    });

    it('stays at 1.3 when already at minimum', () => {
      const result = sm2('again', {
        easinessFactor: 1.3,
        intervalDays: 1,
        repetitions: 0,
      });
      expect(result.newEasinessFactor).toBe(1.3);
    });
  });

  describe('full progression', () => {
    it('three consecutive good reviews grow interval', () => {
      let params = {
        easinessFactor: 2.5,
        intervalDays: 1,
        repetitions: 0,
      };

      // First good
      let result = sm2('good', params);
      expect(result.newIntervalDays).toBe(1);
      expect(result.newRepetitions).toBe(1);

      // Second good
      params = {
        ...params,
        intervalDays: result.newIntervalDays,
        easinessFactor: result.newEasinessFactor,
        repetitions: result.newRepetitions,
      };
      result = sm2('good', params);
      expect(result.newIntervalDays).toBe(6);
      expect(result.newRepetitions).toBe(2);

      // Third good - EF decreases with each review
      // EF after 2 good: 2.5 -> 2.36 -> 2.22
      // interval = round(6 * 2.22) = 13
      params = {
        ...params,
        intervalDays: result.newIntervalDays,
        easinessFactor: result.newEasinessFactor,
        repetitions: result.newRepetitions,
      };
      result = sm2('good', params);
      expect(result.newRepetitions).toBe(3);
      // Interval should be > 6 and reasonable
      expect(result.newIntervalDays).toBeGreaterThan(6);
      expect(result.newIntervalDays).toBeLessThan(20);
    });

    it("reset after 'again' clears progression", () => {
      let params = {
        easinessFactor: 2.5,
        intervalDays: 1,
        repetitions: 0,
      };

      // Build up
      for (let i = 0; i < 3; i++) {
        const result = sm2('good', params);
        params = {
          easinessFactor: result.newEasinessFactor,
          intervalDays: result.newIntervalDays,
          repetitions: result.newRepetitions,
        };
      }

      expect(params.intervalDays).toBeGreaterThan(1);
      expect(params.repetitions).toBeGreaterThan(0);

      // Reset with 'again'
      const reset = sm2('again', params);
      expect(reset.newIntervalDays).toBe(1);
      expect(reset.newRepetitions).toBe(0);
    });
  });
});

describe('Rating types', () => {
  it('can be used with all rating types', () => {
    const params = {
      easinessFactor: 2.5,
      intervalDays: 1,
      repetitions: 0,
    };

    const ratings: Rating[] = ['again', 'hard', 'good', 'easy'];

    for (const rating of ratings) {
      expect(() => sm2(rating, params)).not.toThrow();
    }
  });
});
