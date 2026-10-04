import { hasLocale } from "next-intl";
import { notFound, redirect } from "next/navigation";
import { routing } from "@/i18n/routing";

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  // EKA-64: dotted misses like /ai.txt land here as locale="ai.txt"; answer 404, not a landing redirect.
  if (!hasLocale(routing.locales, locale)) notFound();
  redirect("https://ekklesia.gr");
}
