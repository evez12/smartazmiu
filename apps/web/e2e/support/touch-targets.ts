import type { Page } from "@playwright/test";

/*
 * Touch targets on a phone (§12.6, CLAUDE.md: ≥ 44 px). A control passes when its own box or the tap area it adds
 * (`touchTarget`, an ::after box that exists only for coarse pointers) is at least 44 px in both directions. Exempt:
 * the skip link (off screen until focused), the hidden inputs behind Radix checkboxes, and links inside a sentence
 * (WCAG 2.5.8), which are recognised by the text around them.
 */
const MIN = 44;

export async function undersizedTargets(page: Page): Promise<string[]> {
  return page.evaluate((min) => {
    const selector =
      "a[href],button,input:not([type=hidden]),select,textarea,summary,[role=tab],[role=menuitem],[role=switch]";
    return Array.from(document.querySelectorAll<HTMLElement>(selector)).flatMap((el) => {
      const box = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      if (box.width < 2 || box.height < 2 || style.visibility === "hidden") return [];
      if (
        el.matches('a[href="#main"],[aria-hidden="true"],[tabindex="-1"]:not(button,a,summary)')
      ) {
        return [];
      }
      const sentence =
        el.tagName === "A" &&
        style.display === "inline" &&
        (el.parentElement?.textContent ?? "").trim().length >
          (el.textContent ?? "").trim().length + 10;
      if (sentence) return [];
      let width = box.width;
      let height = box.height;
      const after = getComputedStyle(el, "::after");
      if (after.content !== "none" && after.display !== "none" && after.position === "absolute") {
        width = Math.max(width, parseFloat(after.width) || 0);
        height = Math.max(height, parseFloat(after.height) || 0);
      }
      if (width >= min - 0.5 && height >= min - 0.5) return [];
      const name = (el.getAttribute("aria-label") ?? el.textContent ?? "").trim().slice(0, 40);
      return [`${el.tagName.toLowerCase()} "${name}" ${Math.round(width)}×${Math.round(height)}`];
    });
  }, MIN);
}
