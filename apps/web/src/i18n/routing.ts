import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["el", "en"],
  defaultLocale: "el",
  localeCookie: {
    name: "NEXT_LOCALE",
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
  },
});
