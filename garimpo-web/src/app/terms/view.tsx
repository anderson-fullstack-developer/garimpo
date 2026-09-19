"use client";

import { LegalPage, type LegalSection } from "@/features/legal/LegalPage";
import { APP_NAME } from "@/config/brand";

const OPERATOR = "[OPERATOR LEGAL NAME], [ADDRESS] ([the “Operator”, “we”, “us”])";

const SECTIONS: LegalSection[] = [
  {
    title: "Who we are and what this service is",
    body: [
      `${APP_NAME} is operated by ${OPERATOR}. Contact: [CONTACT EMAIL].`,
      `${APP_NAME} watches publicly visible listings on second-hand marketplaces, filters them with rules you define (“alerts”), and notifies you on Telegram. By creating an account or using the service you agree to these Terms. If you do not agree, do not use the service.`,
      `${APP_NAME} is an independent service. We are not affiliated with, endorsed by or sponsored by Vinted or any other marketplace. All trademarks belong to their owners.`,
    ],
  },
  {
    title: "Eligibility and your account",
    body: [
      "You must be at least 16 years old (or the age of digital consent in your country, if higher) and able to enter into a binding contract.",
      "You sign up with an email address (used only as your login name, we do not send email), a password and your country. We confirm that you are a real person by asking you to connect a private Telegram chat to your account.",
      "Each Telegram chat can be connected to one account only. You are responsible for keeping your password and your Telegram account secure, and for everything that happens under your account. Tell us at once if you suspect unauthorised use.",
      "Please provide accurate information. We may suspend accounts that use false details or that abuse the service.",
    ],
  },
  {
    title: "How the service works, and its limits",
    body: [
      "We check the marketplace at regular intervals and send you a message when a listing matches your alert. Speed depends on your alert (for example, searching one country is faster than searching all of Europe), your plan, the marketplace and Telegram.",
      "We do our best to notify you quickly, but we do not promise that every listing will be detected, that alerts will arrive within any specific time, or that the service will be uninterrupted or error-free. Marketplaces can change or block access at any time, which may stop or reduce the service.",
      "Listing information (title, price, condition, photos, posting time) comes from the marketplace and may be incomplete or inaccurate. The “published … ago” time is an estimate. Prices in other currencies are converted using public exchange rates and are indicative only. Titles may be machine-translated and can contain mistakes.",
    ],
  },
  {
    title: "Acceptable use",
    body: [
      "You agree not to:",
      "• use the service for anything unlawful, or to harass, defraud or mislead others;",
      "• attempt to overload, probe, scrape, reverse engineer or disrupt the service, or bypass limits of your plan;",
      "• create accounts in bulk, share your account, or resell or redistribute the service or its data without our written permission;",
      "• use the service in a way that breaks the terms of the marketplace you monitor. You are responsible for complying with those terms and for how you use the information you receive.",
      "We may limit, suspend or close accounts that break these rules, with or without notice where the law allows.",
    ],
  },
  {
    title: "Your purchases are between you and the seller",
    body: [
      `${APP_NAME} only tells you about listings. We are not a party to any sale, we do not check listings or sellers, and we are not responsible for the quality, legality, safety or availability of anything you find, or for your dealings with sellers or the marketplace. Take the usual precautions when buying second-hand items.`,
    ],
  },
  {
    title: "Plans and payment",
    body: [
      "The service may be offered free of charge during an early-access period and in different plans (for example, with different check speeds and limits). If we introduce paid plans, we will show the price, billing period and renewal terms before you pay, and we will not charge you without your clear agreement.",
      "Where the law gives you a right of withdrawal or other consumer rights, they are not affected by these Terms.",
    ],
  },
  {
    title: "Your content and our rights",
    body: [
      "You keep the rights to the alert settings and other content you enter. You give us permission to store and process them to run the service for you.",
      `The ${APP_NAME} software, design and branding belong to the Operator or its licensors. We give you a personal, revocable, non-transferable right to use the service under these Terms. Listing data belongs to its respective owners.`,
    ],
  },
  {
    title: "Privacy",
    body: [
      "Our Privacy Policy explains what personal data we process and your rights. It forms part of these Terms.",
    ],
  },
  {
    title: "Availability, changes and ending the service",
    body: [
      "We may change, suspend or discontinue features at any time. If we make a material change that harms you, we will give reasonable notice where possible.",
      "You can stop using the service and delete your account at any time in Settings → Account → Delete my account. We may close your account if you break these Terms or if we stop offering the service.",
    ],
  },
  {
    title: "Disclaimer and limitation of liability",
    body: [
      "The service is provided “as is” and “as available”. To the maximum extent permitted by law, we exclude all implied warranties and we are not liable for indirect or consequential losses, loss of profit, missed opportunities (for example, an item sold before you were notified), or losses caused by third parties such as the marketplace, Telegram or your internet provider.",
      "To the extent permitted by law, our total liability to you for any claim related to the service is limited to the amount you paid us in the 12 months before the event or EUR 100 if you paid nothing.",
      "Nothing in these Terms excludes or limits liability that cannot be excluded or limited by law, including liability for death or personal injury caused by negligence, for fraud, or for intentional misconduct, or your mandatory consumer rights.",
    ],
  },
  {
    title: "Changes to these Terms",
    body: [
      "We may update these Terms from time to time. We will post the new version here with a new date and, for material changes, notify you in the app. If you keep using the service after the change takes effect, you accept the new Terms; if you do not agree, please stop using the service and delete your account.",
    ],
  },
  {
    title: "Governing law and contact",
    body: [
      "These Terms are governed by the laws of [COUNTRY / JURISDICTION], without affecting the mandatory consumer protection rules of the country where you live. If you are a consumer in the European Union, you may also bring a claim in the courts of your country of residence.",
      "Questions about these Terms: [CONTACT EMAIL].",
    ],
  },
];

export function TermsPage() {
  return <LegalPage title="Terms of Service" updated="19 September 2026" sections={SECTIONS} />;
}
