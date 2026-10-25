import { countDifferences, seedRowCounts } from "./database";

/**
 * Data hygiene check: the suite starts on the seeded sample data (`make e2e` runs `make seed` first) and must
 * leave every seed table with the row count it found. A test that imports records removes them itself
 * (`TestRecords`); this check catches the ones that forget.
 */
export default async function globalSetup() {
  const before = await seedRowCounts();
  return async () => {
    const differences = countDifferences(before, await seedRowCounts());
    if (differences.length) {
      throw new Error(`E2E run left seed data changed:\n  ${differences.join("\n  ")}`);
    }
  };
}
