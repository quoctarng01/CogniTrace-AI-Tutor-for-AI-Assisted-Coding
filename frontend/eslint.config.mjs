import eslintConfigPrettier from 'eslint-config-prettier';
import eslint from '@eslint/js';
import tseslint from 'typescript-eslint';
import next from 'eslint-config-next';

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  next,
  {
    ignores: ['.next/', 'node_modules/', 'out/', 'dist/', 'build/'],
  },
  eslintConfigPrettier
);
