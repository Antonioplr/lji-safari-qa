"""
Real-Safari QA of the /technology hero (macOS runner). Drives Safari through safaridriver and WebKit through
Playwright, and writes screenshots, the hero's state at each scroll step, and any page errors to qa-out/.

The page under test carries a tiny error recorder (injected into the built HTML by the workflow), so errors
thrown before WebDriver can attach are still captured in window.__qaErrors.
"""
import json, os, sys, time
from pathlib import Path

BASE = os.environ.get('QA_URL', 'http://localhost:4321/technology')
OUT = Path('qa-out'); OUT.mkdir(exist_ok=True)
STEPS = [0, 150, 300, 450, 600, 800, 1000, 1200, 1500, 2000]

STATE_JS = r"""
const q = (s) => document.querySelector(s);
const lap = q('.tech-hero__laptop'), c = q('.tech-hero__canvas'), h = q('[data-tech-hero]'), h1 = q('.tech-hero h1');
const scr = q('[data-tech-frame] [data-gravty-screen]');
const r = (el) => { if (!el) return null; const b = el.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)]; };
return JSON.stringify({
  ua: navigator.userAgent, reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches, scrollY: scrollY, vw: innerWidth, vh: innerHeight, dpr: devicePixelRatio,
  html: document.documentElement.className,
  hero: h && { cls: h.className, data: Object.assign({}, h.dataset), rect: r(h) },
  laptop: lap && { cls: lap.className, opacity: getComputedStyle(lap).opacity, display: getComputedStyle(lap).display, rect: r(lap) },
  canvas: c && { w: c.width, h: c.height, opacity: getComputedStyle(c).opacity, rect: r(c) },
  h1: h1 && getComputedStyle(h1).opacity,
  screen: scr && { cls: scr.className, transform: getComputedStyle(scr).transform.slice(0, 120), rect: r(scr) },
  imgs: Array.from(document.querySelectorAll('.tech-hero img')).map((i) => [(i.currentSrc || '').split('/').pop(), i.complete, i.naturalWidth, getComputedStyle(i).display, getComputedStyle(i).visibility]),
  frames: performance.getEntriesByType('resource').filter((e) => e.name.includes('/macbook/')).length,
  errors: window.__qaErrors || 'no recorder',
  apis: { createImageBitmap: typeof createImageBitmap, ResizeObserver: typeof ResizeObserver, cqw: CSS.supports('width: 1cqw'), svh: CSS.supports('height: 1svh'), has: CSS.supports('selector(:has(a))') },
});
"""


def run_safari():
    from selenium import webdriver
    report = {'engine': 'safari', 'steps': []}
    d = webdriver.Safari()
    try:
        d.set_window_rect(0, 0, 1440, 1000)
        d.get(BASE)
        time.sleep(6)
        report['load'] = json.loads(d.execute_script(STATE_JS))
        for y in STEPS:
            d.execute_script(f'window.scrollTo(0, {y});')
            time.sleep(1.6)
            d.save_screenshot(str(OUT / f'safari-{y:04d}.png'))
            report['steps'].append(json.loads(d.execute_script(STATE_JS)))
    except Exception as e:  # keep what we have
        report['exception'] = repr(e)
    finally:
        d.quit()
    return report


def run_playwright_webkit():
    from playwright.sync_api import sync_playwright
    report = {'engine': 'playwright-webkit', 'steps': [], 'pageerrors': [], 'console': []}
    with sync_playwright() as p:
        b = p.webkit.launch()
        ctx = b.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=2, record_video_dir=str(OUT / 'video'), record_video_size={'width': 1440, 'height': 900})
        pg = ctx.new_page()
        pg.on('pageerror', lambda e: report['pageerrors'].append(str(e)[:500]))
        pg.on('console', lambda m: report['console'].append(f'{m.type}: {m.text[:300]}'))
        pg.goto(BASE, wait_until='load')
        pg.wait_for_timeout(6000)
        report['load'] = json.loads(pg.evaluate('() => { ' + STATE_JS + ' }'))
        for y in STEPS:
            pg.evaluate(f'scrollTo(0, {y})'); pg.wait_for_timeout(1600)
            pg.screenshot(path=str(OUT / f'pwwebkit-{y:04d}.png'))
            report['steps'].append(json.loads(pg.evaluate('() => { ' + STATE_JS + ' }')))
        ctx.close(); b.close()
    return report


if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'both'
    out = {}
    if which in ('both', 'safari'):
        try: out['safari'] = run_safari()
        except Exception as e: out['safari'] = {'fatal': repr(e)}
    if which in ('both', 'webkit'):
        try: out['webkit'] = run_playwright_webkit()
        except Exception as e: out['webkit'] = {'fatal': repr(e)}
    (OUT / 'report.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({k: {kk: (vv if kk in ('fatal', 'exception', 'pageerrors') else '…') for kk, vv in v.items()} for k, v in out.items()}, indent=1))
