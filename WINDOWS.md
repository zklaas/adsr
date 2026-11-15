# ADSR on Windows

The same code runs on Windows, macOS and Linux. ADSR needs **Python 3.10 or newer**:

    winget install --id Python.Python.3.13 -e --scope user

Then install with PowerShell:

    git clone https://github.com/zklaas/adsr.git ADSR
    cd ADSR
    powershell -ExecutionPolicy Bypass -File install.ps1

That creates `.venv` (PyQt6), a `adsr` command on your PATH (open a
new terminal first), and a **ADSR** Start-menu entry.

LAN games use TCP port 47420: when Windows Firewall asks, allow ADSR on private networks.

To remove it: delete the folder, the Start-menu entry (ADSR) and
`%LOCALAPPDATA%\Programs\ADSR`.

Windows support has not yet been tested on a Windows machine; please report anything
that does not work.
