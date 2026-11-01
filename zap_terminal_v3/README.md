# ZAP Terminal Browser 3.0

All application controls and page text run inside the terminal. A headless Chromium engine loads JavaScript-enabled pages in the background; ZAP displays readable text and links in a Textual terminal interface.

## Install

Python 3.10+ required.

```bash
python -m venv .venv
```

Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```

Linux/macOS:
```bash
source .venv/bin/activate
```

Install and install Chromium:
```bash
pip install -r requirements.txt
playwright install chromium
```

Run:
```bash
python main.py
```

## Commands

- `open URL` — open a page
- `search WORDS` — search DuckDuckGo
- `back`, `forward`, `reload`, `home`
- `tab new`, `tab switch N`, `tab close`, `tabs`
- `links` — list links; enter a number to follow
- `scroll up|down [pixels]`, `scroll top`, `scroll bottom`
- `find TEXT`
- `bookmark add`, `bookmarks`, `history`
- `help`, `clear`, `quit`

## Important limitations

ZAP is terminal-only. It does not show the actual graphical CSS layout, images, video, or graphical controls of websites. Chromium runs headlessly to execute JavaScript and produce rendered page text. Terminal scroll keys scroll the text panel; `scroll up/down` scroll the webpage and refresh its extracted text. This is not a pixel-perfect Chrome replacement.


## Install the `zap` terminal command

From the extracted project directory, activate your virtual environment, then run:

```bash
pip install -e .
playwright install chromium
```

After installation, the command is available as:

```bash
zap
```

Run `zap` while the virtual environment is activated. If you open a new terminal later, activate `.venv` again first.

On Windows PowerShell:

```powershell
.venv\\Scripts\\Activate.ps1
zap
```

On macOS/Linux:

```bash
source .venv/bin/activate
zap
```

The `$` often shown in shell examples is the shell prompt, not part of the command. Type `zap`, not `$zap`.


## One-command install (Linux/macOS)

The installer is configured for the public repository `https://github.com/Quit4859/zap-terminal`. After all project files (including `install.sh`, `main.py`, `zap/`, `pyproject.toml`, and `requirements.txt`) are pushed to its `main` branch, users can install with:

```bash
curl -fsSL https://raw.githubusercontent.com/OWNER/REPO/main/install.sh | bash
```

The installer clones/updates the repository, creates an isolated Python environment,
installs ZAP and Chromium, and creates the `zap` launcher in `~/.local/bin`.

If `~/.local/bin` is not on PATH, the installer prints the required PATH commands.
This installer is for Linux/macOS Bash environments. Windows users should use WSL
or a separate PowerShell installer.

Only run a `curl | bash` installer from a repository you trust: it executes the
downloaded script with your user permissions. Review `install.sh` before running it.
