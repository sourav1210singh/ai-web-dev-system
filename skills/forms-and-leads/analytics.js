/**
 * Do the tags on this page actually fire, once, without the lead's data?
 *
 *   node analytics.js <url> [--out <dir>] [--width 390]
 *                           [--click "<css selector>"] [--consent]
 *
 * A tag in the source is not a tag that fired, and a tag that fired twice is
 * worse than one that did not: the client's reports read double and every
 * decision taken off them is wrong. Delivery of a lead is already checked
 * elsewhere; this checks the half the client actually looks at.
 *
 * It watches the network rather than reading the markup, because the markup
 * says what was intended and the network says what happened.
 *
 * **It only observes.** Nothing is clicked or submitted unless you pass
 * `--click`, and that is for a page you have been told you may exercise. Never
 * fire a real submission on a live client form to test a tag.
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

function loadPlaywright() {
  try { return require("playwright"); } catch { /* keep looking */ }
  const roots = [process.env.NODE_PATH];
  try { roots.push(execSync("npm root -g", { encoding: "utf8" }).trim()); } catch { /* ignore */ }
  roots.push(path.join(process.env.APPDATA || "", "npm", "node_modules"));
  for (const r of roots) {
    if (r && fs.existsSync(path.join(r, "playwright"))) return require(path.join(r, "playwright"));
  }
  console.error("playwright not found; it is installed globally here and a bare\n" +
                "require() does not resolve a global module.");
  process.exit(2);
}

// What a request to each of these means. Loading the library is not the same
// as sending a hit, so the two are kept apart.
const VENDORS = [
  { id: "ga4", name: "Google Analytics 4", hit: /google-analytics\.com\/(g\/)?collect|analytics\.google\.com\/g\/collect|\/g\/collect\?/i, lib: /googletagmanager\.com\/gtag\/js/i },
  { id: "gtm", name: "Google Tag Manager", hit: /googletagmanager\.com\/gtm\.js/i, lib: /googletagmanager\.com\/gtm\.js/i },
  { id: "gads", name: "Google Ads", hit: /googleadservices\.com|google\.[a-z.]+\/pagead|\/ads\/ga-audiences/i, lib: /googleadservices\.com\/pagead\/conversion/i },
  { id: "meta", name: "Meta pixel", hit: /facebook\.com\/tr\b/i, lib: /connect\.facebook\.net/i },
  { id: "linkedin", name: "LinkedIn Insight", hit: /px\.ads\.linkedin\.com/i, lib: /snap\.licdn\.com/i },
  { id: "bing", name: "Microsoft Ads UET", hit: /bat\.bing\.com\/action/i, lib: /bat\.bing\.com\/bat\.js/i },
  { id: "clarity", name: "Microsoft Clarity", hit: /clarity\.ms\/collect/i, lib: /clarity\.ms\/tag/i },
  { id: "hotjar", name: "Hotjar", hit: /hotjar\.(com|io)\/api/i, lib: /static\.hotjar\.com/i },
  { id: "tiktok", name: "TikTok pixel", hit: /analytics\.tiktok\.com\/api/i, lib: /analytics\.tiktok\.com\/i18n/i },
  { id: "pinterest", name: "Pinterest tag", hit: /ct\.pinterest\.com/i, lib: /s\.pinimg\.com/i },
  { id: "segment", name: "Segment", hit: /api\.segment\.io/i, lib: /cdn\.segment\.com/i },
  { id: "plausible", name: "Plausible", hit: /plausible\.io\/api\/event/i, lib: /plausible\.io\/js/i },
  { id: "fathom", name: "Fathom", hit: /cdn\.usefathom\.com\/\?/i, lib: /cdn\.usefathom\.com\/script/i },
];

// A lead's own data, which must never leave in one of these.
const EMAIL = /[\w.+-]+%40[\w-]+(\.[\w-]+)+|[\w.+-]+@[\w-]+(\.[\w-]+)+/;
const PHONE = /(?:^|[^\d])(\+?\d[\d\s().-]{8,16}\d)(?:[^\d]|$)/;
const HASHED = /\b[a-f0-9]{64}\b/i;

const PARAM_NAMES = /\b(em|ph|fn|ln|ct|zp|user_email|email|phone|tel|name|first_name|last_name|message)\b/i;

function vendorOf(url) {
  for (const v of VENDORS) {
    if (v.hit.test(url)) return { ...v, kind: "hit" };
  }
  for (const v of VENDORS) {
    if (v.lib.test(url)) return { ...v, kind: "lib" };
  }
  return null;
}

/** The GA4 measurement id a hit was sent to, which is how doubles are seen. */
function measurementId(url) {
  const m = /[?&]tid=([^&]+)/.exec(url);
  return m ? decodeURIComponent(m[1]) : null;
}

function eventName(url, body) {
  const m = /[?&]en=([^&]+)/.exec(url);
  if (m) return decodeURIComponent(m[1]);
  const b = /[?&]ev=([^&]+)/.exec(url);
  if (b) return decodeURIComponent(b[1]);
  if (body) {
    const e = /"event"\s*:\s*"([^"]+)"/.exec(body);
    if (e) return e[1];
  }
  return null;
}

/**
 * Personal data on its way out.
 *
 * Checked on the whole request - the query string and the body - because a
 * pixel will take either, and the rule is the same for both: the event name
 * and nothing else.
 */
function personalData(url, body) {
  const found = [];
  const hay = url + "\n" + (body || "");
  if (EMAIL.test(hay)) found.push({ what: "an email address", sev: "BLOCKER" });
  const ph = PHONE.exec(hay.replace(/\b\d{10,}\b(?=&|$)/g, ""));
  if (ph && !/\btid=|\bcid=|\b_p=|\bsid=/.test(ph[0])) {
    found.push({ what: "something shaped like a phone number: " + ph[1].trim(),
                 sev: "CHECK" });
  }
  if (HASHED.test(hay)) {
    found.push({
      what: "a sha256 hash, which is how advanced matching sends a customer's " +
            "email or phone. It is not plaintext, and it is still the lead's " +
            "data leaving for an ads platform",
      sev: "MAJOR" });
  }
  const names = [];
  for (const m of hay.matchAll(/[?&]([a-z_]{2,20})=([^&\s]{2,})/gi)) {
    if (PARAM_NAMES.test(m[1]) && m[2].length > 2) names.push(m[1]);
  }
  if (names.length) {
    found.push({ what: "parameters named " + [...new Set(names)].slice(0, 5).join(", "),
                 sev: "MAJOR" });
  }
  return found;
}

/** What the page declares, read out of its own scripts. */
const DECLARED = () => {
  const html = document.documentElement.outerHTML;
  const uniq = (rx) => [...new Set([...html.matchAll(rx)].map((m) => m[1]))];
  const consent = /gtag\(\s*['"]consent['"]\s*,\s*['"]default['"]/.test(html);
  const denied = /analytics_storage['"]\s*:\s*['"]denied['"]/.test(html);
  const update = /gtag\(\s*['"]consent['"]\s*,\s*['"]update['"]/.test(html);
  return {
    ga4: uniq(/\b(G-[A-Z0-9]{6,})\b/g),
    gtm: uniq(/\b(GTM-[A-Z0-9]{5,})\b/g),
    ads: uniq(/\b(AW-[0-9]{6,})\b/g),
    ua: uniq(/\b(UA-\d{4,}-\d+)\b/g),
    meta: uniq(/fbq\(\s*['"]init['"]\s*,\s*['"](\d{6,})['"]/g),
    consentDefault: consent, analyticsDenied: denied, consentUpdate: update,
    dataLayer: typeof window.dataLayer !== "undefined",
  };
};

/**
 * Everything on this page a visitor could convert through.
 *
 * Checking which tags fire answers half the question. The other half is what
 * *should* fire, and nothing was looking at it: a site can have a clean
 * analytics report and leave the phone number, the WhatsApp button and the
 * booking link untracked, so the client's "conversions" are the forms only and
 * the number is wrong in a direction nobody questions.
 */
const SURFACE = () => {
  const list = (sel) => Array.from(document.querySelectorAll(sel));
  const txt = (e) => (e.innerText || e.textContent || "").replace(/\s+/g, " ")
    .trim().slice(0, 50);
  const scripts = Array.from(document.querySelectorAll("script"))
    .map((s) => s.textContent || "").join("\n");

  // Form plugins, because each one needs a different success signal.
  const forms = {
    elementor: list("form.elementor-form").length,
    cf7: list("form.wpcf7-form").length,
    wpforms: list("form.wpforms-form").length,
    gravity: list('form[id^="gform_"]').length,
    ninja: list(".nf-form-cont").length,
    hubspot: list('.hs-form, form[data-form-id]').length,
    other: list("form").filter((f) => !f.closest(
      '[class*="elementor"],[class*="wpforms"],[class*="wpcf7"],[id^="gform"],'
      + '.nf-form-cont,.hs-form')).length,
  };

  return {
    tel: list('a[href^="tel:"]').map((e) => txt(e) || e.getAttribute("href")),
    whatsapp: list('a[href*="wa.me"],a[href*="api.whatsapp"],a[href*="whatsapp://"]').length,
    mailto: list('a[href^="mailto:"]').length,
    forms,
    cta: list('[id*="popup"],[class*="popup-trigger"],[data-toggle="modal"],'
      + '[data-bs-toggle="modal"],[data-micromodal-trigger],[class*="popmake"],'
      + '.pum-trigger,[data-open]').length,
    cart: list('button[name="add"],.add_to_cart_button,[data-action="add-to-cart"],'
      + '[class*="add-to-cart"],.product-form__submit').length,
    booking: list('a[href*="calendly"],a[href*="acuityscheduling"],a[href*="setmore"],'
      + 'a[href*="simplybook"],[class*="calendly"]').length,
    downloads: list('a[href$=".pdf"],a[href$=".doc"],a[href$=".docx"],a[href$=".zip"]').length,
    video: list('iframe[src*="youtube"],iframe[src*="youtu.be"],iframe[src*="vimeo"],video').length,
    social: list('a[href*="facebook.com"],a[href*="instagram.com"],a[href*="linkedin.com"],'
      + 'a[href*="tiktok.com"],a[href*="youtube.com"]').length,
    chat: Object.entries({
      tidio: !!document.querySelector('[id*="tidio"]'),
      intercom: !!(window.Intercom || document.querySelector("#intercom-container")),
      drift: !!(window.drift || document.querySelector("#drift-widget")),
      tawk: !!(window.Tawk_API || document.querySelector("#tawk-widget")),
      zendesk: !!(window.zE || document.querySelector('[id*="zendesk"]')),
      crisp: !!(window.$crisp || document.querySelector(".crisp-client")),
      freshchat: !!(window.fcWidget || document.querySelector("#fc_frame")),
    }).filter(([, on]) => on).map(([k]) => k),
    // Which AJAX success signals anything on the page is actually listening
    // for. GTM injects its custom HTML into the page, so a listener installed
    // through a tag shows up here too.
    listeners: {
      elementor: /elementor-message-success/.test(scripts),
      cf7: /wpcf7mailsent/.test(scripts),
      wpforms: /wpformsAjaxSubmitSuccess/.test(scripts),
      gravity: /gform_confirmation_loaded/.test(scripts),
      ninja: /nfFormSubmitResponse/.test(scripts),
      hubspot: /hsFormCallback/.test(scripts),
      calendly: /calendly\.event_scheduled/.test(scripts),
    },
  };
};

// Each AJAX form plugin shows success without a page load, so a native GTM
// Form Submission trigger either never fires or fires on a failed submit.
const AJAX_FORMS = [
  ["elementor", "Elementor", "a MutationObserver on .elementor-message-success"],
  ["cf7", "Contact Form 7", "the wpcf7mailsent event"],
  ["wpforms", "WPForms", "the wpformsAjaxSubmitSuccess event"],
  ["gravity", "Gravity Forms", "the gform_confirmation_loaded event"],
  ["ninja", "Ninja Forms", "the native nfFormSubmitResponse dataLayer event"],
  ["hubspot", "HubSpot", "the hsFormCallback message event"],
];

/** What could convert here, against what is set up to notice it. */
function surfaceFindings(s, declared) {
  const f = [];
  if (!s) return f;
  const add = (sev, title, detail) => f.push({ sev, title, detail });

  const actions = [];
  if ((s.tel || []).length) actions.push("phone (" + s.tel.length + ")");
  if (s.whatsapp) actions.push("WhatsApp (" + s.whatsapp + ")");
  if (s.mailto) actions.push("mailto (" + s.mailto + ")");
  const formCount = Object.values(s.forms || {}).reduce((a, b) => a + b, 0);
  if (formCount) actions.push("forms (" + formCount + ")");
  if (s.cart) actions.push("add to cart (" + s.cart + ")");
  if (s.booking) actions.push("booking link (" + s.booking + ")");
  if (s.cta) actions.push("popup or CTA trigger (" + s.cta + ")");
  if (s.downloads) actions.push("file download (" + s.downloads + ")");
  if ((s.chat || []).length) actions.push("chat widget (" + s.chat.join(", ") + ")");
  if (s.video) actions.push("video (" + s.video + ")");

  const tagged = (declared && ((declared.gtm || []).length
    || (declared.ga4 || []).length)) || false;
  if (actions.length && !tagged) {
    add("BLOCKER", actions.length + " conversion action(s) on the page and no "
        + "analytics at all", actions.join("; ")
        + " - none of it can be recorded.");
  } else if (actions.length) {
    add("NOTE", actions.length + " conversion action(s) found on this page",
        actions.join("; ") + ". A page load cannot tell you which of these "
        + "fire, because they fire on click. Exercise each one with --click, "
        + "or read GA4 Realtime.");
  }

  for (const [key, name, how] of AJAX_FORMS) {
    if (!(s.forms || {})[key]) continue;
    if ((s.listeners || {})[key]) continue;
    add("MAJOR", name + " form with no success listener on the page",
        "It submits without a page load, so a native Form Submission trigger "
        + "either never fires or fires on a failed submit. It needs " + how
        + " pushing to the dataLayer. Nothing on this page listens for it - "
        + "check the GTM container before concluding it is missing.");
  }
  if (s.booking && !(s.listeners || {}).calendly
      && /calendly/i.test(JSON.stringify(s))) {
    add("MINOR", "A booking link with no booking listener",
        "Calendly confirms inside its own iframe, so the click is trackable "
        + "and the booking is not, unless calendly.event_scheduled is handled.");
  }
  return f;
}

function findings(d) {
  const f = [];
  const add = (sev, title, detail) => f.push({ sev, title, detail });
  const fired = new Set(d.hits.map((h) => h.vendor));

  // Declared and silent is the finding this exists for.
  if (d.declared.ga4.length && !fired.has("ga4")) {
    add("BLOCKER", "GA4 is on the page and sent nothing",
        `${d.declared.ga4.join(", ")} is declared but no hit reached ` +
        "google-analytics.com. The client's reports will be empty while the " +
        "page looks correctly tagged.");
  }
  if (d.declared.meta.length && !fired.has("meta")) {
    add("MAJOR", "A Meta pixel is declared and sent nothing",
        d.declared.meta.join(", "));
  }
  if (d.declared.gtm.length && !fired.has("gtm")) {
    add("MAJOR", "Tag Manager is declared and did not load",
        d.declared.gtm.join(", ") + ". Everything inside it is therefore off.");
  }
  if (!d.declared.ga4.length && !d.declared.gtm.length && !fired.size) {
    add("CHECK", "No analytics of any kind was found",
        "Nothing was declared and nothing fired. If that is deliberate, say " +
        "so; if the client thinks they have analytics, they do not.");
  }

  // Two hits to the same property for one page view is double counting.
  const perId = {};
  for (const h of d.hits) {
    if (h.vendor !== "ga4") continue;
    const id = h.tid || "unknown";
    if (h.event && h.event !== "page_view") continue;
    perId[id] = (perId[id] || 0) + 1;
  }
  for (const [id, n] of Object.entries(perId)) {
    if (n > 1) {
      add("BLOCKER", "The same page view is counted more than once",
          `${n} page_view hits went to ${id} for one load. Usually a tag ` +
          "hardcoded in the page and the same tag again inside Tag Manager. " +
          "Every number the client reads is inflated.");
    }
  }
  if (d.declared.ga4.length > 1) {
    add("MAJOR", "More than one GA4 measurement id in the page",
        d.declared.ga4.join(", ") + ". Decide which one is the property and " +
        "remove the other.");
  }
  if (d.declared.ua.length) {
    add("CHECK", "A Universal Analytics id is still in the page",
        d.declared.ua.join(", ") + ". UA stopped collecting; it is dead weight " +
        "and it confuses whoever reads the source next.");
  }

  // Consent that is denied and never updated records nothing.
  if (d.declared.consentDefault && d.declared.analyticsDenied &&
      !d.declared.consentUpdate) {
    add("BLOCKER", "Consent defaults to denied and is never granted",
        "`analytics_storage` starts denied and nothing calls consent update. " +
        "GA4 will send cookieless pings at best, and the client sees almost " +
        "no users. Check the banner actually calls update when someone accepts.");
  }

  for (const h of d.hits) {
    for (const p of h.personal || []) {
      add(p.sev, `${h.name} is being sent ${p.what}`,
          "The rule is the event name and nothing else. " + h.url.slice(0, 140));
    }
  }

  if (d.clicked) {
    const after = d.hits.filter((h) => h.afterClick);
    if (!after.length) {
      add("MAJOR", "The interaction fired no event at all",
          `Nothing was sent after clicking ${d.clicked}. If this is the ` +
          "conversion, the client is counting none of them.");
    } else {
      const names = [...new Set(after.map((h) => h.event).filter(Boolean))];
      add("CHECK", "What the interaction sent",
          names.length ? names.join(", ")
                       : `${after.length} request(s), no event name readable`);
    }
  }
  return f;
}

async function measure(url, opts) {
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch();
  const width = opts.width;
  const ctx = await browser.newContext({
    viewport: { width, height: width < 768 ? 844 : 900 },
    isMobile: width < 768, hasTouch: width < 768,
    deviceScaleFactor: width < 768 ? 2 : 1,
  });
  const page = await ctx.newPage();
  const hits = [];
  let clicked = null;

  page.on("request", (req) => {
    const u = req.url();
    const v = vendorOf(u);
    if (!v) return;
    let body = null;
    try { body = req.postData(); } catch (e) { /* not available */ }
    hits.push({
      vendor: v.id, name: v.name, kind: v.kind, url: u,
      tid: measurementId(u), event: eventName(u, body),
      personal: v.kind === "hit" ? personalData(u, body) : [],
      afterClick: !!clicked,
    });
  });

  let status = 0;
  try {
    const r = await page.goto(url, { waitUntil: "load", timeout: 90000 });
    status = r ? r.status() : 0;
  } catch (e) {
    await browser.close();
    return { error: String(e).slice(0, 200) };
  }
  // Tags load late, and a consent banner can hold everything until it is
  // answered. Waiting is the difference between "nothing fired" and "nothing
  // had fired yet".
  await page.waitForTimeout(5000);
  const declared = await page.evaluate(DECLARED);
  let surface = null;
  try { surface = await page.evaluate(SURFACE); } catch (e) { /* page gone */ }

  if (opts.consent) {
    const accept = page.locator(
      "button:has-text('Accept'), button:has-text('Agree'), " +
      "button:has-text('Allow'), #onetrust-accept-btn-handler").first();
    try {
      if (await accept.isVisible({ timeout: 2500 })) {
        await accept.click({ timeout: 2500 });
        await page.waitForTimeout(3500);
      }
    } catch (e) { /* no banner */ }
  }

  if (opts.click) {
    clicked = opts.click;
    try {
      await page.locator(opts.click).first().click({ timeout: 8000 });
      await page.waitForTimeout(4000);
    } catch (e) {
      clicked = opts.click + " (could not be clicked: " +
                String(e).slice(0, 60) + ")";
    }
  }

  await browser.close();
  return { url, status, width, declared, surface, hits, clicked,
           consentAccepted: !!opts.consent };
}

function report(d) {
  const L = ["# Analytics", "", d.url, `${d.width}px` +
             (d.consentAccepted ? ", consent banner accepted" : ""), ""];
  L.push("> Read from the network, not the markup: what was sent, not what was");
  L.push("> intended. One load on one machine, with no ad blocker - a real");
  L.push("> visitor's blocker stops some of this, which is a reason the");
  L.push("> client's own numbers are always lower than these.");
  L.push("");
  const dec = d.declared;
  L.push("| Declared | |");
  L.push("|---|---|");
  for (const [k, label] of [["ga4", "GA4"], ["gtm", "Tag Manager"],
                            ["ads", "Google Ads"], ["ua", "Universal Analytics"],
                            ["meta", "Meta pixel"]]) {
    if ((dec[k] || []).length) L.push(`| ${label} | ${dec[k].join(", ")} |`);
  }
  if (dec.consentDefault) {
    L.push(`| Consent mode | default present, analytics_storage ` +
           `${dec.analyticsDenied ? "denied" : "granted"}, update ` +
           `${dec.consentUpdate ? "called" : "**never called**"} |`);
  }
  L.push("");

  const sent = d.hits.filter((h) => h.kind === "hit");
  L.push(`**${sent.length} hit(s) actually sent**` +
         (sent.length ? ":" : ". Nothing reached a collector."));
  for (const h of sent.slice(0, 14)) {
    L.push(`- ${h.name}${h.tid ? ` (${h.tid})` : ""}` +
           `${h.event ? ` - ${h.event}` : ""}${h.afterClick ? "  [after the click]" : ""}`);
  }
  L.push("");

  const f = findings(d).concat(surfaceFindings(d.surface, d.declared));
  for (const sev of ["BLOCKER", "MAJOR", "CHECK", "MINOR", "NOTE"]) {
    const list = f.filter((x) => x.sev === sev);
    if (!list.length) continue;
    L.push(`## ${sev} (${list.length})`, "");
    for (const x of list) L.push(`- **${x.title}** - ${x.detail}`);
    L.push("");
  }
  if (!f.length) L.push("Nothing found.", "");
  return { text: L.join("\n") + "\n", findings: f };
}

async function main() {
  const args = process.argv.slice(2);
  const url = args.find((a) => !a.startsWith("--"));
  if (!url) {
    console.error("usage: node analytics.js <url> [--out <dir>] [--width 390] " +
                  "[--click \"<selector>\"] [--consent]");
    process.exit(2);
  }
  const at = (n, d) => {
    const i = args.indexOf("--" + n);
    return i > -1 && args[i + 1] && !args[i + 1].startsWith("--") ? args[i + 1] : d;
  };
  const out = at("out", "analytics");
  const d = await measure(url, {
    width: parseInt(at("width", "390"), 10),
    click: at("click", null),
    consent: args.includes("--consent"),
  });
  if (d.error) {
    console.error(`could not load ${url}: ${d.error}`);
    process.exit(2);
  }
  fs.mkdirSync(out, { recursive: true });
  const r = report(d);
  fs.writeFileSync(path.join(out, "analytics.md"), r.text, "utf8");
  fs.writeFileSync(path.join(out, "analytics.json"),
    JSON.stringify({ ...d, findings: r.findings }, null, 1), "utf8");
  console.log(r.text);
  console.log(`written to ${path.join(out, "analytics.md")}`);
  process.exit(r.findings.some((x) => x.sev !== "CHECK") ? 1 : 0);
}

if (require.main === module) main();
module.exports = { findings, report, vendorOf, personalData, measurementId,
                   surfaceFindings, AJAX_FORMS,
                  eventName, VENDORS };
