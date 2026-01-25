# HEAT Watch — watchOS Companion

A minimal SwiftUI watchOS app scaffold to display HEAT statewide signals and cluster summaries on Apple Watch. It fetches tiered JSON (public/contributor) from the deployed CDN (CloudFront/S3) and presents:

- Statewide intensity gauge
- Latest 3 clusters (summary + ZIP)
- Simple timeline sparkline

## Data Source

Configure `HeatService.baseUrl` to your deployed origin, e.g.:

```
https://<your-cloudfront-domain>/exports/
```

Expected files:
- `tier0_public.json` (public)
- `tier1_contributor.json` (if authenticated)

## Building

1. Open the folder in Xcode (File → Open...).
2. Create a new watchOS App target and add these source files.
3. Set `HEATWatchApp` as the app entry point.
4. Run on a watchOS simulator (Series 9 recommended).

## Notes

- This is a starter scaffold; integrate auth if you plan Tier 1/2 access.
- Ensure CORS is enabled on the S3 bucket so the CDN serves JSON with appropriate headers.
- The app reads lightweight summaries — no real-time data. It respects the 24h/72h delays.
