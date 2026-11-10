# YouTube transport-state regression

Reproduced in the Themed.AI desktop embed on 2026-10-25: Play All advanced elapsed time but the transport remained Play full track; clicking it did not pause. Next-track and navigation persistence worked.

MusicPlayer consumed infoDelivery.currentTime but only consumed playback state from onStateChange. It now consumes playerState from infoDelivery and initialDelivery too, deduplicates state transitions, explicitly subscribes to state/error events, and accepts messages only from the active YouTube iframe. Error and track-reset paths stop the old elapsed timer.

Validation:
- npm test: 5 passed, including the actual React player sending pauseVideo/playVideo and publishing corresponding desktop host state.
- The component test fails against the original MusicPlayer.jsx with no Pause button found.
- npm run build: passed.
- ESLint passed for the new message helper and test files.
- Test renderer emits its upstream deprecation warning; the Node JSX loader emits its experimental-loader warning.

This fix has not been deployed. Real YouTube/WebView2 playback and audible output must be rechecked after deployment; message-driven tests do not establish that acceptance.
