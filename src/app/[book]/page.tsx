import { redirect, notFound } from "next/navigation";
import { loadCatalog, loadNav } from "@/lib/book/load";

type PageProps = {
  params: Promise<{ book: string }>;
};

export function generateStaticParams() {
  return loadCatalog().books.flatMap((book) => {
    try {
      loadNav(book.id);
      return [{ book: book.id }];
    } catch {
      return [];
    }
  });
}

export async function generateMetadata({ params }: PageProps) {
  const { book } = await params;
  try {
    const nav = loadNav(book);
    return { title: nav.title };
  } catch {
    return { title: "DeepRead" };
  }
}

export default async function BookHome({ params }: PageProps) {
  const { book } = await params;
  const found = loadCatalog().books.find((item) => item.id === book);
  if (!found?.startSlug) notFound();
  redirect(`/${book}/${found.startSlug}`);
}
