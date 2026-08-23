import type { ReactNode } from "react";
import Link from "next/link";
import { Sidebar } from "@/components/book/sidebar";
import { ThemeToggle } from "@/components/book/theme-toggle";
import { loadNav } from "@/lib/book/load";

export function BookFrame({
  bookId,
  active,
  children,
}: {
  bookId: string;
  active: string;
  children: ReactNode;
}) {
  const nav = loadNav(bookId);
  const currentIndex = nav.pagesMeta.findIndex((page) => page.slug === active);
  const progress = currentIndex < 0 ? 0 : ((currentIndex + 1) / nav.pagesMeta.length) * 100;

  return (
    <div className="book-app" data-book={bookId}>
      <header className="book-topbar">
        <div className="flex min-w-0 items-center gap-3">
          <Link href="/" className="brand">
            DeepRead
          </Link>
          <span className="hidden text-mute sm:inline" aria-hidden="true">
            /
          </span>
          <p className="hidden truncate text-sm text-mute sm:block">{nav.title}</p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/" className="quiet-link">
            Library
          </Link>
          <ThemeToggle />
        </div>
        <span className="reading-progress" aria-hidden="true" style={{ width: `${progress}%` }} />
      </header>
      <div className="book-grid">
        <Sidebar bookId={bookId} tree={nav.tree} active={active} />
        <div className="book-main">{children}</div>
      </div>
    </div>
  );
}
