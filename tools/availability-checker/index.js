/*
Availability checker using Playwright (Chromium)
- Proceeds as guest only
- Sets a representative ZIP per retailer (best-effort)
- Searches by Product ID first; if not found, tries GTIN
- Marks as Listed (Y/N) based on whether a product detail page exists or a non-sponsored search result resolves to a detail page
- Outputs CSV to availability_results.csv in this folder
*/

const fs = require('fs');
const path = require('path');
const { chromium, devices } = require('playwright');

/** Input items (deduplicated by key: Retailer|ProductID|GTIN) */
const RAW_ITEMS = [
  { market: 'US', retailer: 'AMAZON', productId: 'B000FKQDDI', gtin: '19000003058' },
  { market: 'US', retailer: 'AMAZON-FRESH', productId: 'B07BKDJ9XS', gtin: '40000525578' },
  { market: 'US', retailer: 'CVS', productId: '230355', gtin: '40000607410' },
  { market: 'US', retailer: 'GIANT-EAGLE', productId: '40000607359', gtin: '40000607359' },
  { market: 'US', retailer: 'GIANT-EAGLE', productId: '40000525509', gtin: '40000607410' },
  { market: 'US', retailer: 'GOPUFF', productId: '228282', gtin: '40000607410' },
  { market: 'US', retailer: 'HEB', productId: '15145015', gtin: '40000607410' },
  { market: 'US', retailer: 'HYVEE', productId: '2608138', gtin: '40000525509' },
  { market: 'US', retailer: 'HYVEE', productId: '2602336', gtin: '40000525578' },
  { market: 'US', retailer: 'INSTACART-PUBLIX', productId: '16295990', gtin: '19000083425' },
  { market: 'US', retailer: 'INSTACART-PUBLIX', productId: '78733', gtin: '19000083449' },
  { market: 'US', retailer: 'INSTACART-PUBLIX', productId: '20226744', gtin: '22000280282' },
  { market: 'US', retailer: 'INSTACART-PUBLIX', productId: '18339619', gtin: '40000525578' },
  { market: 'US', retailer: 'KROGER', productId: '4000052557', gtin: '40000525578' },
  { market: 'US', retailer: 'KROGER', productId: '4000052550', gtin: '40000525509' },
  { market: 'US', retailer: 'MEIJER', productId: 'P4000052550', gtin: '40000525509' },
  { market: 'US', retailer: 'MEIJER', productId: 'P4000052557', gtin: '40000525578' },
  { market: 'US', retailer: 'SAMS-CLUB', productId: '4000004432', gtin: '40000044321' },
  { market: 'US', retailer: 'SAMS-CLUB', productId: '15366017660', gtin: '22000104281' },
  { market: 'US', retailer: 'SHOPRITE', productId: '40000595786', gtin: '40000595786' },
  { market: 'US', retailer: 'SHOPRITE', productId: '00040000525509', gtin: '40000525509' },
  { market: 'US', retailer: 'SHOPRITE', productId: '22000297051', gtin: '22000297051' },
  { market: 'US', retailer: 'SHOPRITE', productId: '2200011693', gtin: '22000116932' },
  { market: 'US', retailer: 'SHOPRITE', productId: '00040000525578', gtin: '40000525578' },
  { market: 'US', retailer: 'SHOPRITE', productId: '40000598671', gtin: '40000598671' },
  { market: 'US', retailer: 'TARGET', productId: 'A-53280541', gtin: '40000525509' },
  { market: 'US', retailer: 'TARGET', productId: 'A-87620145', gtin: '40000525578' },
  { market: 'US', retailer: 'TARGET', productId: 'A-90037671', gtin: '22000297051' },
  { market: 'US', retailer: 'WALGREENS', productId: 'prod6381251', gtin: '40000525509' },
  { market: 'US', retailer: 'WALGREENS', productId: '300446423', gtin: '40000598671' },
  { market: 'US', retailer: 'WALGREENS', productId: 'PROD6381498', gtin: '40000525578' },
  { market: 'US', retailer: 'WALMART', productId: '578410887', gtin: '40000525509' },
];

/** Representative ZIP per retailer */
const RETAILER_ZIPS = {
  'AMAZON': '10001', // NYC
  'AMAZON-FRESH': '10001',
  'CVS': '20001', // Washington, DC
  'GIANT-EAGLE': '15222', // Pittsburgh, PA
  'GOPUFF': '10001', // NYC
  'HEB': '78701', // Austin, TX
  'HYVEE': '50309', // Des Moines, IA
  'INSTACART-PUBLIX': '33130', // Miami, FL
  'KROGER': '45202', // Cincinnati, OH
  'MEIJER': '49503', // Grand Rapids, MI
  'SAMS-CLUB': '30303', // Atlanta, GA
  'SHOPRITE': '07102', // Newark, NJ
  'TARGET': '10001',
  'WALGREENS': '20001', // DC
  'WALMART': '10001',
};

const MOBILE = devices['Pixel 7'];

function dedupeItems(items) {
  const seen = new Set();
  const deduped = [];
  for (const it of items) {
    const key = `${it.retailer}|${it.productId}|${it.gtin}`;
    if (!seen.has(key)) {
      seen.add(key);
      deduped.push(it);
    }
  }
  return deduped;
}

function csvEscape(val) {
  if (val == null) return '';
  const s = String(val);
  if (s.includes(',') || s.includes('"') || s.includes('\n')) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

async function safeClick(page, selector, opts = {}) {
  try {
    await page.waitForSelector(selector, { timeout: opts.timeout ?? 5000 });
    await page.click(selector, { delay: 50 });
    return true;
  } catch {
    return false;
  }
}

async function safeType(page, selector, text, opts = {}) {
  try {
    await page.waitForSelector(selector, { timeout: opts.timeout ?? 5000 });
    await page.fill(selector, '');
    await page.type(selector, text, { delay: 50 });
    return true;
  } catch {
    return false;
  }
}

async function setZipForDomain(page, retailer, zip) {
  // Best-effort ZIP setter per retailer/domain. Many sites gate with bot protection or login.
  try {
    switch (retailer) {
      case 'AMAZON':
      case 'AMAZON-FRESH': {
        await page.goto('https://www.amazon.com/', { waitUntil: 'domcontentloaded', timeout: 30000 });
        // Try the location popover
        const opened = await safeClick(page, '#glow-ingress-block, #nav-global-location-popover-link, #nav-global-location-data-modal-action');
        if (opened) {
          // New GLUX modal sometimes uses input[name=pincode] or #GLUXZipUpdateInput
          const typed = await safeType(page, '#GLUXZipUpdateInput, input[name="zipCode"], input[name="pincode"]', zip);
          if (typed) {
            await page.keyboard.press('Enter');
            await page.waitForTimeout(2000);
            // Sometimes a "Continue" button appears
            await safeClick(page, 'input[name="glowDoneButton"], .a-button-input');
            await page.waitForTimeout(1000);
          }
        }
        break;
      }
      case 'TARGET': {
        await page.goto('https://www.target.com', { waitUntil: 'domcontentloaded', timeout: 30000 });
        // Try change zip dialog
        const opened = await safeClick(page, '[data-test="storeFulfillmentContainer"] button, button[data-test="storeFulfillmentLink"]');
        if (opened) {
          const typed = await safeType(page, 'input#zip-code, input[name="zipCode"], input[aria-label="Zip code"]', zip);
          if (typed) {
            await page.keyboard.press('Enter');
            await page.waitForTimeout(2000);
          }
        }
        break;
      }
      case 'WALGREENS': {
        await page.goto('https://www.walgreens.com', { waitUntil: 'domcontentloaded', timeout: 30000 });
        // Open location modal
        const opened = await safeClick(page, '#user_location_toggle, button[aria-label*="delivery" i], button[aria-label*="pickup" i]');
        if (opened) {
          const typed = await safeType(page, 'input#user_location, input[name="zip"]', zip);
          if (typed) {
            await page.keyboard.press('Enter');
            await page.waitForTimeout(2000);
          }
        }
        break;
      }
      case 'WALMART': {
        await page.goto('https://www.walmart.com', { waitUntil: 'domcontentloaded', timeout: 30000 });
        // Try location selector
        const opened = await safeClick(page, 'button[aria-label*="location" i], button[aria-label*="address" i], button:has-text("location" i)');
        if (opened) {
          const typed = await safeType(page, 'input[aria-label*="ZIP" i], input[name="zip"]', zip);
          if (typed) {
            await page.keyboard.press('Enter');
            await page.waitForTimeout(2000);
          }
        }
        break;
      }
      case 'HEB': {
        await page.goto('https://www.heb.com', { waitUntil: 'domcontentloaded', timeout: 30000 });
        // HEB location is store-based; best-effort zip in search bar store selector
        await page.waitForTimeout(1000);
        break;
      }
      case 'KROGER': {
        await page.goto('https://www.kroger.com', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(1000);
        break;
      }
      case 'MEIJER': {
        await page.goto('https://www.meijer.com', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(1000);
        break;
      }
      case 'SHOPRITE': {
        await page.goto('https://shop.shoprite.com', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(1000);
        break;
      }
      case 'GIANT-EAGLE': {
        await page.goto('https://www.gianteagle.com', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(1000);
        break;
      }
      case 'HYVEE': {
        await page.goto('https://www.hy-vee.com', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(1000);
        break;
      }
      case 'GOPUFF': {
        await page.goto('https://www.gopuff.com', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(1000);
        break;
      }
      case 'SAMS-CLUB': {
        await page.goto('https://www.samsclub.com', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(1000);
        break;
      }
      case 'INSTACART-PUBLIX': {
        await page.goto('https://www.instacart.com/store/publix', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(1000);
        break;
      }
      default:
        break;
    }
    return true;
  } catch (err) {
    return false;
  }
}

async function openFirstNonSponsoredResult(page) {
  // Heuristic: click first result card that links to a product detail page. Sites vary widely.
  const selectors = [
    'a[href*="/p/"]', // Target
    'a[href*="/product/"]', // Walgreens, HEB
    'a[href*="/ip/"]', // Walmart
    'a[href*="/product-detail"], a[href*="/product-detail/"]', // HEB
    'a[href*="/pd/"]', // Kroger
    'a[href*="/shopping/product" i]', // Meijer
    'a[href*="/product/" i]', // generic
  ];
  for (const sel of selectors) {
    const handles = await page.$$(sel);
    for (const handle of handles) {
      // Attempt to skip sponsored by common markers
      const isSponsored = await handle.evaluate((a) => {
        const card = a.closest('[data-sponsored], [aria-label*="Sponsored" i], [data-test*="sponsored" i]');
        if (card) return true;
        // Check text nearby
        const text = (a.textContent || '').toLowerCase();
        if (text.includes('sponsored')) return true;
        return false;
      }).catch(() => false);
      if (isSponsored) continue;
      await handle.click({ button: 'left' });
      await page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => {});
      return true;
    }
  }
  return false;
}

async function retailerAmazon(page, item, zip) {
  // Try to set ZIP (best-effort), then go to dp page.
  await setZipForDomain(page, 'AMAZON', zip);
  const url = `https://www.amazon.com/dp/${item.productId}`;
  const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => null);
  const status = resp?.status();
  let found = false;
  let title = '';
  if (status && status < 400) {
    found = true;
    try {
      title = await page.title();
    } catch {}
  } else {
    // fallback to mobile detail
    const murl = `https://www.amazon.com/gp/aw/d/${item.productId}`;
    const mresp = await page.goto(murl, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => null);
    if (mresp && mresp.status() < 400) {
      found = true;
      title = await page.title().catch(() => '');
    }
  }
  return { found, url: page.url(), title, price: '', notes: status ? `HTTP ${status}` : 'no response' };
}

async function retailerAmazonFresh(page, item, zip) {
  await setZipForDomain(page, 'AMAZON-FRESH', zip);
  const murl = `https://www.amazon.com/gp/aw/d/${item.productId}`;
  const resp = await page.goto(murl, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => null);
  const status = resp?.status();
  const found = !!(status && status < 400);
  return { found, url: page.url(), title: await page.title().catch(() => ''), price: '', notes: status ? `HTTP ${status}` : 'no response' };
}

async function retailerTarget(page, item, zip) {
  await setZipForDomain(page, 'TARGET', zip);
  const id = (item.productId || '').replace(/^A-/, '');
  const url = `https://www.target.com/p/-/A-${id}`;
  const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => null);
  const status = resp?.status();
  const found = !!(status && status < 400 && status !== 404);
  let title = '';
  try { title = await page.title(); } catch {}
  return { found, url: page.url(), title, price: '', notes: status ? `HTTP ${status}` : 'no response' };
}

async function retailerWalgreens(page, item, zip) {
  await setZipForDomain(page, 'WALGREENS', zip);
  const search = `https://www.walgreens.com/search/results.jsp?Ntt=${encodeURIComponent(item.productId)}`;
  await page.goto(search, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
  // Click first non-sponsored result
  await page.waitForTimeout(2000);
  const clicked = await openFirstNonSponsoredResult(page);
  let found = false; let title = ''; let url = page.url();
  if (clicked) {
    await page.waitForTimeout(2000);
    title = await page.title().catch(() => '');
    url = page.url();
    found = true;
  } else {
    // Try GTIN search if ID failed
    const search2 = `https://www.walgreens.com/search/results.jsp?Ntt=${encodeURIComponent(item.gtin)}`;
    await page.goto(search2, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2000);
    if (await openFirstNonSponsoredResult(page)) {
      await page.waitForTimeout(2000);
      title = await page.title().catch(() => '');
      url = page.url();
      found = true;
    }
  }
  return { found, url, title, price: '', notes: clicked ? 'from ID' : 'from GTIN or not found' };
}

async function retailerWalmart(page, item, zip) {
  await setZipForDomain(page, 'WALMART', zip);
  const url = `https://www.walmart.com/ip/${item.productId}`;
  const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => null);
  const status = resp?.status();
  let found = false; let title = '';
  if (status && status < 400) {
    title = await page.title().catch(() => '');
    const currentUrl = page.url();
    const blocked = /\/blocked|are-you-human/i.test(currentUrl) || /robot or human\?/i.test(title);
    found = !blocked;
  }
  return { found, url: page.url(), title, price: '', notes: status ? `HTTP ${status}` : 'no response' };
}

async function retailerHEB(page, item, zip) {
  await setZipForDomain(page, 'HEB', zip);
  const url = `https://www.heb.com/product-detail/${item.productId}`;
  const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => null);
  const status = resp?.status();
  const found = !!(status && status < 400 && status !== 404);
  const title = await page.title().catch(() => '');
  return { found, url: page.url(), title, price: '', notes: status ? `HTTP ${status}` : 'no response' };
}

async function retailerGiantEagle(page, item, zip) {
  await setZipForDomain(page, 'GIANT-EAGLE', zip);
  const search = `https://www.gianteagle.com/search?q=${encodeURIComponent(item.productId)}`;
  await page.goto(search, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(2000);
  let found = false; let title = ''; let url = page.url();
  if (await openFirstNonSponsoredResult(page)) {
    await page.waitForTimeout(2000);
    title = await page.title().catch(() => '');
    url = page.url();
    found = true;
  } else {
    const search2 = `https://www.gianteagle.com/search?q=${encodeURIComponent(item.gtin)}`;
    await page.goto(search2, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2000);
    if (await openFirstNonSponsoredResult(page)) {
      await page.waitForTimeout(2000);
      title = await page.title().catch(() => '');
      url = page.url();
      found = true;
    }
  }
  return { found, url, title, price: '', notes: 'search-based' };
}

async function retailerHyVee(page, item, zip) {
  await setZipForDomain(page, 'HYVEE', zip);
  const search = `https://www.hy-vee.com/grocery/search?text=${encodeURIComponent(item.productId)}`;
  await page.goto(search, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(2500);
  let found = false; let title = ''; let url = page.url();
  if (await openFirstNonSponsoredResult(page)) {
    await page.waitForTimeout(2000);
    title = await page.title().catch(() => '');
    url = page.url();
    found = true;
  } else {
    const search2 = `https://www.hy-vee.com/grocery/search?text=${encodeURIComponent(item.gtin)}`;
    await page.goto(search2, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2000);
    if (await openFirstNonSponsoredResult(page)) {
      await page.waitForTimeout(2000);
      title = await page.title().catch(() => '');
      url = page.url();
      found = true;
    }
  }
  return { found, url, title, price: '', notes: 'search-based' };
}

async function retailerGopuff(page, item, zip) {
  await setZipForDomain(page, 'GOPUFF', zip);
  const search = `https://www.gopuff.com/search?query=${encodeURIComponent(item.productId)}`;
  await page.goto(search, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(2000);
  let found = false; let title = ''; let url = page.url();
  if (await openFirstNonSponsoredResult(page)) {
    await page.waitForTimeout(1500);
    title = await page.title().catch(() => '');
    url = page.url();
    found = true;
  } else {
    const search2 = `https://www.gopuff.com/search?query=${encodeURIComponent(item.gtin)}`;
    await page.goto(search2, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(1500);
    if (await openFirstNonSponsoredResult(page)) {
      await page.waitForTimeout(1500);
      title = await page.title().catch(() => '');
      url = page.url();
      found = true;
    }
  }
  return { found, url, title, price: '', notes: 'search-based' };
}

async function retailerCVS(page, item, zip) {
  await setZipForDomain(page, 'CVS', zip);
  const search = `https://www.cvs.com/search?searchTerm=${encodeURIComponent(item.productId)}`;
  await page.goto(search, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(2500);
  let found = false; let title = ''; let url = page.url();
  if (await openFirstNonSponsoredResult(page)) {
    await page.waitForTimeout(2000);
    title = await page.title().catch(() => '');
    url = page.url();
    found = true;
  } else {
    const search2 = `https://www.cvs.com/search?searchTerm=${encodeURIComponent(item.gtin)}`;
    await page.goto(search2, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2000);
    if (await openFirstNonSponsoredResult(page)) {
      await page.waitForTimeout(2000);
      title = await page.title().catch(() => '');
      url = page.url();
      found = true;
    }
  }
  return { found, url, title, price: '', notes: 'search-based' };
}

async function retailerKroger(page, item, zip) {
  await setZipForDomain(page, 'KROGER', zip);
  const candidates = [item.productId, item.gtin, item.gtin && item.gtin.length === 11 ? '0' + item.gtin : ''];
  let found = false; let title = ''; let url = '';
  for (const q of candidates.filter(Boolean)) {
    const search = `https://www.kroger.com/search?query=${encodeURIComponent(q)}`;
    await page.goto(search, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2500);
    if (await openFirstNonSponsoredResult(page)) {
      await page.waitForTimeout(2000);
      title = await page.title().catch(() => '');
      url = page.url();
      found = true; break;
    }
  }
  return { found, url: url || page.url(), title, price: '', notes: 'search-based' };
}

async function retailerMeijer(page, item, zip) {
  await setZipForDomain(page, 'MEIJER', zip);
  const candidates = [item.productId, item.gtin];
  let found = false; let title = ''; let url = '';
  for (const q of candidates.filter(Boolean)) {
    const search = `https://www.meijer.com/shopping/search.html?q=${encodeURIComponent(q)}`;
    await page.goto(search, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2500);
    if (await openFirstNonSponsoredResult(page)) {
      await page.waitForTimeout(2000);
      title = await page.title().catch(() => '');
      url = page.url();
      found = true; break;
    }
  }
  return { found, url: url || page.url(), title, price: '', notes: 'search-based' };
}

async function retailerSamsClub(page, item, zip) {
  await setZipForDomain(page, 'SAMS-CLUB', zip);
  const candidates = [item.productId, item.gtin];
  let found = false; let title = ''; let url = '';
  for (const q of candidates.filter(Boolean)) {
    const search = `https://www.samsclub.com/s/${encodeURIComponent(q)}`;
    await page.goto(search, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2500);
    if (await openFirstNonSponsoredResult(page)) {
      await page.waitForTimeout(2000);
      title = await page.title().catch(() => '');
      url = page.url();
      found = true; break;
    }
  }
  return { found, url: url || page.url(), title, price: '', notes: 'search-based' };
}

async function retailerShopRite(page, item, zip) {
  await setZipForDomain(page, 'SHOPRITE', zip);
  const candidates = [item.productId, item.gtin];
  let found = false; let title = ''; let url = '';
  for (const q of candidates.filter(Boolean)) {
    const search = `https://shop.shoprite.com/search?searchText=${encodeURIComponent(q)}`;
    await page.goto(search, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2500);
    if (await openFirstNonSponsoredResult(page)) {
      await page.waitForTimeout(2000);
      title = await page.title().catch(() => '');
      url = page.url();
      found = true; break;
    }
  }
  return { found, url: url || page.url(), title, price: '', notes: 'search-based' };
}

async function retailerInstacartPublix(page, item, zip) {
  // Instacart typically requires login; best-effort guest search
  await setZipForDomain(page, 'INSTACART-PUBLIX', zip);
  const search = `https://www.instacart.com/store/publix/search?q=${encodeURIComponent(item.productId)}`;
  await page.goto(search, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(2500);
  let found = false; let title = ''; let url = page.url();
  if (await openFirstNonSponsoredResult(page)) {
    await page.waitForTimeout(2000);
    title = await page.title().catch(() => '');
    url = page.url();
    found = true;
  } else {
    const search2 = `https://www.instacart.com/store/publix/search?q=${encodeURIComponent(item.gtin)}`;
    await page.goto(search2, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2000);
    if (await openFirstNonSponsoredResult(page)) {
      await page.waitForTimeout(2000);
      title = await page.title().catch(() => '');
      url = page.url();
      found = true;
    }
  }
  return { found, url, title, price: '', notes: 'login may be required' };
}

const HANDLERS = {
  'AMAZON': retailerAmazon,
  'AMAZON-FRESH': retailerAmazonFresh,
  'TARGET': retailerTarget,
  'WALGREENS': retailerWalgreens,
  'WALMART': retailerWalmart,
  'HEB': retailerHEB,
  'GIANT-EAGLE': retailerGiantEagle,
  'HYVEE': retailerHyVee,
  'GOPUFF': retailerGopuff,
  'CVS': retailerCVS,
  'KROGER': retailerKroger,
  'MEIJER': retailerMeijer,
  'SAMS-CLUB': retailerSamsClub,
  'SHOPRITE': retailerShopRite,
  'INSTACART-PUBLIX': retailerInstacartPublix,
};

async function main() {
  const items = dedupeItems(RAW_ITEMS);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    ...MOBILE, // mobile device profile to reduce bot friction
    userAgent: MOBILE.userAgent.replace('Chrome/112.0.5615.49', 'Chrome/124.0.0.0'),
    locale: 'en-US',
    colorScheme: 'light',
    timezoneId: 'America/New_York',
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30000);

  const rows = [];
  rows.push(['Market','Retailer','Product ID','GTIN','Found (Y/N)','Availability status','Product title','Size/variant','Price','URL checked','ZIP used','Notes']);

  for (const item of items) {
    const zip = RETAILER_ZIPS[item.retailer] || '20001';
    const handler = HANDLERS[item.retailer];
    if (!handler) {
      rows.push([item.market, item.retailer, item.productId, item.gtin, 'N', 'Not checked', '', '', '', '', zip, 'No handler']);
      continue;
    }
    let result = { found: false, url: '', title: '', price: '', notes: '' };
    try {
      result = await handler(page, item, zip);
    } catch (err) {
      result = { found: false, url: page.url(), title: '', price: '', notes: `error: ${err?.message || err}` };
    }
    const row = [
      item.market,
      item.retailer,
      item.productId,
      item.gtin,
      result.found ? 'Y' : 'N',
      result.found ? 'Listed' : 'Not listed',
      result.title || '',
      '', // Size/variant not reliably parsed in this version
      result.price || '',
      result.url || '',
      zip,
      result.notes || '',
    ];
    rows.push(row);
    // Small pause between retailers to be polite
    await page.waitForTimeout(800);
  }

  await browser.close();

  const csv = rows.map(r => r.map(csvEscape).join(',')).join('\n');
  const outPath = path.join(__dirname, 'availability_results.csv');
  fs.writeFileSync(outPath, csv, 'utf8');
  console.log(`Wrote ${rows.length - 1} results to ${outPath}`);
}

if (require.main === module) {
  main().catch(err => {
    console.error(err);
    process.exit(1);
  });
}
