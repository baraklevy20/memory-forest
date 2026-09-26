/* The add-on's browser code: plain scripts in Anki's webview, no bundler, no modules.
 * `npm install && npm run lint` from this folder. */
export default [
  {
    files: ['web/**/*.js', 'dev/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'script',
      globals: {
        window: 'readonly', document: 'readonly', console: 'readonly',
        performance: 'readonly', requestAnimationFrame: 'readonly',
        requestIdleCallback: 'readonly', setTimeout: 'readonly', clearTimeout: 'readonly',
        matchMedia: 'readonly', IntersectionObserver: 'readonly', ResizeObserver: 'readonly',
        MouseEvent: 'readonly', Image: 'readonly', Float32Array: 'readonly',
        Uint8Array: 'readonly', Int8Array: 'readonly', Uint8ClampedArray: 'readonly',
        pycmd: 'readonly',  // Anki's bridge: a bare global, not a window property
      },
    },
    linterOptions: { reportUnusedDisableDirectives: true },
    rules: {
      'no-unused-vars': ['error', { args: 'after-used', argsIgnorePattern: '^_' }],
      'no-undef': 'error',
      'no-implicit-globals': 'error',
      'no-var': 'error',
      'prefer-const': 'error',
      'eqeqeq': ['error', 'smart'],
      'no-console': ['warn', { allow: ['error', 'warn'] }],
      'no-unused-expressions': 'error',
      'no-shadow-restricted-names': 'error',
      'no-fallthrough': 'error',
      'no-constant-condition': ['error', { checkLoops: false }],
    },
  },
];
