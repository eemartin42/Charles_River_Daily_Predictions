# Frontend

## Install and run

```bash
npm install
npm run dev
```

Set API origin **before** `npm run build` or `npm run dev` (Next.js inlines `NEXT_PUBLIC_*`):

```bash
export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
export NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=your_maps_javascript_key
```

For production, use your **deployed** API URL, e.g. `https://your-api.example.com`, and configure the same value in your host’s environment variables.

The **river map** uses the Google Maps JavaScript API. Create a key with that API enabled; restrict by HTTP referrer (`localhost` + your production domain).

The UI sends `map_rate` to `/predictions` so segment colors and `hourly[].segments` match the selected stroke rate; the table still shows all rates.

