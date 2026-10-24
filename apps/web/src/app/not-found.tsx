import { FileQuestion } from "lucide-react";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import { StatusPage } from "@/features/shell/status-page";

export default async function NotFound() {
  const t = await getTranslations("status");
  return (
    <StatusPage
      icon={FileQuestion}
      title={t("notFoundTitle")}
      body={t("notFoundBody")}
      action={
        <Button asChild variant="primary">
          <Link href="/">{t("goHome")}</Link>
        </Button>
      }
    />
  );
}
