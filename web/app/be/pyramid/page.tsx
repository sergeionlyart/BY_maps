import type { Metadata } from 'next';
import { loadContent } from '@/lib/content';
import { parsePyramidContent } from '@/lib/pyramidContent';
import { authors, altFor } from '@/lib/seo';
import PyramidBody from '@/components/PyramidBody';

const content = loadContent('be', 'pyramid');

export const metadata: Metadata = {
  alternates: altFor('/be/pyramid'),
  authors,
  title: content.title,
  description: content.description,
};

export default function PyramidPageBe() {
  return <PyramidBody parsed={parsePyramidContent(content.body)} />;
}
