import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import AnalyticsPage from "./page";

const state = vi.hoisted(() => ({ total: null as number | null }));
vi.mock("react", async (importOriginal) => ({
  ...await importOriginal<typeof import("react")>(),
  useEffect: () => {},
  useState: (initial: unknown) => [initial === null ? { votes: { total: state.total } } : initial === true ? false : initial, () => {}],
}));
vi.mock("next-intl", () => ({ useLocale: () => "en" }));

describe("analytics turnout", () => {
  it.each([null, 0, 41])("renders the returned turnout %s without inventing zero", (total) => {
    state.total = total;
    const html = renderToStaticMarkup(<AnalyticsPage />);
    expect(html).toContain(`text-blue-600">${total == null ? "—" : total}</div>`);
  });
});
