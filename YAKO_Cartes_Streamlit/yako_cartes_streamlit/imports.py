"""Import de listes et lecture assistée des captures, avec validation humaine."""

from __future__ import annotations

import csv
import re
import shutil
import subprocess
import tempfile
import unicodedata
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd
from PIL import Image, ImageEnhance


DEFAULT_ADDRESS = "Immeuble pacifique, Rue du commerce"
DEFAULT_COMPANY_EMAIL = "infos@yakoafricassur.com"
COLUMNS = ["type", "nom", "fonction", "telephone", "mobile", "email",
           "adresse", "email_societe", "qr_fichier"]


def _key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value).strip().lower())
    return "".join(c for c in text if c.isalnum())


ALIASES = {
    "type": "type", "categorie": "type", "profil": "type",
    "nom": "nom", "nometprenom": "nom", "nometprenoms": "nom", "fullname": "nom",
    "prenom": "prenom", "fonction": "fonction", "poste": "fonction",
    "telephone": "telephone", "tel": "telephone", "numero": "telephone",
    "mobile": "mobile", "secondnumero": "mobile", "telephone2": "mobile",
    "email": "email", "mail": "email", "courriel": "email",
    "adresse": "adresse", "lieuprofessionnel": "adresse", "lieudetravail": "adresse",
    "emailsociete": "email_societe", "mailgeneral": "email_societe",
    "qrfichier": "qr_fichier", "qrcode": "qr_fichier", "fichierqr": "qr_fichier",
}


def read_table(raw: bytes, filename: str) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        decoded = raw.decode("utf-8-sig")
        sample = decoded[:4096]
        try:
            sep = csv.Sniffer().sniff(sample, delimiters=";,\t").delimiter
        except csv.Error:
            sep = ";" if sample.count(";") >= sample.count(",") else ","
        frame = pd.read_csv(StringIO(decoded), sep=sep, dtype=str, keep_default_na=False)
    elif suffix == ".xlsx":
        frame = pd.read_excel(BytesIO(raw), dtype=str, keep_default_na=False)
    else:
        raise ValueError("Utilise un fichier CSV ou XLSX.")
    if frame.empty:
        raise ValueError("Le tableau est vide.")
    frame.columns = [ALIASES.get(_key(column), str(column).strip()) for column in frame.columns]
    if "nom" not in frame and "prenom" in frame:
        raise ValueError("Ajoute une colonne nom.")
    if "prenom" in frame:
        frame["nom"] = frame["prenom"].astype(str).str.strip() + " " + frame["nom"].astype(str).str.strip()
    missing = {"nom", "fonction", "telephone", "email"} - set(frame.columns)
    if missing:
        raise ValueError("Colonnes obligatoires manquantes : " + ", ".join(sorted(missing)))
    for column in COLUMNS:
        if column not in frame:
            frame[column] = ""
    frame = frame[COLUMNS].fillna("").astype(str)
    frame["type"] = frame["type"].replace("", "Employé")
    frame["adresse"] = frame["adresse"].replace("", DEFAULT_ADDRESS)
    frame["email_societe"] = frame["email_societe"].replace("", DEFAULT_COMPANY_EMAIL)
    return frame


def extract_screenshot(raw: bytes) -> dict[str, str]:
    if not shutil.which("tesseract"):
        raise RuntimeError("L'OCR nécessite Tesseract installé sur l'ordinateur. La saisie manuelle reste disponible.")
    image = Image.open(BytesIO(raw)).convert("RGB")
    image = image.resize((image.width * 4, image.height * 4), Image.Resampling.LANCZOS)
    image = ImageEnhance.Contrast(image).enhance(1.8)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "capture.png"
        image.save(path)
        result = subprocess.run(["tesseract", str(path), "stdout", "--psm", "11"],
                                capture_output=True, text=True, timeout=25)
    if result.returncode:
        raise RuntimeError("Impossible de lire cette capture. Saisis les informations manuellement.")
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", " ".join(lines))
    phones = []
    for line in lines:
        digits = re.sub(r"\D", "", line)
        if 10 <= len(digits) <= 14:
            phones.append("+" + digits[:3] + " " + " ".join(digits[3:][i:i+2]
                          for i in range(0, len(digits[3:]), 2)))
    filtered = [line for line in lines if "@" not in line and len(re.sub(r"\D", "", line)) < 8]
    return {
        "nom": filtered[0] if filtered else "",
        "fonction": filtered[1] if len(filtered) > 1 else "",
        "telephone": phones[0] if phones else "",
        "mobile": phones[1] if len(phones) > 1 else "",
        "email": next((mail for mail in emails if not mail.lower().startswith("infos@")), ""),
        "adresse": next((line for line in lines if "immeuble" in line.lower() or "rue du" in line.lower()), DEFAULT_ADDRESS),
        "email_societe": next((mail for mail in emails if mail.lower().startswith("infos@")), DEFAULT_COMPANY_EMAIL),
    }


def crop_qr(raw: bytes, x_pct: int, y_pct: int, size_pct: int) -> bytes:
    image = Image.open(BytesIO(raw)).convert("RGB")
    x = round(image.width * x_pct / 100)
    y = round(image.height * y_pct / 100)
    size = round(image.width * size_pct / 100)
    if size < 20 or x + size > image.width or y + size > image.height:
        raise ValueError("Le cadrage du QR code dépasse l'image.")
    buffer = BytesIO()
    image.crop((x, y, x + size, y + size)).save(buffer, format="PNG")
    return buffer.getvalue()
