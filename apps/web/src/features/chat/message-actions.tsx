"use client";

import { MessageSquareReply, Ellipsis, Pencil, SmilePlus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  Menu,
  MenuContent,
  MenuItem,
  MenuTrigger,
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/overlay";
import { cn } from "@/lib/cn";

import { REACTIONS, type ChatMessage } from "./model";

/** The eight reactions in a grid (D-067); a pressed button removes the reader's own reaction. */
export function ReactionPicker({
  mine,
  onPick,
  trigger,
}: {
  mine: readonly string[];
  onPick: (emoji: string, add: boolean) => void;
  trigger: ReactNode;
}) {
  const t = useTranslations("chat");
  const [open, setOpen] = useState(false);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent align="end" className="grid grid-cols-4 gap-1 p-2">
        {REACTIONS.map((emoji) => {
          const pressed = mine.includes(emoji);
          return (
            <button
              key={emoji}
              type="button"
              aria-pressed={pressed}
              aria-label={t("reactWith", { emoji })}
              onClick={() => {
                onPick(emoji, !pressed);
                setOpen(false);
              }}
              className={cn(
                "flex size-11 items-center justify-center rounded-control border text-xl hover:bg-bg-subtle lg:size-9",
                pressed ? "border-primary bg-bg-subtle" : "border-transparent",
              )}
            >
              {emoji}
            </button>
          );
        })}
      </PopoverContent>
    </Popover>
  );
}

/** Counts under a message; each chip toggles the reader's reaction and states its count in words. */
export function ReactionChips({
  message,
  disabled,
  onToggle,
}: {
  message: ChatMessage;
  disabled: boolean;
  onToggle: (emoji: string, add: boolean) => void;
}) {
  const t = useTranslations("chat");
  if (!message.reactions.length) return null;
  const mine = message.my_reactions ?? [];
  return (
    <ul className="mt-1 flex flex-wrap gap-1">
      {message.reactions.map((reaction) => {
        const pressed = mine.includes(reaction.emoji);
        return (
          <li key={reaction.emoji}>
            <button
              type="button"
              disabled={disabled}
              aria-pressed={pressed}
              aria-label={t("reactionCount", {
                emoji: reaction.emoji,
                count: reaction.count,
                mine: String(pressed),
              })}
              onClick={() => onToggle(reaction.emoji, !pressed)}
              className={cn(
                "inline-flex h-7 items-center gap-1 rounded-control border px-1.5 text-sm tabular hover:bg-bg-subtle disabled:cursor-not-allowed pointer-coarse:h-11",
                pressed ? "border-primary bg-bg-subtle font-medium" : "border-border",
              )}
            >
              <span aria-hidden="true">{reaction.emoji}</span>
              <span aria-hidden="true">{reaction.count}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export type MessageActionHandlers = {
  canReact: boolean;
  onReact: (emoji: string, add: boolean) => void;
  onReply?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  /** Further "more" menu entries (report, Sprint 6 group A). */
  extra?: ReactNode;
};

/**
 * Hover toolbar (§12.7): react, reply, more. It is also shown while any of its controls has focus, so keyboard
 * users reach it by tabbing through the message.
 */
export function MessageToolbar({
  message,
  handlers,
}: {
  message: ChatMessage;
  handlers: MessageActionHandlers;
}) {
  const t = useTranslations("chat");
  const { canReact, onReact, onReply, onEdit, onDelete, extra } = handlers;
  const hasMore = Boolean(onEdit || onDelete || extra);
  return (
    <div
      role="toolbar"
      aria-label={t("toolbarLabel")}
      className="absolute -top-4 right-4 hidden gap-0.5 rounded-control border border-border bg-surface p-0.5 group-focus-within:flex group-hover:flex pointer-coarse:static pointer-coarse:mt-1 pointer-coarse:flex pointer-coarse:w-fit"
    >
      {canReact ? (
        <ReactionPicker
          mine={message.my_reactions ?? []}
          onPick={onReact}
          trigger={
            <Button variant="tertiary" size="icon-dense" aria-label={t("react")}>
              <Icon icon={SmilePlus} />
            </Button>
          }
        />
      ) : null}
      {onReply ? (
        <Button variant="tertiary" size="icon-dense" aria-label={t("reply")} onClick={onReply}>
          <Icon icon={MessageSquareReply} />
        </Button>
      ) : null}
      {hasMore ? (
        <Menu>
          <MenuTrigger asChild>
            <Button variant="tertiary" size="icon-dense" aria-label={t("more")}>
              <Icon icon={Ellipsis} />
            </Button>
          </MenuTrigger>
          <MenuContent>
            {onEdit ? (
              <MenuItem onSelect={onEdit}>
                <Icon icon={Pencil} />
                {t("edit")}
              </MenuItem>
            ) : null}
            {onDelete ? (
              <MenuItem destructive onSelect={onDelete}>
                <Icon icon={Trash2} />
                {t("delete")}
              </MenuItem>
            ) : null}
            {extra}
          </MenuContent>
        </Menu>
      ) : null}
    </div>
  );
}
