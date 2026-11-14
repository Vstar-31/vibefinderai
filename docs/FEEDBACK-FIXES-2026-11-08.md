# VibeFinder feedback fixes, 8 November 2026

The legacy /app route mounted three desktop bridge listeners. App and ThemedAIHostBridge could both execute playback commands; AppWithThemedAI additionally changed/focused the prompt and clicked Run Analysis. DOM polling and a mutation observer repeatedly published scraped playback/results. App now owns commands/results, MusicPlayer owns playback snapshots, and the auxiliary bridge only forwards personalization.

The signed-in prompt stays editable during a running analysis. Typed prompts survive host reconnect/default messages. Explicit native Save & Apply uses force=true to replace them. Background host analyses are ignored while the user owns the edited prompt.

YouTube track selection awaits in-flight prefetches, authenticates lookups, does not cache transient errors as permanent misses, and can retry on Play. Old prefetch timers are cancelled. Preview audio stops on tracks without a preview and is recreated when switching providers.

Playlists/history load independently with timeouts, clear session/network/status errors, retries and stale-request cancellation. Failed deletes no longer disappear locally. Recent-search failures remain visible. Saved-playlist Load and history Re-run now have callbacks connected to the main app.

Validation: 12 frontend tests pass in the release branch, including prefetch/selection races, failed lookup retry, audio provider switches, reconnect prompt protection, independent library loading and stale-account responses. Production build passes. Focused lint passes for new hooks/tests and the simplified bridge. No full-repository lint-clean claim.

GUI evidence uses the deployed frontend, not this unpublished bundle: authenticated library initially failed, then rendered saved playlists and 30 history entries after isolated desktop restart. Native diagnostics recorded HTTP 200 for /api/playlist/list, /api/user/history and /api/vibe/history. Anonymous requests returned HTTP 401. The original transient failure's cause remains unproven.

The release branch applies the frontend feedback changes to the production Themed.AI branch at 9e28247. It uses the deployed backend's existing library and media routes. OAuth and database changes have their own pull requests.
