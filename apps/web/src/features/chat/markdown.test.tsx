import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithIntl } from "@/test/render";

import { MAX_DEPTH, MessageMarkdown, prepareSource, sourceNesting } from "./markdown";

const RAMIN = "0a6f3c1e-5b7d-4e2a-9c11-2f3e4d5a6b7c";

function render(body: string, mentions = [{ id: RAMIN, display_name: "Ramin Əliyev" }]) {
  return renderWithIntl(<MessageMarkdown body={body} mentions={mentions} currentUserId="me" />)
    .container;
}

/** No element or attribute that can run script survived. */
function expectInert(container: HTMLElement) {
  expect(
    container.querySelector("script, iframe, object, embed, svg, img, style, form"),
  ).toBeNull();
  for (const element of container.querySelectorAll("*")) {
    for (const attribute of element.attributes) {
      expect(attribute.name).not.toMatch(/^on/i);
      expect(attribute.value).not.toMatch(/^\s*(javascript|data|vbscript):/i);
    }
  }
}

describe("MessageMarkdown: XSS vectors (§13.2, §14)", () => {
  it.each([
    ["script tag", "<script>alert(1)</script>"],
    ["event handler", '<img src=x onerror="alert(1)">'],
    ["SVG payload", '<svg onload="alert(1)"><circle r="5"/></svg>'],
    ["iframe", '<iframe src="https://evil.example"></iframe>'],
    ["style tag", "<style>body{display:none}</style>"],
    ["HTML comment trick", "<!-- --><script>alert(1)</script>"],
    ["form", '<form action="https://evil.example"><button>Göndər</button></form>'],
  ])("shows raw HTML as text: %s", (_, payload) => {
    const container = render(payload);
    expectInert(container);
    expect(container.textContent).toContain(payload.replace(/^<!-- -->/, "").slice(0, 8));
  });

  it.each([
    ["javascript link", "[bax](javascript:alert(1))"],
    ["encoded javascript link", "[bax](jav&#x61;script:alert(1))"],
    ["data link", "[bax](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)"],
    ["vbscript link", "[bax](vbscript:msgbox(1))"],
    ["autolink", "<javascript:alert(1)>"],
  ])("drops unsafe link targets: %s", (_, payload) => {
    const container = render(payload);
    expectInert(container);
    for (const link of container.querySelectorAll("a")) {
      expect(link.getAttribute("href") ?? "").toMatch(/^(https?:|mailto:|$)/);
    }
  });

  it("never renders Markdown images (no tracking pixels)", () => {
    const container = render("![sxem](https://evil.example/pixel.png)");
    expect(container.querySelector("img")).toBeNull();
  });

  it("keeps KaTeX from producing links, classes or HTML", () => {
    const container = render(
      String.raw`$\href{javascript:alert(1)}{x}$ $\url{https://evil.example}$ $\htmlClass{x}{y}$ $\htmlStyle{color:red}{y}$`,
    );
    expectInert(container);
    expect(container.querySelector("a")).toBeNull();
  });

  it("shows huge nested input as plain text instead of building a deep tree", () => {
    const body = `${"> ".repeat(2000)}dərin`;
    const started = performance.now();
    const container = render(body);
    expect(performance.now() - started).toBeLessThan(5000);
    expect(container.querySelectorAll("blockquote")).toHaveLength(0);
    expect(container.textContent).toContain("dərin");
    expect(MAX_DEPTH).toBeLessThan(100);
    const lists = render(`${"- ".repeat(1500)}son`);
    expect(lists.querySelectorAll("li").length).toBeLessThan(MAX_DEPTH);
  });

  it("survives a macro bomb within KaTeX's limits", () => {
    const container = render(
      String.raw`$\def\a{\b\b}\def\b{\c\c}\def\c{\d\d}\def\d{\e\e}\def\e{\f\f}\def\f{xx}\a\a\a\a$`,
    );
    expectInert(container);
  });
});

describe("MessageMarkdown: formatting", () => {
  it("renders emphasis, lists, quotes and code in IBM Plex Mono", () => {
    const container = render(
      "**Diqqət:** _sabah_ ~~yox~~\n\n- birinci\n- ikinci\n\n> sitat\n\n```python\nprint('salam')\n```\n\nVə `x = 1`.",
    );
    expect(container.querySelector("strong")?.textContent).toBe("Diqqət:");
    expect(container.querySelector("em")?.textContent).toBe("sabah");
    expect(container.querySelector("del")?.textContent).toBe("yox");
    expect(container.querySelectorAll("li")).toHaveLength(2);
    expect(container.querySelector("blockquote")?.textContent).toContain("sitat");
    const block = container.querySelector("pre code");
    expect(block?.textContent).toBe("print('salam')\n");
    expect(block).toHaveClass("font-mono");
    expect(container.querySelector("p code")?.textContent).toBe("x = 1");
  });

  it("renders inline and display math with KaTeX", () => {
    const container = render("Düstur: $E = mc^2$\n\n$$\\int_0^1 x\\,dx = \\frac{1}{2}$$");
    expect(container.querySelectorAll(".katex").length).toBeGreaterThanOrEqual(2);
    expect(container.querySelector(".katex-display")).not.toBeNull();
    // Invalid TeX is shown, not thrown.
    const broken = render("$\\frac{1}{$");
    expect(broken.textContent).toContain("\\frac");
  });

  it("marks external links and opens them safely", () => {
    const container = render("Bax: https://azmiu.edu.az/cedvel və [daxili](/schedule)");
    const external = screen.getAllByRole("link")[0]!;
    expect(external).toHaveAttribute("href", "https://azmiu.edu.az/cedvel");
    expect(external).toHaveAttribute("target", "_blank");
    expect(external).toHaveAttribute("rel", "noopener noreferrer nofollow");
    expect(external).toHaveTextContent("xarici keçid");
    const internal = container.querySelector('a[href="/schedule"]');
    expect(internal).not.toHaveAttribute("target");
  });

  it("names member mentions and hides other ids, also never inside code", () => {
    const stranger = "1b2c3d4e-5f60-4718-9a0b-c1d2e3f40516";
    const container = render(`<@${RAMIN}> və <@${stranger}>, \`<@${RAMIN}>\``);
    expect(container.textContent).toContain("@Ramin Əliyev");
    expect(container.textContent).toContain("@istifadəçi");
    expect(container.textContent).not.toContain(stranger);
    expect(container.querySelector("code")?.textContent).toBe(`<@${RAMIN}>`);
  });
});

describe("source checks", () => {
  it("measures container nesting and fences single-line display math", () => {
    expect(sourceNesting("> > - 1. bənd\nadi sətir")).toBe(4);
    expect(sourceNesting("-1 dərəcə, 3.5 bal")).toBe(0);
    expect(prepareSource("Düstur:\n$$a^2+b^2=c^2$$\nson")).toBe(
      "Düstur:\n$$\na^2+b^2=c^2\n$$\nson",
    );
    expect(prepareSource("Mətn içində $$x$$ qalır")).toBe("Mətn içində $$x$$ qalır");
  });
});
