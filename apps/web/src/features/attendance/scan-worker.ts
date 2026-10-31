import jsQR from "jsqr";

export type ScanFrame = { data: Uint8ClampedArray<ArrayBuffer>; width: number; height: number };
export type ScanResult = { text: string | null };

/*
 * Decodes camera frames away from the main thread, for browsers without a native BarcodeDetector (D-095).
 * The worker is a same-origin script, so the Content-Security-Policy needs no relaxation.
 */
self.onmessage = (event: MessageEvent<ScanFrame>) => {
  const { data, width, height } = event.data;
  const found = jsQR(data, width, height, { inversionAttempts: "dontInvert" });
  const result: ScanResult = { text: found?.data ?? null };
  self.postMessage(result);
};
