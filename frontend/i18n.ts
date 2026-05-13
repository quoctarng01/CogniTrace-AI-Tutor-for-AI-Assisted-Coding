/**
 * Internationalization setup using next-intl.
 * 
 * Supports: English (en), Vietnamese (vi)
 * Add more locales by adding entries to messages/ and configuring in i18n.ts
 */
import { getRequestConfig } from "next-intl/server";
import { cookies, headers } from "next/headers";

export const locales = ["en", "vi"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "en";

export default getRequestConfig(async () => {
  const headersList = await headers();
  const cookieStore = await cookies();

  // Accept-Language header → locale
  const acceptLanguage = headersList.get("accept-language") ?? "";
  const preferredLocale = acceptLanguage
    ? acceptLanguage
        .split(",")[0]
        .split("-")[0]
        .toLowerCase() as Locale
    : defaultLocale;

  // Cookie override (user preference)
  const localeCookie = cookieStore.get("NEXT_LOCALE")?.value as Locale | undefined;

  const locale = localeCookie ?? (locales.includes(preferredLocale) ? preferredLocale : defaultLocale);

  return {
    locale,
    messages: (await import(`./locales/${locale}.json`)).default,
  };
});
