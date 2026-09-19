"use client";

import Link from "next/link";
import { Bell, Filter, Send, Zap } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { APP_NAME } from "@/config/brand";
import { pt } from "@/i18n/pt";
import { t } from "@/i18n/pt";

export function Landing() {
  const features = [
    { icon: Zap, title: pt.landing.feature1Title, text: pt.landing.feature1Text },
    { icon: Filter, title: pt.landing.feature2Title, text: pt.landing.feature2Text },
    { icon: Send, title: pt.landing.feature3Title, text: pt.landing.feature3Text },
  ];
  return (
    <div className="min-h-screen bg-background">
      <header className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-5">
        <Logo />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button asChild variant="ghost" size="sm">
            <Link href="/login">{pt.landing.ctaSecondary}</Link>
          </Button>
          <Button asChild size="sm">
            <Link href="/register">{pt.landing.ctaPrimary}</Link>
          </Button>
        </div>
      </header>

      <main>
        <section className="radar-glow px-4 py-16 text-center sm:py-24">
          <div className="mx-auto max-w-2xl space-y-6">
            <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
              <Bell className="size-3" aria-hidden /> {pt.landing.badge}
            </span>
            <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
              {pt.landing.heroTitle}
            </h1>
            <p className="text-base text-muted-foreground sm:text-lg">
              {t(pt.landing.heroSubtitle, { app: APP_NAME })}
            </p>
            <div className="flex flex-wrap justify-center gap-3">
              <Button asChild size="lg">
                <Link href="/register">{pt.landing.ctaPrimary}</Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link href="/login">{pt.landing.ctaSecondary}</Link>
              </Button>
            </div>
          </div>
        </section>

        <section className="mx-auto grid max-w-5xl gap-4 px-4 pb-20 sm:grid-cols-3">
          {features.map(({ icon: Icon, title, text }) => (
            <article key={title} className="surface p-6">
              <Icon className="size-5 text-primary" strokeWidth={1.75} aria-hidden />
              <h2 className="mt-4 text-base font-semibold">{title}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{text}</p>
            </article>
          ))}
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-4 py-6 text-sm text-muted-foreground">
          <span>
            © {new Date().getFullYear()} {APP_NAME}. {pt.landing.footerRights}
          </span>
          <nav className="flex gap-4">
            <Link href="/terms" className="hover:text-foreground">
              {pt.legal.terms}
            </Link>
            <Link href="/privacy" className="hover:text-foreground">
              {pt.legal.privacy}
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
