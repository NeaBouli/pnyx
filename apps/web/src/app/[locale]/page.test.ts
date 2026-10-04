import { beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "./page";

const nav = vi.hoisted(() => ({
  redirect: vi.fn((url: string) => { throw new Error(`NEXT_REDIRECT ${url}`); }),
  notFound: vi.fn(() => { throw new Error("NEXT_HTTP_ERROR_FALLBACK;404"); }),
}));
vi.mock("next/navigation", () => nav);

const params = (locale: string) => Promise.resolve({ locale });

describe("[locale] HomePage (EKA-64)", () => {
  beforeEach(() => {
    nav.redirect.mockClear();
    nav.notFound.mockClear();
  });

  it.each(["ai.txt", "llms-full.txt", "xyz.json"])("returns 404 without redirect for invalid locale %s", async (locale) => {
    await expect(HomePage({ params: params(locale) })).rejects.toThrow("NEXT_HTTP_ERROR_FALLBACK;404");
    expect(nav.notFound).toHaveBeenCalledOnce();
    expect(nav.redirect).not.toHaveBeenCalled();
  });

  it.each(["el", "en"])("keeps the landing redirect for %s", async (locale) => {
    await expect(HomePage({ params: params(locale) })).rejects.toThrow("NEXT_REDIRECT https://ekklesia.gr");
    expect(nav.redirect).toHaveBeenCalledExactlyOnceWith("https://ekklesia.gr");
    expect(nav.notFound).not.toHaveBeenCalled();
  });
});
