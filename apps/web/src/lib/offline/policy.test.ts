import { describe, expect, it } from "vitest";

import { belongsTo, forbidsStoring, isNeverStored, isStorableChannel, snapshotKey } from "./policy";

describe("snapshot keys", () => {
  it("are namespaced by the user, so one account cannot address another's data", () => {
    const aysel = "01a19d28-c354-7be3-83ff-a11dbd4de9d1";
    const ramin = "01a19d28-c354-7be3-83ff-a11dbd4de9d2";
    expect(snapshotKey(aysel, "channel", "c1")).toBe(`u:${aysel}:channel:c1`);
    expect(belongsTo(aysel, snapshotKey(aysel, "schedule"))).toBe(true);
    expect(belongsTo(ramin, snapshotKey(aysel, "schedule"))).toBe(false);
  });

  it("do not let a user id that is a prefix of another match", () => {
    expect(belongsTo("u1", snapshotKey("u10", "schedule"))).toBe(false);
  });
});

describe("channels that may be stored", () => {
  const channel = (type: string, is_archived = false) => ({ type, is_archived });

  it("are course, community, group, faculty, announcement and club channels", () => {
    for (const type of [
      "course_offering",
      "subject_community",
      "academic_group",
      "faculty",
      "announcement",
      "club",
    ]) {
      expect(isStorableChannel(channel(type)), type).toBe(true);
    }
  });

  it("never include direct messages, support or private groups", () => {
    for (const type of ["dm", "support", "private_group"]) {
      expect(isStorableChannel(channel(type)), type).toBe(false);
    }
  });

  it("leave out archived channels", () => {
    expect(isStorableChannel(channel("course_offering", true))).toBe(false);
  });
});

describe("data that is never stored", () => {
  it.each([
    "/api/v1/me/grades",
    "/api/v1/me/academics",
    "/api/v1/me/export",
    "/api/v1/me/push-subscriptions",
    "/api/v1/attendance/sessions/1/check-in",
    "/api/v1/exams/slots",
    "/api/v1/exams/papers/3/download",
    "/api/v1/gpa/rules",
    "/api/v1/admin/users",
    "/api/v1/reports/queue",
    "/api/v1/privacy/consents",
    "/api/v1/chat/ws-ticket",
    "/api/v1/chat/attachments/9",
    "/api/v1/materials/4/files",
    "/auth/callback",
    "/smartazmiu/object-key",
    "/ws",
  ])("refuses %s", (path) => {
    expect(isNeverStored(path)).toBe(true);
  });

  it.each(["/api/v1/me/schedule", "/api/v1/chat/channels", "/api/v1/chat/channels/c1/messages"])(
    "does not refuse %s, the kinds that may be stored",
    (path) => {
      expect(isNeverStored(path)).toBe(false);
    },
  );

  it("refuses a response that says no-store", () => {
    expect(forbidsStoring(new Headers({ "cache-control": "private, no-store" }))).toBe(true);
    expect(forbidsStoring(new Headers({ "cache-control": "NO-STORE" }))).toBe(true);
    expect(forbidsStoring(new Headers({ "cache-control": "private, max-age=60" }))).toBe(false);
    expect(forbidsStoring(new Headers())).toBe(false);
  });
});
