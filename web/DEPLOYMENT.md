# Automataii Web deployment

The web app is static. Build once and publish `web/dist/` to any static host.

## Fast path with Bun

```bash
cd web
bun install --frozen-lockfile
bun run check:bun
```

`bun run check:bun` runs lint, unit/static tests, HTTP smoke, real browser smoke, and build.

## NPM fallback

```bash
cd web
npm ci
npm run check
```

## Local preview

```bash
cd web
bun run dev:bun   # or npm run dev
```

Open <http://127.0.0.1:5173>.

## Static hosts

Use:

- build command: `bun install --frozen-lockfile && bun run build`
- publish directory: `web/dist` from repo root, or `dist` when the host base directory is `web`

No backend, database, private key, or server runtime is required after build.
