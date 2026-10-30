/** Run in node_repl with a documented Browser tab handle. */
export async function captureArticle(tab, {selector, title, sourceUrl}) {
  if (!selector || !title || !sourceUrl) throw new Error('selector, title, sourceUrl required');
  if (await tab.url() !== sourceUrl) throw new Error('Tab changed; inspect it again');
  const root = tab.playwright.locator(selector);
  if (await root.count() !== 1) throw new Error('Selector must match one article');
  const blocks = await root.evaluate(el => Array.from(el.children)
    .filter(p => !['STYLE', 'SCRIPT'].includes(p.tagName))
    .map((p, index) => ({index, tag:p.tagName, html:p.innerHTML, text:p.textContent,
      code:p.tagName === 'PRE' ? {
        text:(p.querySelector('code') || p).textContent,
        language:p.querySelector('code')?.className.match(/language-([^\s]+)/)?.[1] || 'text'
      } : null,
      images:Array.from(p.querySelectorAll('img')).map(i => ({
        src:i.currentSrc || i.src, alt:i.alt, width:i.naturalWidth, height:i.naturalHeight
      }))
    })));
  if (!blocks.length) throw new Error('No article content; inspect loading/access');
  return {schema_version:1, title, source_url:sourceUrl, blocks};
}

/** Only actual rendered links matching a user-selected article/course prefix. */
export async function discoverLinks(tab, {selector, urlPrefix}) {
  return tab.playwright.locator(selector).evaluateAll((els, prefix) => {
    const seen = new Set();
    return els.filter(a => a.getClientRects().length > 0 && a.href?.startsWith(prefix))
      .filter(a => {if (seen.has(a.href)) return false; seen.add(a.href); return true;})
      .map(a => ({title:a.textContent.trim(), url:a.href}));
  }, urlPrefix);
}
