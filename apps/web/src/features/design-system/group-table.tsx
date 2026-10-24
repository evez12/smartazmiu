"use client";

import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  type SortDirection,
} from "@/components/ui/table";

type GroupRow = {
  code: string;
  specialty: "civil" | "architecture" | "economics" | "design";
  students: number;
  curator: string;
};

// Made-up sample data (D-010).
const GROUPS: GroupRow[] = [
  { code: "765a2", specialty: "civil", students: 27, curator: "Rəşad Mirzəyev" },
  { code: "742a1", specialty: "architecture", students: 22, curator: "Günel Kazımova" },
  { code: "781b3", specialty: "economics", students: 31, curator: "Şəhla Ağayeva" },
  { code: "713a2", specialty: "design", students: 18, curator: "Çingiz Hüseynov" },
];

const collator = new Intl.Collator("az");

export function GroupTable() {
  const t = useTranslations("designSystem.table");
  const [sort, setSort] = useState<{ key: "code" | "students"; direction: SortDirection }>({
    key: "code",
    direction: "ascending",
  });

  const rows = useMemo(() => {
    const sorted = [...GROUPS].sort((a, b) =>
      sort.key === "students" ? a.students - b.students : collator.compare(a.code, b.code),
    );
    return sort.direction === "descending" ? sorted.reverse() : sorted;
  }, [sort]);

  const toggle = (key: "code" | "students") =>
    setSort((current) => ({
      key,
      direction:
        current.key === key && current.direction === "ascending" ? "descending" : "ascending",
    }));

  return (
    <Table>
      <TableCaption>{t("caption")}</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead
            sort={sort.key === "code" ? sort.direction : "none"}
            onSort={() => toggle("code")}
          >
            {t("group")}
          </TableHead>
          <TableHead>{t("specialty")}</TableHead>
          <TableHead
            numeric
            sort={sort.key === "students" ? sort.direction : "none"}
            onSort={() => toggle("students")}
          >
            {t("students")}
          </TableHead>
          <TableHead>{t("curator")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.code}>
            <TableCell label={t("group")} className="font-medium">
              {row.code}
            </TableCell>
            <TableCell label={t("specialty")}>{t(row.specialty)}</TableCell>
            <TableCell label={t("students")} numeric>
              {row.students}
            </TableCell>
            <TableCell label={t("curator")}>{row.curator}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
