import '@testing-library/jest-dom';
import React from 'react';
import { vi } from 'vitest';

process.env.NEXT_PUBLIC_API_URL = '';

vi.mock('@/lib/supabase', () => ({
  getSupabase: vi.fn(() => ({
    auth: {
      getSession: vi.fn(() => Promise.resolve({ data: { session: null }, error: null })),
      onAuthStateChange: vi.fn(() => ({
        data: { subscription: { unsubscribe: vi.fn() } },
      })),
    },
  })),
  getAuthToken: vi.fn(() => Promise.resolve(null)),
}));
