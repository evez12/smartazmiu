"use client";

import { Paperclip, SendHorizontal } from "lucide-react";
import { useTranslations } from "next-intl";
import {
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/cn";

import { AttachmentChips } from "./attachment-chips";
import { COUNTER_FROM, encodeMentions, MAX_BODY, type Author } from "./model";
import { ACCEPTED_FILES, MAX_ATTACHMENTS, type Upload } from "./uploads";
import { useUploads } from "./use-uploads";

const MAX_HEIGHT_PX = 160;
const MAX_SUGGESTIONS = 6;
// "@" at the start or after a space, then up to 30 letters, digits or spaces before the caret.
const MENTION_QUERY = /(?:^|\s)@([\p{L}\p{N} .'-]{0,30})$/u;
const collator = new Intl.Collator("az", { sensitivity: "base" });

/** Grows with its lines up to 160 px, then scrolls; the width stays the row's. */
function grow(element: HTMLTextAreaElement) {
  element.style.height = "auto";
  element.style.height = `${Math.min(element.scrollHeight + 2, MAX_HEIGHT_PX)}px`;
}

function startsWithAny(name: string, query: string): boolean {
  if (!query) return true;
  const words = [name, ...name.split(/\s+/)];
  return words.some((word) => collator.compare(word.slice(0, query.length), query) === 0);
}

type ComposerProps = {
  label: string;
  placeholder?: string;
  disabled: boolean;
  /** Receives the text with picked people encoded as `<@id>` mentions, and the uploaded attachments. */
  onSend: (body: string, attachmentIds: string[]) => void;
  /** The channel files are uploaded to; without it the composer has no attach button (edit mode). */
  attachTo?: string;
  onTyping?: () => void;
  /** Channel members for the "@" suggestions; the server records only members anyway (§13.2). */
  members?: Author[];
  currentUserId?: string;
  initialText?: string;
  initialPicked?: ReadonlyMap<string, string>;
  submitLabel?: string;
  /** Edit mode: Escape and the cancel button call this. */
  onCancel?: () => void;
  footer?: ReactNode;
};

/**
 * Multi-line composer: Enter sends, Shift+Enter starts a new line, a counter near the limit (§12.7). Typing "@"
 * suggests channel members; the picked person appears as "@Name" and is sent as a mention token.
 */
export function Composer({
  label,
  placeholder,
  disabled,
  onSend,
  onTyping,
  members = [],
  currentUserId,
  initialText = "",
  initialPicked,
  submitLabel,
  onCancel,
  footer,
  attachTo,
}: ComposerProps) {
  const t = useTranslations("chat");
  const [body, setBody] = useState(initialText);
  const [picked, setPicked] = useState(() => new Map(initialPicked ?? []));
  const [query, setQuery] = useState<string | null>(null);
  const [highlighted, setHighlighted] = useState(0);
  const field = useRef<HTMLTextAreaElement>(null);
  const caret = useRef<number | null>(null);
  const baseId = useId();
  const hintId = `${baseId}-hint`;
  const counterId = `${baseId}-counter`;
  const listId = `${baseId}-mentions`;
  const uploads = useUploads(attachTo);
  const files = useRef<HTMLInputElement>(null);
  const length = body.length;
  const tooLong = length > MAX_BODY;
  const ready = uploads.items.filter((item: Upload) => item.state === "ready");
  const uploading = uploads.items.some((item: Upload) => item.state === "uploading");
  const empty = body.trim().length === 0 && ready.length === 0;
  const editing = onCancel !== undefined;
  const blocked = disabled || empty || tooLong || uploading;

  const suggestions = useMemo(
    () =>
      query === null
        ? []
        : members
            .filter(
              (member) =>
                member.id !== currentUserId && startsWithAny(member.display_name, query.trim()),
            )
            .slice(0, MAX_SUGGESTIONS),
    [currentUserId, members, query],
  );
  const open = suggestions.length > 0;

  const submit = () => {
    if (blocked) return;
    onSend(
      encodeMentions(body, picked),
      ready.map((item: Upload) => item.attachmentId!),
    );
    if (editing) return;
    setBody("");
    setPicked(new Map());
    setQuery(null);
    uploads.clear();
    if (field.current) {
      field.current.style.height = "";
      field.current.focus();
    }
  };

  const readQuery = (element: HTMLTextAreaElement) => {
    const before = element.value.slice(0, element.selectionStart ?? element.value.length);
    const match = MENTION_QUERY.exec(before);
    setQuery(match ? match[1]! : null);
    setHighlighted(0);
  };

  const pick = (member: Author) => {
    const element = field.current;
    if (!element) return;
    const end = element.selectionStart ?? body.length;
    const before = body.slice(0, end);
    const at = before.lastIndexOf("@");
    const inserted = `@${member.display_name} `;
    const next = body.slice(0, at) + inserted + body.slice(end);
    setBody(next);
    setPicked((current) => new Map(current).set(member.display_name, member.id));
    setQuery(null);
    caret.current = at + inserted.length;
  };

  // After a pick, the caret goes behind the inserted name once React has written the new value.
  useLayoutEffect(() => {
    const element = field.current;
    if (caret.current === null || !element) return;
    element.focus();
    element.setSelectionRange(caret.current, caret.current);
    caret.current = null;
  }, [body]);

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (open) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const step = event.key === "ArrowDown" ? 1 : -1;
        setHighlighted((index) => (index + step + suggestions.length) % suggestions.length);
        return;
      }
      if ((event.key === "Enter" || event.key === "Tab") && !event.shiftKey) {
        event.preventDefault();
        pick(suggestions[highlighted]!);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        setQuery(null);
        return;
      }
    }
    if (event.key === "Escape" && onCancel) {
      event.preventDefault();
      onCancel();
      return;
    }
    // Input methods use Enter to confirm a composition; that must not send the message.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form
      className={cn(
        "flex flex-col gap-1",
        !editing && "border-t border-border bg-surface px-4 py-3",
      )}
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <label htmlFor={`${baseId}-field`} className="sr-only">
        {label}
      </label>
      {uploads.items.length ? (
        <AttachmentChips items={uploads.items} onRemove={uploads.remove} />
      ) : null}
      <div className="relative flex items-end gap-2">
        {open ? (
          <ul
            id={listId}
            role="listbox"
            aria-label={t("mentionSuggestions")}
            className="absolute bottom-full left-0 z-20 mb-1 w-full max-w-sm rounded-panel border border-border bg-surface p-1 shadow-overlay"
          >
            {suggestions.map((member, index) => (
              <li
                key={member.id}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === highlighted}
                // Keeps the focus in the field; a click picks without blurring it first.
                onMouseDown={(event) => {
                  event.preventDefault();
                  pick(member);
                }}
                className={cn(
                  "flex min-h-11 cursor-default items-center gap-2 rounded-control px-2 lg:min-h-9",
                  index === highlighted && "bg-bg-subtle",
                )}
              >
                <Avatar
                  name={member.display_name}
                  src={member.photo_url ?? undefined}
                  size={24}
                  decorative
                />
                <span className="truncate">{member.display_name}</span>
              </li>
            ))}
          </ul>
        ) : null}
        <textarea
          id={`${baseId}-field`}
          ref={field}
          value={body}
          rows={editing ? 2 : 1}
          disabled={disabled}
          placeholder={placeholder}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-activedescendant={open ? `${listId}-${highlighted}` : undefined}
          aria-describedby={`${hintId} ${counterId}`}
          aria-invalid={tooLong || undefined}
          onChange={(event) => {
            setBody(event.target.value);
            grow(event.target);
            readQuery(event.target);
            if (event.target.value) onTyping?.();
          }}
          onKeyDown={onKeyDown}
          onBlur={() => setQuery(null)}
          className={cn(
            "max-h-40 min-h-11 min-w-0 flex-1 resize-none rounded-control border border-border-control bg-surface px-3 py-2 text-text placeholder:text-muted disabled:cursor-not-allowed disabled:bg-bg-subtle lg:min-h-9",
            tooLong && "border-danger",
          )}
        />
        {attachTo && !editing ? (
          <>
            <input
              ref={files}
              type="file"
              multiple
              hidden
              accept={ACCEPTED_FILES}
              onChange={(event) => {
                uploads.add([...(event.target.files ?? [])]);
                event.target.value = "";
              }}
            />
            <Button
              type="button"
              variant="secondary"
              size="icon"
              aria-label={t("attach")}
              disabled={disabled || uploads.items.length >= MAX_ATTACHMENTS}
              onClick={() => files.current?.click()}
              className="max-lg:size-11"
            >
              <Icon icon={Paperclip} />
            </Button>
          </>
        ) : null}
        {editing ? null : (
          <Button type="submit" variant="primary" disabled={blocked}>
            <Icon icon={SendHorizontal} />
            <span className="max-sm:sr-only">{submitLabel ?? t("send")}</span>
          </Button>
        )}
      </div>
      <div className="flex flex-wrap items-baseline justify-between gap-2 text-xs text-muted">
        <span id={hintId} className={cn(!editing && "max-sm:sr-only")}>
          {editing ? t("editHint") : t("composerHint")}
        </span>
        <span id={counterId} aria-live="polite" className={cn("tabular", tooLong && "text-danger")}>
          {tooLong
            ? t("tooLong", { max: MAX_BODY })
            : length >= COUNTER_FROM
              ? t("counter", { count: length, max: MAX_BODY })
              : null}
        </span>
      </div>
      {editing ? (
        <div className="flex flex-wrap gap-2">
          <Button type="submit" size="dense" disabled={blocked}>
            {submitLabel ?? t("save")}
          </Button>
          <Button type="button" size="dense" variant="secondary" onClick={onCancel}>
            {t("cancel")}
          </Button>
        </div>
      ) : null}
      {footer}
    </form>
  );
}
