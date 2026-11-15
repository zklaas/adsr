# ADSR on macOS

The same code runs on macOS, Windows and Linux. ADSR needs **Python 3.10 or newer**
(macOS's own `python3` is too old):

    brew install python@3.13        # Homebrew: https://brew.sh
    # or the installer from https://www.python.org/downloads/macos/

Then, in Terminal:

    git clone https://github.com/zklaas/adsr.git ADSR
    cd ADSR
    bash install-macos.sh

That creates `.venv` (PyQt6), a `adsr` command in `~/.local/bin`, and a
**ADSR** app in your Applications folder (Launchpad, Spotlight, the Dock).

LAN games use TCP port 47420: when macOS asks whether to accept incoming connections, allow it.

To remove it: delete the folder, `~/Applications/ADSR.app` and `~/.local/bin/adsr`.

macOS support has not yet been tested on a Mac; please report anything that does
not work.
