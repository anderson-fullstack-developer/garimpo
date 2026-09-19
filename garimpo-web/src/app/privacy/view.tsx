"use client";

import { LegalPage, type LegalSection } from "@/features/legal/LegalPage";
import { APP_NAME } from "@/config/brand";

const SECTIONS: LegalSection[] = [
  {
    title: "Who is responsible for your data",
    body: [
      `The controller of your personal data is [OPERATOR LEGAL NAME], [ADDRESS] (“we”, “us”), the operator of ${APP_NAME}. Contact for privacy questions and to exercise your rights: [CONTACT EMAIL]. [If required: Data Protection Officer / EU representative: NAME, CONTACT.]`,
    ],
  },
  {
    title: "What data we process, why, and on what legal basis",
    body: [
      "We only process what we need to run the service.",
      "• Account data: your email address (used as your login name; we do not send email to it), your password (stored only as a salted hash), your country, language, currency and plan, and account dates. Purpose: create and secure your account and provide the service. Legal basis: performance of a contract (Art. 6(1)(b) GDPR).",
      "• Telegram data: the identifier and name of the Telegram chat you connect (private chat, group or channel), your language choice for that chat, and the messages the bot sends there. Purpose: verify that you are a real person and deliver your alerts and account messages (such as password reset links). Legal basis: performance of a contract.",
      "• Your alerts and settings: search terms, price limits, excluded words, countries, check interval and related options. Purpose: run your alerts. Legal basis: performance of a contract.",
      "• Listing data: public information about marketplace listings that match searches (title, price, condition, photo link, listing link, posting time estimate) and your alert matches and notification history. Purpose: show results and avoid duplicate alerts. Legal basis: performance of a contract and our legitimate interest in operating the service (Art. 6(1)(f)). This is information about products, not about you.",
      "• Technical data: IP address, browser and request details in server logs and for abuse and rate limiting; session cookies (see Cookies). Purpose: security, preventing abuse and fixing errors. Legal basis: legitimate interest (Art. 6(1)(f)).",
      "We do not ask for your real name, phone number, address, payment card or precise location, and we do not use your data for advertising or sell it.",
    ],
  },
  {
    title: "Who receives your data (processors and recipients)",
    body: [
      "We use service providers that process data on our behalf, under contracts that require them to protect it:",
      "• Database hosting: Neon (PostgreSQL), in the European Union (Frankfurt).",
      "• Application hosting: [HOSTING PROVIDER AND REGION].",
      "• Telegram (Telegram Messenger): to deliver messages to your chat. Telegram is an independent service with its own privacy policy; messages you receive on Telegram are handled by Telegram.",
      "• Translation: listing titles (not your account data) may be sent to a translation service ([TRANSLATION PROVIDER, currently MyMemory]) so that we can show or send them in your language.",
      "• Exchange rates: we fetch public rates from the European Central Bank via Frankfurter; no personal data is sent.",
      "• [Anti-bot verification provider, if used, e.g. Cloudflare Turnstile.]",
      "We also read public pages of the marketplace to find listings; this does not involve sending your personal data to it. We disclose data to authorities only when the law requires it.",
    ],
  },
  {
    title: "International transfers",
    body: [
      "Where a provider processes data outside the European Economic Area (for example Telegram or a translation provider), we rely on an adequacy decision or on Standard Contractual Clauses and other safeguards required by the GDPR. You can ask us for details.",
    ],
  },
  {
    title: "How long we keep data",
    body: [
      "• Account, alerts, settings and connected chats: until you delete your account (Settings → Account → Delete my account), which erases them together with your matches and notification history.",
      "• Listing data: deleted automatically about 30 days after the listing was last seen.",
      "• Monitor run logs: about 7 days. Expired sessions and password-reset codes are deleted automatically.",
      "• Server logs: [RETENTION PERIOD, e.g. up to 30 days].",
      "• Backups: kept by our database provider for a limited period and then overwritten.",
      "We may keep limited data longer where the law requires it or to handle legal claims.",
    ],
  },
  {
    title: "Cookies and similar technologies",
    body: [
      "We use only strictly necessary storage: secure, HTTP-only session cookies that keep you logged in; a cookie that remembers your language; and browser storage that remembers your theme (light/dark) and small interface preferences. These do not need consent under the ePrivacy rules. We do not use advertising or analytics cookies. If that changes, we will ask for your consent first.",
    ],
  },
  {
    title: "Your rights",
    body: [
      "Under the GDPR you have the right to:",
      "• access your personal data and receive a copy;",
      "• have inaccurate data corrected;",
      "• have your data erased (you can do it yourself by deleting your account in Settings);",
      "• restrict or object to certain processing, including processing based on legitimate interest;",
      "• receive your data in a portable format;",
      "• withdraw consent at any time where we rely on it, without affecting earlier processing;",
      "• lodge a complaint with your local data protection authority (for example, the authority in your country of residence).",
      "To exercise these rights, contact [CONTACT EMAIL]. We may need to verify your identity, for example by asking you to send a message from your connected Telegram chat. We reply within one month.",
    ],
  },
  {
    title: "Security",
    body: [
      "We protect your data with measures such as password hashing, encrypted connections (HTTPS), HTTP-only cookies, access limited to the data that belongs to each account, rate limiting and short-lived, single-use password reset codes. No system is completely secure; if a breach affecting your data occurs, we will notify you and the authorities as the law requires.",
    ],
  },
  {
    title: "Children",
    body: [
      "The service is not for anyone under 16. We do not knowingly collect data from children. If you believe a child has given us data, contact us and we will delete it.",
    ],
  },
  {
    title: "Automated decisions",
    body: [
      "We do not make decisions about you that have legal or similarly significant effects based solely on automated processing. Alerts are matched only against the rules you set.",
    ],
  },
  {
    title: "Changes to this policy and contact",
    body: [
      "We may update this policy. We will post the new version here with a new date and, for material changes, notify you in the app or on Telegram.",
      "Questions or requests: [CONTACT EMAIL].",
    ],
  },
];

export function PrivacyPage() {
  return <LegalPage title="Privacy Policy" updated="19 September 2026" sections={SECTIONS} />;
}
