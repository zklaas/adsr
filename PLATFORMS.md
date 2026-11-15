# Installing ADSR

## Linux

```
git clone https://github.com/zklaas/adsr.git
cd adsr
python3 -m pip install --user PyQt6   # or your distribution's packages
./install.sh
```

## Windows (untested)

```
git clone https://github.com/zklaas/adsr.git
cd adsr
py -m pip install PyQt6
powershell -ExecutionPolicy Bypass -File install.ps1
```

## macOS (untested)

```
git clone https://github.com/zklaas/adsr.git
cd adsr
python3 -m pip install --user PyQt6
python3 adsr.py
```
