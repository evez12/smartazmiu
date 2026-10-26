import {
  BookOpen,
  CalendarClock,
  CircleCheck,
  Ellipsis,
  Lock,
  Paperclip,
  RotateCw,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Checkbox, RadioGroup, Switch } from "@/components/ui/choice";
import { CountBadge } from "@/components/ui/count-badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Breadcrumb, PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Skeleton, SkeletonText } from "@/components/ui/skeleton";
import { Tag } from "@/components/ui/tag";
import { cn } from "@/lib/cn";

import { ChatSpecimen } from "@/features/chat/specimen";

import { GroupTable } from "./group-table";
import { Section } from "./section";
import { Sprint6Specimens } from "./sprint6-specimens";

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-medium text-muted">{label}</h3>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </div>
  );
}

const colorGroups = {
  surfaces: ["bg", "bg-subtle", "surface"],
  text: ["text", "text-muted"],
  brand: ["primary", "primary-hover", "primary-contrast", "accent"],
  semantic: ["success", "warning", "danger", "info"],
  borders: ["border", "border-strong", "border-control", "focus-ring"],
} as const;

function Colors() {
  const t = useTranslations("designSystem");
  return (
    <Section title={t("sections.colors")}>
      {Object.entries(colorGroups).map(([group, tokens]) => (
        <Row key={group} label={t(`colors.${group as keyof typeof colorGroups}`)}>
          {tokens.map((token) => (
            <div key={token} className="flex w-32 flex-col gap-1">
              <div
                className="h-10 rounded-control border border-border"
                style={{ backgroundColor: `var(--${token})` }}
              />
              <code className="font-mono text-xs text-muted">--{token}</code>
            </div>
          ))}
        </Row>
      ))}
    </Section>
  );
}

function Typography() {
  const t = useTranslations("designSystem.typography");
  const ds = useTranslations("designSystem");
  return (
    <Section title={ds("sections.typography")}>
      <div className="flex flex-col gap-3">
        <p className="text-2xl font-semibold">{t("h1")}</p>
        <p className="text-xl font-semibold">{t("h2")}</p>
        <p className="text-lg font-semibold">{t("h3")}</p>
        <p className="text-md">{t("publicBody")}</p>
        <p className="text-base">{t("appBody")}</p>
        <p className="text-sm">{t("dense")}</p>
        <p className="text-xs text-muted">{t("caption")}</p>
      </div>
      <Row label={t("weights")}>
        <span className="font-normal">{t("weight400")}</span>
        <span className="font-medium">{t("weight500")}</span>
        <span className="font-semibold">{t("weight600")}</span>
      </Row>
      <Row label={t("numerals")}>
        <span className="tabular">{t("numeralsSample")}</span>
      </Row>
      <Row label={t("mono")}>
        <code className="font-mono">
          normalize_az(&quot;İSTİFADƏÇİ&quot;) == &quot;istifadəçi&quot;
        </code>
      </Row>
    </Section>
  );
}

const ALPHABET = "A B C Ç D E Ə F G Ğ H X I İ J K Q L M N O Ö P R S Ş T U Ü V Y Z";
const SPECIAL = "Ə ə İ ı Ş ş Ğ ğ Ç ç Ö ö Ü ü";

function Glyphs() {
  const t = useTranslations("designSystem.glyphs");
  const ds = useTranslations("designSystem");
  const weights = ["font-normal", "font-medium", "font-semibold"] as const;
  return (
    <Section title={ds("sections.glyphs")}>
      <Row label={t("alphabet")}>
        <div className="flex flex-col gap-1">
          <p className="text-md">{ALPHABET}</p>
          <p className="text-md">{ALPHABET.toLocaleLowerCase("az")}</p>
        </div>
      </Row>
      <Row label={t("special")}>
        <div className="flex flex-col gap-1">
          {weights.map((weight) => (
            <p key={weight} className={cn("text-lg", weight)}>
              {SPECIAL}
            </p>
          ))}
        </div>
      </Row>
      <Row label={t("uppercase")}>
        <p lang="az" className="font-medium uppercase">
          {t("uppercaseSource")}
        </p>
      </Row>
      <p className="max-w-[75ch]">{t("sentence")}</p>
      <Row label={t("cyrillic")}>
        <p lang="ru">{t("cyrillicSample")}</p>
      </Row>
    </Section>
  );
}

function Buttons() {
  const t = useTranslations("designSystem.buttons");
  const ds = useTranslations("designSystem");
  return (
    <Section title={ds("sections.buttons")}>
      <Row label={t("variants")}>
        <Button variant="primary">{t("primary")}</Button>
        <Button variant="secondary">{t("secondary")}</Button>
        <Button variant="tertiary">{t("tertiary")}</Button>
        <Button variant="destructive">{t("destructive")}</Button>
        <Button variant="destructive-solid">{t("destructiveSolid")}</Button>
      </Row>
      <Row label={t("sizes")}>
        <Button variant="secondary">
          <Icon icon={Paperclip} />
          {t("withIcon")}
        </Button>
        <Button variant="secondary" size="dense">
          {t("dense")}
        </Button>
        <Button variant="secondary" size="icon" aria-label={t("iconOnly")}>
          <Icon icon={Ellipsis} size={20} />
        </Button>
        <Button variant="tertiary" size="icon-dense" aria-label={t("iconOnly")}>
          <Icon icon={Ellipsis} />
        </Button>
      </Row>
      <Row label={t("states")}>
        <Button variant="primary" disabled>
          {t("disabled")}
        </Button>
        <Button variant="secondary" disabled>
          {t("disabled")}
        </Button>
        <Button variant="primary" loading>
          {t("loading")}
        </Button>
      </Row>
    </Section>
  );
}

function Forms() {
  const t = useTranslations("designSystem.forms");
  const ds = useTranslations("designSystem");
  return (
    <Section title={ds("sections.forms")}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("name")} required>
          <Input defaultValue={t("nameValue")} autoComplete="name" />
        </Field>
        <Field label={t("group")} helper={t("groupHelper")}>
          <Input defaultValue={t("groupValue")} readOnly />
        </Field>
        <Field label={t("email")} error={t("emailError")} required>
          <Input defaultValue={t("emailValue")} type="text" inputMode="email" />
        </Field>
        <Field label={t("disabled")}>
          <Input defaultValue={t("disabledValue")} disabled />
        </Field>
        <Field label={t("semester")}>
          <Select defaultValue="fall">
            <option value="fall">{t("semesterFall")}</option>
            <option value="spring">{t("semesterSpring")}</option>
            <option value="summer">{t("semesterSummer")}</option>
          </Select>
        </Field>
        <Field label={t("bio")} helper={t("bioHelper")}>
          <Textarea maxLength={300} rows={3} />
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-3">
          <Checkbox label={t("consent")} description={t("consentHelp")} defaultChecked />
          <Checkbox label={t("notifications")} />
          <Checkbox label={t("indeterminate")} checked="indeterminate" />
          <Checkbox label={t("disabledChoice")} disabled />
          <Switch label={t("quietHours")} defaultChecked />
        </div>
        <RadioGroup
          legend={t("dmPolicy")}
          defaultValue="shared_context"
          options={[
            { value: "everyone", label: t("dmEveryone") },
            { value: "shared_context", label: t("dmShared") },
            { value: "guides_and_teachers", label: t("dmGuides") },
            { value: "nobody", label: t("dmNobody"), description: t("dmNobodyHelp") },
          ]}
        />
      </div>
    </Section>
  );
}

function Tags() {
  const t = useTranslations("designSystem.tags");
  const ds = useTranslations("designSystem");
  return (
    <Section title={ds("sections.tags")}>
      <Row label={t("neutral")}>
        <Tag>{t("neutral")}</Tag>
        <Tag tone="info" icon={CalendarClock}>
          {t("info")}
        </Tag>
        <Tag tone="success" icon={CircleCheck}>
          {t("success")}
        </Tag>
        <Tag tone="warning">{t("warning")}</Tag>
        <Tag tone="danger">{t("danger")}</Tag>
        <Tag tone="accent">{t("accent")}</Tag>
      </Row>
      <Row label={t("counters")}>
        <CountBadge count={3} />
        <CountBadge count={128} />
        <CountBadge count={2} kind="mention" />
      </Row>
    </Section>
  );
}

function Feedback() {
  const t = useTranslations("designSystem.feedback");
  const ds = useTranslations("designSystem");
  return (
    <Section title={ds("sections.feedback")}>
      <Banner tone="info" title={t("infoTitle")}>
        {t("infoBody")}
      </Banner>
      <Banner tone="success" title={t("successTitle")}>
        {t("successBody")}
      </Banner>
      <Banner tone="warning" title={t("warningTitle")}>
        {t("warningBody")}
      </Banner>
      <Banner
        tone="danger"
        title={t("dangerTitle")}
        action={
          <Button size="dense">
            <Icon icon={RotateCw} />
            {t("retry")}
          </Button>
        }
      >
        {t("dangerBody")}
      </Banner>
    </Section>
  );
}

function Navigation() {
  const t = useTranslations("designSystem.navigation");
  const ds = useTranslations("designSystem");
  return (
    <Section title={ds("sections.navigation")}>
      <Breadcrumb
        items={[
          { label: t("home"), href: "/design-system" },
          { label: t("subjects"), href: "/design-system" },
          { label: t("subject") },
        ]}
      />
      <Panel>
        <PanelBody>
          <PageHeader
            className="pb-0"
            title={t("headerTitle")}
            description={t("headerDescription")}
            actions={<Button variant="primary">{t("headerAction")}</Button>}
          />
        </PanelBody>
      </Panel>
      <div className="flex items-center gap-3">
        <Avatar name="Aysel Məmmədova" size={40} />
        <Avatar name="ilkin əliyev" size={32} />
        <Avatar name="Şəhla Ağayeva" size={24} />
      </div>
    </Section>
  );
}

function States() {
  const t = useTranslations("designSystem.states");
  const ds = useTranslations("designSystem");
  return (
    <Section title={ds("sections.states")}>
      <div className="grid gap-4 md:grid-cols-2">
        <Panel>
          <PanelHeader title={t("loading")} headingLevel={3} />
          <PanelBody className="flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <Skeleton className="size-8 rounded-full" />
              <Skeleton className="h-4 w-40" />
            </div>
            <SkeletonText lines={3} />
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title={t("empty")} headingLevel={3} />
          <PanelBody>
            <EmptyState
              className="py-0"
              icon={BookOpen}
              message={t("emptyMessage")}
              action={<Button size="dense">{t("emptyAction")}</Button>}
            />
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title={t("error")} headingLevel={3} />
          <PanelBody>
            <Banner
              tone="danger"
              title={t("errorTitle")}
              action={
                <Button size="dense">
                  <Icon icon={RotateCw} />
                  {ds("feedback.retry")}
                </Button>
              }
            >
              {t("errorBody")}
            </Banner>
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title={t("forbidden")} headingLevel={3} />
          <PanelBody className="flex flex-col items-start gap-3">
            <p className="flex items-start gap-2 font-medium text-text">
              <Icon icon={Lock} size={20} className="mt-px text-muted" />
              {t("forbiddenTitle")}
            </p>
            <p className="max-w-[75ch] text-muted">{t("forbiddenBody")}</p>
            <Button size="dense" variant="tertiary">
              {t("back")}
            </Button>
          </PanelBody>
        </Panel>
      </div>
    </Section>
  );
}

/** Everything that renders without user interaction, so it can be shown in both themes at once. */
export function StaticSpecimens() {
  const t = useTranslations("designSystem");
  return (
    <div className="flex flex-col gap-12">
      <Colors />
      <Typography />
      <Glyphs />
      <Buttons />
      <Forms />
      <Tags />
      <Feedback />
      <Section title={t("sections.table")}>
        <GroupTable />
      </Section>
      <Navigation />
      <States />
      <Section title={t("sections.chat")}>
        <ChatSpecimen />
      </Section>
      <Sprint6Specimens />
    </div>
  );
}
