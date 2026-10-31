import type { ScanFrame, ScanResult } from "./scan-worker";

type Detector = { detect(source: CanvasImageSource): Promise<{ rawValue: string }[]> };
type DetectorConstructor = new (options: { formats: string[] }) => Detector;

const FRAME_INTERVAL_MS = 250;
/** Frames are scaled down: a code that fills the screen decodes fine at this width, and the work stays small. */
const FRAME_WIDTH = 480;

/**
 * Reads QR codes from a playing video until the returned function is called. The browser's own BarcodeDetector is
 * used when it exists; otherwise frames go to a worker running jsQR (D-095).
 */
export function startScanning(video: HTMLVideoElement, onCode: (text: string) => void): () => void {
  const Native = (window as unknown as { BarcodeDetector?: DetectorConstructor }).BarcodeDetector;
  const detector = Native ? new Native({ formats: ["qr_code"] }) : null;
  const worker = detector ? null : new Worker(new URL("./scan-worker.ts", import.meta.url));
  const canvas = document.createElement("canvas");
  let stopped = false;
  let busy = false;
  let timer = 0;

  if (worker) {
    worker.onmessage = (event: MessageEvent<ScanResult>) => {
      busy = false;
      if (event.data.text) onCode(event.data.text);
    };
  }

  const tick = async () => {
    if (stopped) return;
    if (video.readyState >= 2 && video.videoWidth > 0 && !busy) {
      try {
        if (detector) {
          const [found] = await detector.detect(video);
          if (found?.rawValue) onCode(found.rawValue);
        } else if (worker) {
          canvas.width = FRAME_WIDTH;
          canvas.height = Math.round((FRAME_WIDTH * video.videoHeight) / video.videoWidth);
          const context = canvas.getContext("2d", { willReadFrequently: true });
          if (context) {
            context.drawImage(video, 0, 0, canvas.width, canvas.height);
            const frame = context.getImageData(0, 0, canvas.width, canvas.height);
            busy = true;
            const message: ScanFrame = {
              data: frame.data as Uint8ClampedArray<ArrayBuffer>,
              width: frame.width,
              height: frame.height,
            };
            worker.postMessage(message, [message.data.buffer]);
          }
        }
      } catch {
        // A frame that cannot be read is skipped; the next one may be fine.
        busy = false;
      }
    }
    if (!stopped) timer = window.setTimeout(() => void tick(), FRAME_INTERVAL_MS);
  };
  void tick();

  return () => {
    stopped = true;
    window.clearTimeout(timer);
    worker?.terminate();
  };
}
