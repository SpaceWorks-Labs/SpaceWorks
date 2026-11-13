import type { HelpArticle } from "./helpTypes";

const fold = (value: string) => value.toLocaleLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");
const words = (value: string) => fold(value).split(/[^\p{L}\p{N}]+/u).filter(Boolean);

/** Plain text of a body for searching: Markdown punctuation and screenshot notes removed. */
function bodyText(body: string) {
  return body.replace(/!\[[^\]]*\]\([^)]*\)/g, " ").replace(/\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/[#>*`_-]/g, " ");
}

/**
 * Search ONLY the articles passed in: callers hand over what the reader may see, so a hidden
 * article can never surface as a result. Every query word must match the start of a word in
 * the article; matches in the title and keywords rank above matches in the body.
 */
export function searchHelp(articles: readonly HelpArticle[], query: string): HelpArticle[] {
  const terms = words(query);
  if (!terms.length) return [];
  const scored: { article: HelpArticle; score: number }[] = [];
  for (const article of articles) {
    const fields = [
      { weight: 8, tokens: words(article.title) },
      { weight: 5, tokens: article.keywords.flatMap(words) },
      { weight: 3, tokens: words(article.summary) },
      { weight: 1, tokens: words(bodyText(article.body)) },
    ];
    let score = 0;
    for (const term of terms) {
      const best = Math.max(0, ...fields.filter(field => field.tokens.some(token => token.startsWith(term))).map(field => field.weight));
      if (!best) { score = 0; break; }
      score += best;
    }
    if (score) scored.push({ article, score });
  }
  return scored.sort((a, b) => b.score - a.score || a.article.title.localeCompare(b.article.title)).map(entry => entry.article);
}
