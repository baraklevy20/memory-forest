/* The add-on's browser code: plain scripts in Anki's webview, no bundler, no modules; and
 * the node tooling (dev/*.mjs, e2e/*.mjs): ES modules that drive headless Chrome.
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
        MouseEvent: 'readonly', Image: 'readonly', Path2D: 'readonly', Float32Array: 'readonly',
        Uint8Array: 'readonly', Int8Array: 'readonly', Uint8ClampedArray: 'readonly', ImageData: 'readonly',
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
  {
    // the node tooling: its output is console.log, and what it runs in the page
    // (page.evaluate) sees the browser's globals and window.AnkiForest; and the JS unit tests
    // (tests/js), which run web/'s scripts in node
    files: ['dev/**/*.mjs', 'e2e/**/*.mjs', 'tests/**/*.mjs'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        process: 'readonly', console: 'readonly', URL: 'readonly', Buffer: 'readonly',
        setTimeout: 'readonly', clearTimeout: 'readonly', setInterval: 'readonly', clearInterval: 'readonly',
        performance: 'readonly',
        window: 'readonly', document: 'readonly', requestAnimationFrame: 'readonly', getComputedStyle: 'readonly',
        innerWidth: 'readonly', innerHeight: 'readonly', MouseEvent: 'readonly', KeyboardEvent: 'readonly',
        HTMLCanvasElement: 'readonly', CanvasRenderingContext2D: 'readonly',
        AnkiForest: 'readonly', WheelEvent: 'readonly', Event: 'readonly',
        Uint8ClampedArray: 'readonly', T: 'readonly',
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
      'no-unused-expressions': 'error',
      'no-shadow-restricted-names': 'error',
      'no-fallthrough': 'error',
      'no-constant-condition': ['error', { checkLoops: false }],
    },
  },
];
