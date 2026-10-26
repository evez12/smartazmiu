"use client";

import { SendHorizontal } from "lucide-react";
import { useTranslations } from "next-intl";
import { useId, useRef, useState, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/cn";

import { COUNTER_FROM, MAX_BODY } from "./model";

const MAX_HEIGHT_PX = 160;

/** Grows with its lines up to 160 px, then scrolls; the width stays the row's. */
function grow(element: HTMLTextAreaElement) {
  element.style.height = "auto";
  element.style.height = `${Math.min(element.scrollHeight + 2, MAX_HEIGHT_PX)}px`;
}

type ComposerProps = {
  channelName: string;
  disabled: boolean;
  onSend: (body: string) => void;
  onTyping: () => void;
};

/** Multi-line composer: Enter sends, Shift+Enter starts a new line, a counter near the limit (§12.7). */
export function Composer({ channelName, disabled, onSend, onTyping }: ComposerProps) {
  const t = useTranslations("chat");
  const [body, setBody] = useState("");
  const field = useRef<HTMLTextAreaElement>(null);
  const hintId = useId();
  const counterId = useId();
  const length = body.length;
  const tooLong = length > MAX_BODY;
  const empty = body.trim().length === 0;

  const submit = () => {
    if (disabled || empty || tooLong) return;
    onSend(body);
    setBody("");
    if (field.current) {
      field.current.style.height = "";
      field.current.focus();
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Input methods use Enter to confirm a composition; that must not send the message.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form
      className="flex flex-col gap-1 border-t border-border bg-surface px-4 py-3"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <label htmlFor={`${hintId}-field`} className="sr-only">
        {t("composerLabel")}
      </label>
      <div className="flex items-end gap-2">
        <textarea
          id={`${hintId}-field`}
          ref={field}
          value={body}
          rows={1}
          disabled={disabled}
          placeholder={t("composerPlaceholder", { channel: channelName })}
          aria-describedby={`${hintId} ${counterId}`}
          aria-invalid={tooLong || undefined}
          onChange={(event) => {
            setBody(event.target.value);
            grow(event.target);
            if (event.target.value) onTyping();
          }}
          onKeyDown={onKeyDown}
          className={cn(
            "max-h-40 min-h-11 min-w-0 flex-1 resize-none rounded-control border border-border-control bg-surface px-3 py-2 text-text placeholder:text-muted disabled:cursor-not-allowed disabled:bg-bg-subtle lg:min-h-9",
            tooLong && "border-danger",
          )}
        />
        <Button type="submit" variant="primary" disabled={disabled || empty || tooLong}>
          <Icon icon={SendHorizontal} />
          <span className="max-sm:sr-only">{t("send")}</span>
        </Button>
      </div>
      <div className="flex flex-wrap items-baseline justify-between gap-2 text-xs text-muted">
        <span id={hintId} className="max-sm:sr-only">
          {t("composerHint")}
        </span>
        <span id={counterId} aria-live="polite" className={cn("tabular", tooLong && "text-danger")}>
          {tooLong
            ? t("tooLong", { max: MAX_BODY })
            : length >= COUNTER_FROM
              ? t("counter", { count: length, max: MAX_BODY })
              : null}
        </span>
      </div>
    </form>
  );
}
