"use client";

import { Copy, Ellipsis, Flag, Info, Reply } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { RadioGroup } from "@/components/ui/choice";
import { Icon } from "@/components/ui/icon";
import {
  ConfirmDialog,
  Dialog,
  DialogClose,
  DialogContent,
  DialogTrigger,
  Menu,
  MenuContent,
  MenuItem,
  MenuLabel,
  MenuSeparator,
  MenuTrigger,
  Sheet,
  Tooltip,
} from "@/components/ui/overlay";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";

import { Section } from "./section";

export function InteractiveSpecimens() {
  const t = useTranslations("designSystem");
  const toast = useToast();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);

  return (
    <div className="flex flex-col gap-12">
      <p className="flex items-start gap-2 text-muted">
        <Icon icon={Info} size={20} className="mt-px" />
        {t("interactiveNote")}
      </p>

      <Section title={t("sections.overlays")}>
        <div className="flex flex-wrap gap-3">
          <Dialog>
            <DialogTrigger asChild>
              <Button>{t("overlays.openDialog")}</Button>
            </DialogTrigger>
            <DialogContent
              title={t("overlays.dialogTitle")}
              description={t("overlays.dialogDescription")}
              footer={
                <>
                  <DialogClose asChild>
                    <Button>{t("buttons.secondary")}</Button>
                  </DialogClose>
                  <DialogClose asChild>
                    <Button variant="primary">{t("overlays.save")}</Button>
                  </DialogClose>
                </>
              }
            >
              <RadioGroup
                legend={t("overlays.notifyLevel")}
                defaultValue="mentions"
                options={[
                  { value: "all", label: t("overlays.levelAll") },
                  { value: "mentions", label: t("overlays.levelMentions") },
                  { value: "none", label: t("overlays.levelNone") },
                ]}
              />
            </DialogContent>
          </Dialog>

          <Button variant="destructive" onClick={() => setConfirmOpen(true)}>
            {t("overlays.openConfirm")}
          </Button>
          <ConfirmDialog
            open={confirmOpen}
            onOpenChange={setConfirmOpen}
            title={t("overlays.confirmTitle")}
            consequence={t("overlays.confirmConsequence")}
            confirmLabel={t("overlays.confirmAction")}
            onConfirm={() => setConfirmOpen(false)}
            destructive
          />

          <Menu>
            <MenuTrigger asChild>
              <Button>
                <Icon icon={Ellipsis} />
                {t("overlays.openMenu")}
              </Button>
            </MenuTrigger>
            <MenuContent align="start">
              <MenuLabel>{t("overlays.menuLabel")}</MenuLabel>
              <MenuItem>
                <Icon icon={Reply} />
                {t("overlays.menuReply")}
              </MenuItem>
              <MenuItem>
                <Icon icon={Copy} />
                {t("overlays.menuCopy")}
              </MenuItem>
              <MenuSeparator />
              <MenuItem destructive>
                <Icon icon={Flag} />
                {t("overlays.menuReport")}
              </MenuItem>
            </MenuContent>
          </Menu>

          <Tooltip content={t("overlays.tooltip")}>
            <Button variant="tertiary">{t("overlays.tooltipTrigger")}</Button>
          </Tooltip>

          <Button onClick={() => setSheetOpen(true)}>{t("overlays.openSheet")}</Button>
          <Sheet open={sheetOpen} onOpenChange={setSheetOpen} title={t("overlays.sheetTitle")}>
            <p className="p-4 text-muted">{t("overlays.sheetBody")}</p>
          </Sheet>

          <Button
            onClick={() =>
              toast({ title: t("feedback.toastTitle"), description: t("feedback.successBody") })
            }
          >
            {t("feedback.showToast")}
          </Button>
        </div>
      </Section>

      <Section title={t("sections.tabs")}>
        <Tabs defaultValue="schedule">
          <TabsList>
            <TabsTrigger value="schedule">{t("tabs.schedule")}</TabsTrigger>
            <TabsTrigger value="materials">{t("tabs.materials")}</TabsTrigger>
            <TabsTrigger value="members">{t("tabs.members")}</TabsTrigger>
          </TabsList>
          <TabsContent value="schedule">{t("tabs.scheduleBody")}</TabsContent>
          <TabsContent value="materials">{t("tabs.materialsBody")}</TabsContent>
          <TabsContent value="members">{t("tabs.membersBody")}</TabsContent>
        </Tabs>
      </Section>
    </div>
  );
}
