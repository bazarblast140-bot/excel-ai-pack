#!/usr/bin/env python3
"""Static and local-server checks for the ₹99 Hindi pack delivery update.

v2 product bytes are NOT release-ready. An Android viewer opened the v2 shop
workbook and showed separated Hindi matras (dotted circles) plus horizontally
clipped instruction lines. When corrected v3 files arrive, replace the files
in pack/ AND the EXPECTED hashes below. Do not treat phone display as verified.

Does not open Microsoft Excel or Google Sheets.
Does not re-run the LibreOffice formula suite (reported 242/242 elsewhere).
"""
from __future__ import annotations

import hashlib
import http.server
import re
import socket
import subprocess
import threading
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "pack"

EXPECTED = {
    "01_Quick_Start.pdf": (
        42237,
        "960c937c6f438dfaacfe793056a610a10319900c5989c6bb1885dbf2afb245c7",
        b"%PDF",
        "application/pdf",
    ),
    "02_Excel_AI_Hindi_Book.pdf": (
        231511,
        "0caab0cfc76a748c6dfb8e51a2b37d0b0ffd69c7e6a82e70aa45d98a8b14d371",
        b"%PDF",
        "application/pdf",
    ),
    "03_dukaan_bikri.xlsx": (
        83851,
        "0bcb6ef808987c44767aae1ac25d97a7fd9708b019f982880956353f78e9a832",
        b"PK\x03\x04",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "04_udhaar_khata.xlsx": (
        108007,
        "fa4c203f8223f4eb80cbce060ed8edb4309d6cc329248a54d9703e4b03160199",
        b"PK\x03\x04",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "05_ghar_budget.xlsx": (
        17251,
        "6f11f46b03a027419968e86a47f9add264a01d7836f07d66ceee12a5cb62270e",
        b"PK\x03\x04",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "06_attendance.xlsx": (
        21391,
        "4bf6711d48a6928040bcf6173b429e72927f812efe8d33d98ba9beae0f2e89cf",
        b"PK\x03\x04",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "07_gst_invoice.xlsx": (
        14196,
        "11248df2822d0207c46fec2fe313e1a684b5a354cc603d249fe1282cb1af9d3f",
        b"PK\x03\x04",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "Excel_AI_Hindi_Starter_Pack_v2.zip": (
        394580,
        "ec50d170b76dc9bd522ad9fc51e40d1ba90869e3da00fc641992dc4648f4fcb8",
        b"PK\x03\x04",
        "application/zip",
    ),
}

PRIMARY = [
    ("01_Quick_Start.pdf", "Quick Start – पहले यही खोलें"),
    ("02_Excel_AI_Hindi_Book.pdf", "पूरी हिंदी किताब (32 पेज)"),
    ("03_dukaan_bikri.xlsx", "दुकान बिक्री रजिस्टर"),
    ("04_udhaar_khata.xlsx", "उधार खाता"),
    ("05_ghar_budget.xlsx", "घर का बजट"),
    ("06_attendance.xlsx", "हाज़िरी रजिस्टर"),
    ("07_gst_invoice.xlsx", "GST इनवॉइस (सीखने का टेम्पलेट)"),
    ("Excel_AI_Hindi_Starter_Pack_v2.zip", "पूरा पैक ZIP (कंप्यूटर के लिए)"),
]

OLD_FILES = [
    "01_START_HERE.pdf",
    "02_Excel_AI_Hindi_Starter_Guide.pdf",
    "OPTIONAL_full_pack.zip",
]

SUPPORT = ("bazarblast140@gmail.com", "919118606518", "Rajesh Kumar")
PIXEL = "1690255725618467"
BUTTON = "pl_TuxhxMgITxpLb2"
FALLBACK = "pl_ToaPkUzSQWDGHi"

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("ok  " if cond else "FAIL") + " " + msg)
    if not cond:
        failures.append(msg)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str, str]] = []
        self._href = ""
        self._download = ""
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        ad = dict(attrs)
        self._href = ad.get("href", "")
        self._download = ad.get("download", "")
        self._text = []

    def handle_data(self, data):
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            self.links.append((self._href, self._download, "".join(self._text).strip()))
            self._href = ""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_files() -> None:
    for name, (size, digest, magic, _mime) in EXPECTED.items():
        path = PACK / name
        data = path.read_bytes()
        check(path.is_file(), f"exists {name}")
        check(len(data) == size, f"size {name} {len(data)} == {size}")
        check(sha256(path) == digest, f"sha256 {name}")
        check(data.startswith(magic), f"magic {name}")
    for name in OLD_FILES:
        check((PACK / name).is_file(), f"old download still present {name}")
    # v2 zip members are the seven individual files, byte-for-byte.
    with zipfile.ZipFile(PACK / "Excel_AI_Hindi_Starter_Pack_v2.zip") as zf:
        names = zf.namelist()
        check(names == [n for n, _ in PRIMARY[:-1]], f"zip member order {names}")
        for info in zf.infolist():
            payload = zf.read(info)
            check(hashlib.sha256(payload).hexdigest() == EXPECTED[info.filename][1], f"zip member hash {info.filename}")
    # Shop workbook states the catalogue-rate limitation in its own instructions.
    shop_xml = zipfile.ZipFile(PACK / "03_dukaan_bikri.xlsx").read("xl/worksheets/sheet1.xml")
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    shop_text = "".join(t.text or "" for t in ET.fromstring(shop_xml).iter(ns + "t"))
    check("पुरानी लाइनों का Amount भी नए रेट से बदल जाएगा" in shop_text, "shop sheet warns that a new rate rewrites old amounts")


def check_html(path: Path, prefix: str) -> None:
    text = path.read_text(encoding="utf-8")
    parser = LinkParser()
    parser.feed(text)
    hrefs = [h for h, _d, _t in parser.links]
    positions = []
    for filename, label in PRIMARY:
        href = prefix + filename
        matches = [(h, d, t) for h, d, t in parser.links if h == href]
        check(len(matches) >= 1, f"{path.name} links {href}")
        if not matches:
            continue
        _h, download, link_text = matches[0]
        check(download != "", f"{path.name} download attribute on {filename} ({download!r})")
        check(label in link_text, f"{path.name} label {label!r} in {link_text!r}")
        positions.append(hrefs.index(href))
    check(positions == sorted(positions), f"{path.name} primary links stay in order {positions}")
    if positions:
        zip_at = hrefs.index(prefix + PRIMARY[-1][0])
        earlier = [hrefs.index(prefix + name) for name, _label in PRIMARY[:-1]]
        check(all(i < zip_at for i in earlier), f"{path.name} ZIP is after each individual file")
    check("noindex" in text, f"{path.name} stays noindex")
    check("जारी करने लायक नहीं" in text, f"{path.name} marks v2 assets not release-ready")
    check("Android viewer" in text and "dotted circles" in text, f"{path.name} records the Android shop-file failure")
    check("सत्यापित नहीं" in text, f"{path.name} does not present phone display as verified")
    for banned in ("Microsoft Excel ऐप में खोलें", "Edit दबाएँ", "phone par sahi dikhna verify ho chuka"):
        check(banned not in text, f"{path.name} does not claim a verified phone open path ({banned})")
    check("नए रेट से बदल" in text, f"{path.name} does not claim historical shop prices stay fixed")
    for token in ("countdown", "offer ends", "% off", "50% off", "<s>"):
        check(token not in text.lower(), f"{path.name} has no {token}")
    # No second price. ₹99 is the only rupee amount.
    amounts = set(re.findall(r"₹\s*[0-9][0-9,]*", text))
    check(amounts == {"₹99"}, f"{path.name} only rupee amount is ₹99, got {amounts}")


def check_pages() -> None:
    check_html(ROOT / "thank-you.html", "pack/")
    check_html(PACK / "index.html", "")
    landing = (ROOT / "index.html").read_text(encoding="utf-8")
    ty = (ROOT / "thank-you.html").read_text(encoding="utf-8")
    for token in (PIXEL, BUTTON, FALLBACK, *SUPPORT[:2], "Rajesh Kumar"):
        check(token in landing, f"landing still has {token}")
    check(PIXEL in ty, "thank-you pixel unchanged id")
    for token in SUPPORT:
        check(token in landing or token in (ROOT / "privacy.html").read_text(encoding="utf-8"), f"support identity kept {token}")
    check("mailto:bazarblast140@gmail.com" in ty, "thank-you email support kept")
    check("https://wa.me/919118606518" in ty, "thank-you WhatsApp support kept")
    # Sales page must not grow a direct download of the paid files.
    check(not re.search(r'href="[^"]*(?:pack/|\.xlsx|\.pdf|\.zip)', landing), "landing has no file download link")
    check("release-ready nahi" in landing and "dotted circles" in landing, "landing marks v2 assets not release-ready")
    check("Phone par sahi dikhna verify nahi hua" in landing, "landing does not present phone display as verified")
    check("Microsoft Excel app kholkar Edit" not in landing, "landing does not give an unverified phone edit path")
    for name in OLD_FILES:
        committed = subprocess.check_output(["git", "show", f"HEAD:pack/{name}"])
        check(committed == (PACK / name).read_bytes(), f"old file bytes unchanged {name}")
    check("Purchase" in ty and "if(!hasRzpParam&&!fromRzp&&!srcRzp)return" in ty, "Purchase pixel still gated on Razorpay signal")
    old = subprocess.check_output(["git", "show", "HEAD:thank-you.html"], text=True)
    old_scripts = re.findall(r"<script>(.*?)</script>", old, re.S)
    new_scripts = re.findall(r"<script>(.*?)</script>", ty, re.S)
    check(old_scripts == new_scripts, "thank-you script blocks unchanged")
    en_diff = subprocess.check_output(["git", "diff", "--name-only", "--", "en", "img", ".github"], text=True)
    check(en_diff.strip() == "", f"english, ads and workflows untouched ({en_diff.strip()!r})")
    # Page counts from the shipped PDFs.
    from pypdf import PdfReader

    check(len(PdfReader(str(PACK / "01_Quick_Start.pdf")).pages) == 2, "quick start is 2 pages")
    check(len(PdfReader(str(PACK / "02_Excel_AI_Hindi_Book.pdf")).pages) == 32, "book is 32 pages")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return


def check_http() -> None:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    # Serve from the site root.
    import os

    os.chdir(ROOT)
    thread.start()
    try:
        for name, (_size, _digest, magic, mime) in EXPECTED.items():
            url = f"http://127.0.0.1:{port}/pack/{name}"
            with urllib.request.urlopen(url) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "").split(";")[0].strip()
                check(resp.status == 200, f"GET {name} -> {resp.status}")
                check(ctype == mime, f"local MIME {name} {ctype} == {mime}")
                check(body.startswith(magic), f"served magic {name}")
                check(len(body) == _size, f"served size {name} {len(body)}")
        for page in ("/thank-you.html", "/pack/", "/"):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{page}") as resp:
                check(resp.status == 200, f"GET {page} -> {resp.status}")
                check("text/html" in resp.headers.get("Content-Type", ""), f"{page} is html")
    finally:
        server.shutdown()


def main() -> int:
    check_files()
    check_pages()
    check_http()
    print(f"\n{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
