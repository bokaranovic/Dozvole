# vektor — PNG / JPEG → SVG na računaru (kombinacija open-source alata)

Tok obrade, sve besplatno i bez slanja slike ikome:

| Korak | Alat | Šta radi |
|---|---|---|
| 1. priprema | **Pillow** | uvećanje do ~1500 px (glađe krive), medijan filter za JPEG šum, izbjeljivanje ili uklanjanje pozadine koja dodiruje rub |
| 2a. boje | **VTracer** (Rust, MIT) | vektorizacija u boji, naslagani slojevi, Bezier krive |
| 2b. crno-bijelo | **Potrace** (kroz `potracer`) | pečati, potpisi, skenovi — Otsu prag pa pravi Potrace algoritam |
| 3. čišćenje | **Scour** | manji SVG, isti izgled |

`--preset auto` sam prepozna je li slika praktično dvobojna i bira Potrace, inače VTracer.

## Instalacija (Windows, jednom)

1. Python 3.10+ sa https://www.python.org/downloads/ (označi *Add python.exe to PATH*).
2. Dupli klik na `INSTALACIJA.bat`.

## Korištenje

- **Prozor:** dupli klik `POKRENI.bat` → izaberi slike, preset, pozadinu → *Pretvori u SVG*.
- **Prevuci i pusti:** prevuci sliku ili cijeli folder na `VEKTORIZUJ-OVDJE.bat`.
- **Komandna linija:**

```bat
py vektorizuj.py grb.jpg --preset logo --bg white
py vektorizuj.py pecat.jpg --preset bw --bg clear
py vektorizuj.py "slicice ikonice" --preset ikona --out izlaz
py vektorizuj.py *.png --colors 8 --speckle 16 --denoise 3
```

## Preseti i kad koji

| Preset | Za šta | Boje | Mrlje |
|---|---|---|---|
| `logo` | grb, logotip, čiste boje | 16 | 8 |
| `ikona` | ilustracija sa sjenčenjem | 24 | 12 |
| `foto` | fotografija → plakatski izgled | 48 | 32 |
| `bw` | pečat, potpis, sken, crtež | 2 | 6 |
| `auto` | ne znam → sam odluči | | |

Savjeti:
- JPEG sa sivim „oreolom“ oko grba → `--bg white`.
- Providna pozadina za web ili aplikaciju → `--bg clear`.
- Previše sitnih oblika → povećaj `--speckle` (16–48) ili dodaj `--denoise 3`.
- Premalo detalja → povećaj `--colors` ili smanji `--speckle`.
- Doradu (brisanje viška, spajanje) uradi u Inkscape-u (besplatan).

## Zašto ne „AI model“

Otvoreni modeli slika→SVG (OmniSVG, StarVector) traže NVIDIA karticu sa 17+ GB memorije, rade na malim rezolucijama i sliku *precrtavaju*, pa grb ne ispadne isti. Za vjeran prenos grba, logotipa ili pečata klasični tracer je bolji, brži i radi na svakom računaru. Modeli imaju smisla za drugi posao: generisanje nove ikone iz teksta.

## Ista stvar u pregledniku

Na sajtu postoji `Alati-PNG-u-SVG.html` sa vlastitim motorom (bez instalacije, radi i na telefonu). Ovaj paket daje bolji kvalitet jer koristi VTracer i Potrace; browser verzija je za brzo, usput.
