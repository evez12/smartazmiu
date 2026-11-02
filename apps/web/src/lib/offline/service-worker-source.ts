const PLACEHOLDER = '"__BUILD_ID__"';

/** The worker script for one build: the shared source with the build id written in (`public/sw-core.js`). */
export function renderServiceWorker(source: string, buildId: string): string {
  if (!source.includes(PLACEHOLDER))
    throw new Error("The service worker source has no build id slot");
  return source.replace(PLACEHOLDER, JSON.stringify(buildId));
}
