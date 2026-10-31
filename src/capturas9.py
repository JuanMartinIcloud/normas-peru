"""Prueba: que base principal usa la web (y que variables tiene configuradas Vercel)."""
import json
import os

from playwright.sync_api import sync_playwright

os.makedirs("capturas", exist_ok=True)
with sync_playwright() as pw:
    nav = pw.chromium.launch()
    page = nav.new_page()
    r = page.goto("https://normas-peru.vercel.app/api/estado", wait_until="networkidle", timeout=120000)
    d = r.json()
    nota = json.dumps({"principal": d.get("principal"), "normas": d.get("normas"),
                       "bases_texto": [b.get("base") for b in (d.get("textos") or {}).get("bases", [])],
                       "error": d.get("error")}, ensure_ascii=False)
    print(nota)
    page.goto("https://normas-peru.vercel.app/proyectos?q=00098-2026-2031-CD", wait_until="networkidle", timeout=120000)
    page.screenshot(path="capturas/proyecto.png", full_page=False)
    nav.close()
with open("capturas/notas.txt", "w") as f:
    f.write(nota)
