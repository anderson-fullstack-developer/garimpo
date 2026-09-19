import Link from "next/link";
import type { ReactNode } from "react";

import { Logo } from "@/components/logo";

export interface LegalSection {
  title: string;
  /** Parágrafos; um item que começa com "• " vira item de lista. */
  body: string[];
}

/**
 * Página de documento legal. O texto é sempre em inglês (versão única para todos os usuários) e
 * precisa de revisão jurídica antes da publicação: os campos [entre colchetes] são para preencher.
 */
export function LegalPage({
  title,
  updated,
  sections,
  footer,
}: {
  title: string;
  updated: string;
  sections: LegalSection[];
  footer?: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-10">
      <Link href="/" aria-label="Home">
        <Logo />
      </Link>
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="text-xs text-muted-foreground">Last updated: {updated}</p>
        <p
          role="note"
          className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-200"
        >
          Draft: this text is pending legal review. Items in [square brackets] must be completed
          before launch.
        </p>
      </div>

      <div className="space-y-6 text-sm leading-relaxed">
        {sections.map((section, index) => (
          <section key={section.title} className="space-y-2">
            <h2 className="text-base font-semibold">
              {index + 1}. {section.title}
            </h2>
            {groupParagraphs(section.body)}
          </section>
        ))}
      </div>
      {footer}
    </div>
  );
}

/** Junta itens "• ..." consecutivos numa lista. */
function groupParagraphs(lines: string[]): ReactNode[] {
  const out: ReactNode[] = [];
  let bullets: string[] = [];
  const flush = () => {
    if (bullets.length) {
      out.push(
        <ul key={`ul-${out.length}`} className="list-disc space-y-1 pl-5">
          {bullets.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>,
      );
      bullets = [];
    }
  };
  for (const line of lines) {
    if (line.startsWith("• ")) bullets.push(line.slice(2));
    else {
      flush();
      out.push(<p key={`p-${out.length}`}>{line}</p>);
    }
  }
  flush();
  return out;
}
