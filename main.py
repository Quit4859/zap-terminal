from __future__ import annotations

import asyncio
import shlex
from pathlib import Path
from urllib.parse import quote_plus, urlsplit

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, BrowserContext, Page, Error as PlaywrightError
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Footer, Input, RichLog, Static

from zap.storage import Storage

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
DB = DATA / "zap.sqlite3"
PROFILE = DATA / "chromium-profile"

CSS = """
Screen { background: #111318; color: #E7E9ED; }
#topbar { height: 3; padding: 1 2; background: #191C23; color: #F4F5F7; text-style: bold; }
#welcome { height: 12; margin: 1 1 0 1; }
.panel { height: 1fr; border: round #343944; padding: 1 2; background: #171A21; }
#hero { width: 2fr; margin-right: 1; }
#activity { width: 1fr; }
.orange { color: #FF923D; text-style: bold; }
.muted { color: #9299A6; }
#tabs { height: 3; margin: 0 1; padding: 0 1; border: round #343944; }
#page { height: 1fr; margin: 0 1; padding: 1 2; border: round #343944; background: #14171D; }
#status { height: 1; padding: 0 2; color: #A3A9B5; background: #191C23; }
#command-row { height: 3; margin: 0 1; }
#prompt { width: 3; content-align: center middle; color: #FF923D; text-style: bold; }
#command { width: 1fr; height: 3; border: round #FF923D; background: #171A21; }
Footer { background: #191C23; color: #9299A6; }
"""

class ZapTerminal(App):
    TITLE = "ZAP"
    SUB_TITLE = "Terminal Web Browser"
    CSS = CSS
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+l", "focus_command", "Command"),
        ("ctrl+t", "new_tab", "New tab"),
        ("ctrl+w", "close_tab", "Close tab"),
        ("pageup", "scroll_up", "Page up"),
        ("pagedown", "scroll_down", "Page down"),
    ]

    def __init__(self):
        super().__init__()
        self.pw = None
        self.context: BrowserContext | None = None
        self.pages: list[Page] = []
        self.active = 0
        self.storage = Storage(DB)
        self.links: list[tuple[str, str]] = []
        self.current_url = ""
        self.http = httpx.AsyncClient(timeout=15, follow_redirects=True,
                                      headers={"User-Agent": "ZAP-Terminal/3.0"})

    def compose(self) -> ComposeResult:
        yield Static(" Z A P   /   TERMINAL WEB BROWSER                              v3.0", id="topbar")
        with Horizontal(id="welcome"):
            with Vertical(id="hero", classes="panel"):
                yield Static("ZAP  •  TERMINAL EDITION", classes="orange")
                yield Static("Welcome to your web workspace.", id="welcome-title")
                yield Static("Search, browse and explore the web without leaving your terminal.\n"
                             "JavaScript-enabled pages are loaded by a background Chromium engine\n"
                             "and presented here as readable terminal content.", classes="muted")
                yield Static("Try:  search python tutorials     open example.com", classes="orange")
            with Vertical(id="activity", classes="panel"):
                yield Static("RECENT ACTIVITY", classes="orange")
                yield Static("No recent activity", id="activity-list", classes="muted")
                yield Static("COMMANDS", classes="orange")
                yield Static("open · search · tabs · back · scroll · bookmarks · history", classes="muted")
        yield Static(" TABS  •  starting…", id="tabs")
        yield RichLog(id="page", wrap=True, markup=False, highlight=False)
        yield Static(" STARTING  •  Initializing browser engine", id="status")
        with Horizontal(id="command-row"):
            yield Static("❯", id="prompt")
            yield Input(placeholder="Type a command or enter a URL…", id="command")
        yield Footer()

    @property
    def log(self):
        try:
            return _LogProxy(self.query_one("#page", RichLog))
        except NoMatches:
            return _NoOpLog()

    def status(self, value):
        self.query_one("#status", Static).update(" " + value)

    async def on_mount(self):
        DATA.mkdir(parents=True, exist_ok=True)
        self.storage.initialize()
        self.query_one("#command", Input).focus()
        self.show_welcome()
        try:
            self.pw = await async_playwright().start()
            self.context = await self.pw.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE), headless=True,
                viewport={"width": 1280, "height": 900},
                args=["--disable-dev-shm-usage"]
            )
            self.pages = list(self.context.pages)
            if not self.pages:
                self.pages.append(await self.context.new_page())
            self.status("READY  •  Chromium headless engine connected")
            await self.open_url("https://duckduckgo.com", record=False)
        except Exception as exc:
            self.status("ENGINE ERROR  •  Install Chromium with: playwright install chromium")
            self.log().write(str(exc))

    async def on_unmount(self):
        await self.http.aclose()
        if self.context:
            await self.context.close()
        if self.pw:
            await self.pw.stop()
        self.storage.close()

    def show_welcome(self):
        log = self.log()
        log.clear()
        log.write("ZAP — TERMINAL WEB BROWSER")
        log.write("=" * 60)
        log.write("")
        log.write("Your web. Your terminal. Your workspace.")
        log.write("")
        log.write("GET STARTED")
        log.write("  search latest Python tutorials")
        log.write("  open https://example.com")
        log.write("  help")
        log.write("")
        log.write("ZAP loads pages in a headless Chromium engine and renders readable")
        log.write("page content in this terminal. Full graphical CSS layout is not shown.")

    def current(self):
        self.pages = [p for p in self.pages if not p.is_closed()]
        if not self.pages:
            return None
        self.active = min(self.active, len(self.pages)-1)
        return self.pages[self.active]

    def update_tabs(self):
        labels = []
        for i, page in enumerate(self.pages):
            label = f"[{i+1}:{(page.url or 'New tab')[:24]}]"
            if i == self.active:
                label = "▶ " + label
            labels.append(label)
        self.query_one("#tabs", Static).update(" TABS  •  " + "   ".join(labels))

    async def on_input_submitted(self, event: Input.Submitted):
        raw = event.value.strip()
        event.input.value = ""
        if not raw:
            return
        try:
            args = shlex.split(raw)
        except ValueError as exc:
            self.status(f"COMMAND ERROR • {exc}")
            return
        cmd, rest = args[0].lower(), args[1:]
        if cmd in {"quit", "exit"}: self.exit()
        elif cmd in {"help", "?"}: self.show_help()
        elif cmd == "open": await self.open_url(" ".join(rest))
        elif cmd == "search": await self.search(" ".join(rest))
        elif cmd == "home": await self.open_url("https://duckduckgo.com")
        elif cmd == "back": await self.navigate_history("back")
        elif cmd == "forward": await self.navigate_history("forward")
        elif cmd == "reload": await self.reload()
        elif cmd == "tabs": self.show_tabs()
        elif cmd == "tab": await self.tab_command(rest)
        elif cmd == "links": self.show_links()
        elif cmd == "scroll": await self.scroll(rest)
        elif cmd == "find": await self.find(" ".join(rest))
        elif cmd == "bookmark": self.add_bookmark(rest)
        elif cmd == "bookmarks": self.show_bookmarks()
        elif cmd == "history": self.show_history()
        elif cmd == "clear": self.log().clear(); self.status("VIEW CLEARED")
        elif raw.startswith(("http://", "https://", "www.")) or "." in cmd:
            await self.open_url(raw)
        else: self.status("UNKNOWN COMMAND • Type help")

    async def open_url(self, url, record=True):
        if not url:
            self.status("USAGE • open https://example.com")
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            self.status("INVALID URL")
            return
        page = self.current()
        if page is None:
            page = await self.new_page()
        self.status("LOADING • " + url[:100])
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(500)
            self.current_url = page.url
            title = await page.title()
            text = await page.locator("body").inner_text(timeout=10000)
            await self.render_text(page, title, text)
            if record:
                self.storage.add_history(page.url, title)
            self.update_tabs()
            self.query_one("#welcome-title", Static).update(title[:80])
            self.query_one("#activity-list", Static).update(self.storage.recent_text())
            self.status(f"LOADED • {title[:70]} • {page.url[:100]}")
        except PlaywrightError as exc:
            self.log().clear()
            self.log().write("PAGE LOAD ERROR")
            self.log().write(str(exc))
            self.status("PAGE LOAD ERROR")

    async def render_text(self, page, title, text):
        self.links = await page.locator("a[href]").evaluate_all(
            """els => els.map(a => ({
                text: (a.innerText || a.getAttribute('aria-label') || a.href).trim(),
                href: a.href
            })).filter(x => x.href.startsWith('http'))"""
        )
        log = self.log()
        log.clear()
        log.write(title or "Untitled page")
        log.write("=" * min(72, max(20, len(title or ""))))
        log.write(page.url)
        log.write("")
        # Keep terminal output bounded; scrolling commands fetch the visible document text again.
        lines = (text or "[No readable page text]").splitlines()
        for line in lines[:2500]:
            line = " ".join(line.split())
            if line:
                log.write(line)
        log.write("")
        log.write(f"LINKS FOUND: {len(self.links)}  •  Type links to list them")
        log.write("Tip: type a link number to open it.")

    async def search(self, query):
        if not query:
            self.status("USAGE • search your query")
            return
        await self.open_url("https://duckduckgo.com/?q=" + quote_plus(query))

    async def new_page(self):
        assert self.context
        page = await self.context.new_page()
        self.pages.append(page)
        self.active = len(self.pages)-1
        self.update_tabs()
        return page

    async def tab_command(self, args):
        if not args or args[0] == "new":
            page = await self.new_page()
            await self.open_url("https://duckduckgo.com", record=False)
        elif args[0] == "close":
            if len(self.pages) <= 1:
                self.status("CANNOT CLOSE LAST TAB")
            else:
                page = self.current()
                await page.close()
                self.pages = [p for p in self.pages if not p.is_closed()]
                self.active = max(0, min(self.active, len(self.pages)-1))
                self.update_tabs()
                await self.refresh_page()
        elif args[0] == "switch" and len(args) > 1 and args[1].isdigit():
            n = int(args[1])
            if 1 <= n <= len(self.pages):
                self.active = n-1
                await self.refresh_page()
            else: self.status("TAB NOT FOUND")
        else: self.status("USAGE • tab new | tab close | tab switch N")

    async def refresh_page(self):
        page = self.current()
        if page:
            try:
                title = await page.title()
                text = await page.locator("body").inner_text(timeout=5000)
                await self.render_text(page, title, text)
                self.update_tabs()
                self.status("ACTIVE TAB • " + page.url[:110])
            except Exception as exc:
                self.status(str(exc)[:120])

    async def navigate_history(self, direction):
        page = self.current()
        if not page: return
        try:
            if direction == "back": await page.go_back(wait_until="domcontentloaded")
            else: await page.go_forward(wait_until="domcontentloaded")
            await self.refresh_page()
        except PlaywrightError:
            self.status("NO " + direction.upper() + " PAGE")

    async def reload(self):
        page = self.current()
        if page:
            await page.reload(wait_until="domcontentloaded")
            await self.refresh_page()

    async def scroll(self, args):
        page = self.current()
        if not page: return
        direction = args[0] if args else "down"
        amount = int(args[1]) if len(args)>1 and args[1].isdigit() else 600
        if direction == "top": await page.evaluate("window.scrollTo(0,0)")
        elif direction == "bottom": await page.evaluate("window.scrollTo(0,document.body.scrollHeight)")
        elif direction in {"up","down"}:
            await page.evaluate("(n)=>window.scrollBy(0,n)", -amount if direction=="up" else amount)
        else:
            self.status("USAGE • scroll up|down [pixels]|top|bottom")
            return
        await self.refresh_page()

    async def find(self, query):
        page = self.current()
        if not page or not query: return
        found = await page.evaluate("(q)=>window.find(q)", query)
        self.status("TEXT FOUND" if found else "TEXT NOT FOUND")

    def show_links(self):
        self.log().clear()
        self.log().write("PAGE LINKS")
        for i, link in enumerate(self.links, 1):
            self.log().write(f"[{i}] {link['text'][:100]} — {link['href']}")
        if not self.links: self.log().write("No links found.")

    def show_tabs(self):
        self.log().clear()
        self.log().write("OPEN TABS")
        for i, p in enumerate(self.pages, 1):
            self.log().write(f"{'▶' if i-1 == self.active else ' '} {i}. {p.url}")
        self.update_tabs()

    def show_help(self):
        self.log().clear()
        self.log().write("ZAP COMMAND REFERENCE")
        self.log().write("")
        for line in [
            "open URL              Open a website",
            "search WORDS          Search DuckDuckGo",
            "home                  Open search home",
            "back / forward        Navigate browser history",
            "reload                Reload current page",
            "tab new               Open new tab",
            "tab switch N          Switch to tab N",
            "tab close             Close active tab",
            "tabs                  List tabs",
            "links                 List numbered links",
            "NUMBER                Open numbered link",
            "scroll up|down [px]   Scroll page and refresh text view",
            "scroll top|bottom     Jump to page edge",
            "find TEXT             Find text on page",
            "bookmark add          Save current page",
            "bookmarks             List bookmarks",
            "history               List browsing history",
            "clear                 Clear terminal viewport",
            "quit                  Exit ZAP",
            "",
            "Ctrl+L focus command · Ctrl+T new tab · Ctrl+W close tab",
            "PageUp/PageDown scroll terminal output.",
        ]:
            self.log().write(line)
        self.status("HELP")

    def add_bookmark(self, args):
        page = self.current()
        if not page or not args or args[0] != "add":
            self.status("USAGE • bookmark add")
            return
        self.storage.add_bookmark(page.url, page.url)
        self.status("BOOKMARK SAVED")

    def show_bookmarks(self):
        self.log().clear()
        self.log().write("BOOKMARKS")
        for i, (title, url) in enumerate(self.storage.bookmarks(), 1):
            self.log().write(f"{i}. {title} — {url}")

    def show_history(self):
        self.log().clear()
        self.log().write("BROWSING HISTORY")
        for i, (title, url, when) in enumerate(self.storage.history(), 1):
            self.log().write(f"{i}. {title} — {url} ({when})")

    def action_focus_command(self):
        self.query_one("#command", Input).focus()

    async def action_new_tab(self):
        await self.tab_command(["new"])

    async def action_close_tab(self):
        await self.tab_command(["close"])

    async def action_scroll_up(self):
        await self.scroll(["up", "600"])

    async def action_scroll_down(self):
        await self.scroll(["down", "600"])


class _NoOpLog:
    def write(self, *args, **kwargs):
        pass

    def clear(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def critical(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass

    def system(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return self


class _LogProxy(_NoOpLog):
    def __init__(self, richlog):
        self._rl = richlog

    def write(self, *args, **kwargs):
        self._rl.write(*args, **kwargs)

    def clear(self, *args, **kwargs):
        self._rl.clear(*args, **kwargs)


def run():
    """Console entry point installed as the `zap` command."""
    ZapTerminal().run()


if __name__ == "__main__":
    run()
