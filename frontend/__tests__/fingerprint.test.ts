/**
 * Pure-helper tests for the fingerprint type utilities.
 *
 * These pin the bucket translation and the CSS-variable lookups so a
 * future tweak to the colour scheme doesn't accidentally mislabel a
 * red trace as yellow.
 */
import { describe, it, expect } from 'vitest';
import {
  complexityBucket,
  complexityColor,
  complexityBorderColor,
} from '@/types/fingerprint';

describe('complexityBucket', () => {
  it('classifies 🔴 as red', () => {
    expect(complexityBucket('🔴')).toBe('red');
  });

  it('classifies 🟡 as yellow', () => {
    expect(complexityBucket('🟡')).toBe('yellow');
  });

  it('classifies 🟢 as green', () => {
    expect(complexityBucket('🟢')).toBe('green');
  });

  it('falls back to green for any unknown emoji', () => {
    expect(complexityBucket('?')).toBe('green');
    expect(complexityBucket('')).toBe('green');
  });
});

describe('complexityColor / complexityBorderColor', () => {
  it('uses CSS variables (not hardcoded hex) so theming flows through', () => {
    // We don't pin exact hex — the contract is "this is a CSS var string".
    for (const bucket of ['red', 'yellow', 'green'] as const) {
      const fakeFp = { conceptual_complexity: bucket === 'red' ? '🔴' : bucket === 'yellow' ? '🟡' : '🟢' };
      const bg = complexityColor(fakeFp.conceptual_complexity);
      const border = complexityBorderColor(fakeFp.conceptual_complexity);
      expect(bg).toMatch(/^var\(--/);
      expect(border).toMatch(/^var\(--/);
    }
  });

  it('red bucket gets red-flavoured vars', () => {
    expect(complexityColor('🔴')).toMatch(/danger/);
    expect(complexityBorderColor('🔴')).toMatch(/danger/);
  });

  it('yellow bucket gets warning-flavoured vars', () => {
    expect(complexityColor('🟡')).toMatch(/warning/);
    expect(complexityBorderColor('🟡')).toMatch(/warning/);
  });

  it('green bucket gets success-flavoured vars', () => {
    expect(complexityColor('🟢')).toMatch(/success/);
    expect(complexityBorderColor('🟢')).toMatch(/success/);
  });
});
