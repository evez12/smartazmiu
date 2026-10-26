"use client";

import "katex/dist/katex.min.css";

import type { Element, ElementContent, Root, RootContent, Text } from "hast";
import type { Nodes as MdastNodes, Root as MdastRoot } from "mdast";
import { ExternalLink } from "lucide-react";
import { useTranslations } from "next-intl";
import { memo, type ComponentProps, type ReactNode } from "react";
import Markdown, { type Components } from "react-markdown";
import rehypeKatex from "rehype-katex";
import rehypeSanitize, { type Options as SanitizeSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/cn";

import type { Mention } from "./model";

/**
 * Chat Markdown (§5.3, §13.2, §14, D-069). The raw text is stored; the browser parses it into a syntax tree (raw
 * HTML becomes literal text), keeps only the elements below, and only then lets KaTeX turn the math nodes into its
 * own markup. React renders the tree as elements: nothing reaches `innerHTML`.
 */
export const SANITIZE_SCHEMA: SanitizeSchema = {
  tagNames: [
    "p",
    "br",
    "strong",
    "em",
    "del",
    "code",
    "pre",
    "blockquote",
    "ul",
    "ol",
    "li",
    "a",
    "hr",
  ],
  attributes: {
    a: ["href"],
    // remark-math marks math as code with these classes; rehype-katex looks for them after sanitising.
    code: [["className", /^language-[\w+-]{1,30}$/, "math-inline", "math-display"]],
    ol: [["start", /^\d{1,6}$/]],
  },
  protocols: { href: ["http", "https", "mailto"] },
  // Removed with their content; anything else not listed is replaced by its text.
  strip: ["script", "style", "svg", "math", "iframe", "object", "embed", "template"],
  clobberPrefix: "",
  required: {},
};

// Deeper trees (thousands of nested quotes or lists) are shown as plain text: rendering them would only hurt.
export const MAX_DEPTH = 40;

const KATEX_OPTIONS = {
  throwOnError: false,
  errorColor: "var(--danger)",
  strict: "ignore",
  // No \href, \url, \htmlClass or similar: KaTeX output stays plain math.
  trust: false,
  maxSize: 20,
  maxExpand: 200,
  output: "htmlAndMathml",
} as const;

// Container markers at the start of a line: quotes, bullets and numbered items.
const CONTAINER_MARKERS = /^(?:\s*(?:>|[*+-](?=\s)|\d{1,9}[.)](?=\s)))+/;
// A line that is only `$$…$$` is display math, as on paper; remark-math wants the fences on their own lines.
const DISPLAY_MATH_LINE = /^(\s*)\$\$([^\n$]+)\$\$\s*$/gm;

/**
 * How deeply the source nests containers. Checked before parsing: the parser and the tree transforms recurse,
 * and a 4,000-character message of ">" could otherwise exhaust the stack.
 */
export function sourceNesting(body: string): number {
  let deepest = 0;
  for (const line of body.split("\n")) {
    const markers = CONTAINER_MARKERS.exec(line)?.[0] ?? "";
    deepest = Math.max(deepest, markers.replace(/\s/g, "").replace(/\d+[.)]/g, "1").length);
  }
  return deepest;
}

export function prepareSource(body: string): string {
  return body.replace(DISPLAY_MATH_LINE, "$1$$$$\n$1$2\n$1$$$$");
}

const MENTION_TOKEN = /<@([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})>/gi;

function depth(node: Root | ElementContent | RootContent): number {
  if (!("children" in node) || node.children.length === 0) return 1;
  let deepest = 0;
  for (const child of node.children) deepest = Math.max(deepest, depth(child));
  return deepest + 1;
}

/** Replaces an overly nested tree with one paragraph of the raw text. */
function limitDepth(raw: string) {
  return () => (tree: Root) => {
    if (depth(tree) <= MAX_DEPTH) return;
    tree.children = [
      { type: "element", tagName: "p", properties: {}, children: [{ type: "text", value: raw }] },
    ];
  };
}

/**
 * `<@user-id>` tokens outside code become `mention` elements (rendered by the component below). Runs after
 * sanitising, so the element is never something a message could produce on its own.
 */
function mentions() {
  return () => (tree: Root) => {
    const visit = (parent: Root | Element) => {
      const next: (RootContent | ElementContent)[] = [];
      for (const child of parent.children) {
        if (child.type === "element") {
          if (child.tagName !== "code" && child.tagName !== "pre") visit(child);
          next.push(child);
          continue;
        }
        if (child.type !== "text" || !child.value.includes("<@")) {
          next.push(child);
          continue;
        }
        let last = 0;
        for (const match of child.value.matchAll(MENTION_TOKEN)) {
          if (match.index > last) next.push(text(child.value.slice(last, match.index)));
          next.push({
            type: "element",
            tagName: "mention",
            properties: { userId: match[1]!.toLowerCase() },
            children: [],
          });
          last = match.index + match[0].length;
        }
        if (last < child.value.length) next.push(text(child.value.slice(last)));
      }
      parent.children = next as typeof parent.children;
    };
    visit(tree);
  };
}

/** Raw HTML in a message is shown as the characters typed, never parsed (§13.2). */
function htmlAsText() {
  return (tree: MdastRoot) => {
    const visit = (node: MdastNodes) => {
      // An html node and a text node both carry the source in `value`; only the type changes.
      if (node.type === "html") Object.assign(node, { type: "text" });
      if ("children" in node) for (const child of node.children) visit(child);
    };
    visit(tree);
  };
}

function text(value: string): Text {
  return { type: "text", value };
}

function isExternal(href: string): boolean {
  if (!/^https?:\/\//i.test(href)) return false;
  try {
    return new URL(href).host !== globalThis.location?.host;
  } catch {
    return true;
  }
}

function SafeLink({ href = "", children }: ComponentProps<"a">) {
  const t = useTranslations("chat");
  if (!isExternal(href)) {
    return (
      <a href={href} className="text-primary underline underline-offset-2">
        {children}
      </a>
    );
  }
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer nofollow"
      className="inline-flex items-baseline gap-0.5 text-primary underline underline-offset-2"
    >
      {children}
      <Icon icon={ExternalLink} className="size-3 self-center" />
      <span className="sr-only">{t("externalLink")}</span>
    </a>
  );
}

type MarkdownProps = {
  body: string;
  mentions: Mention[];
  currentUserId: string;
  className?: string;
  /** Inline after the last paragraph, e.g. the "redaktə olunub" label. */
  suffix?: ReactNode;
};

function MessageMarkdownImpl({
  body,
  mentions: named,
  currentUserId,
  className,
  suffix,
}: MarkdownProps) {
  const t = useTranslations("chat");
  const names = new Map(named.map((mention) => [mention.id.toLowerCase(), mention.display_name]));
  const components: Components = {
    a: SafeLink,
    p: ({ children }) => <p className="break-words whitespace-pre-wrap">{children}</p>,
    pre: ({ children }) => (
      <pre className="my-1 max-w-full overflow-x-auto rounded-control border border-border bg-bg-subtle px-3 py-2 font-mono text-sm">
        {children}
      </pre>
    ),
    code: ({ className: language, children }) => (
      <code
        className={cn(
          "font-mono text-sm",
          // Inline code gets a frame; inside <pre> the block has one already.
          !language && "rounded-control bg-bg-subtle px-1 [pre_&]:bg-transparent [pre_&]:p-0",
        )}
      >
        {children}
      </code>
    ),
    blockquote: ({ children }) => (
      <blockquote className="my-1 border-l-2 border-border pl-3 text-muted">{children}</blockquote>
    ),
    ul: ({ children }) => <ul className="my-1 list-disc pl-5">{children}</ul>,
    ol: ({ children, start }) => (
      <ol start={start} className="my-1 list-decimal pl-5">
        {children}
      </ol>
    ),
    hr: () => <hr className="my-2 border-border" />,
  };
  // Custom element produced by the mentions plugin; react-markdown passes unknown tags through `components`.
  (components as Record<string, unknown>).mention = ({ userId }: { userId: string }) => {
    const name = names.get(userId);
    if (name === undefined) return <span>{t("mentionUnknown")}</span>;
    return (
      <span
        className={cn(
          "rounded-control px-0.5 font-medium text-primary",
          userId === currentUserId && "bg-bg-subtle",
        )}
      >
        @{name}
      </span>
    );
  };
  if (sourceNesting(body) > MAX_DEPTH) {
    return (
      <div className={cn("min-w-0 [&>p:last-child]:inline", className)}>
        <p className="break-words whitespace-pre-wrap">{body}</p>
        {suffix}
      </div>
    );
  }
  return (
    <div className={cn("min-w-0 [&>*:last-child]:mb-0 [&>p:last-child]:inline", className)}>
      <Markdown
        remarkPlugins={[htmlAsText, remarkGfm, [remarkMath, { singleDollarTextMath: true }]]}
        rehypePlugins={[
          limitDepth(body),
          [rehypeSanitize, SANITIZE_SCHEMA],
          [rehypeKatex, KATEX_OPTIONS],
          mentions(),
        ]}
        components={components}
      >
        {prepareSource(body)}
      </Markdown>
      {suffix}
    </div>
  );
}

/** Messages re-render often (typing, presence); the parse only reruns when the text or names change. */
export const MessageMarkdown = memo(MessageMarkdownImpl);
