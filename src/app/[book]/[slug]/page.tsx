import { notFound } from "next/navigation";
import { HashRedirect } from "@/components/book/book-reader";
import { loadCatalog, loadNav, loadPage } from "@/lib/book/load";

type PageProps = {
  params: Promise<{ book: string; slug: string }>;
};

export function generateStaticParams() {
  return loadCatalog().books.flatMap((book) => {
    try {
      const nav = loadNav(book.id);
      return nav.pagesMeta.map((page) => ({ book: book.id, slug: page.slug }));
    } catch {
      return [];
    }
  });
}

export async function generateMetadata({ params }: PageProps) {
  const { book, slug } = await params;
  try {
    const page = loadPage(book, slug);
    const nav = loadNav(book);
    return { title: page ? `${page.title} · ${nav.title}` : nav.title };
  } catch {
    return { title: "DeepRead" };
  }
}

export default async function LegacySectionPage({ params }: PageProps) {
  const { book, slug } = await params;
  if (!loadCatalog().books.some((item) => item.id === book)) notFound();
  const page = loadPage(book, slug);
  if (!page) notFound();
  const href = `/${book}#${slug}`;
  return (
    <>
      <HashRedirect href={href} />
      <p className="p-8">
        <a href={href}>Continue to this section</a>
      </p>
    </>
  );
}
