"""
ЭТАП 3:
1. Читает employers.csv (колонки name, agency_url, site).
2. Для каждой компании с непустым site:
   - Пробует главную страницу.
   - Ищет ссылку на страницу контактов.
   - Собирает email и телефоны регулярками.
3. Сохраняет результат в contacts.csv
"""

import asyncio
import csv
import re
from urllib.parse import urljoin
from playwright.async_api import async_playwright

INPUT_CSV = "employers.csv"
OUTPUT_CSV = "contacts.csv"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+7|8)[\s\-\(\)]?\d{3}[\s\-\(\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")

CONTACT_LINK_SELECTORS = [
    'a:has-text("Контакты")',
    'a:has-text("Связаться")',
    'a:has-text("Contact")',
    'a[href*="contact"]',
    'a[href*="kontakt"]',
]


async def extract_contacts_from_page(page, url):
    """Заходит на страницу и возвращает (emails, phones)."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
    except Exception as e:
        print(f"    Не удалось открыть {url}: {e}")
        return set(), set()

    text = await page.content()
    emails = set(EMAIL_RE.findall(text))
    phones = set(PHONE_RE.findall(text))
    return emails, phones


async def process_company(page, company):
    """Для одной компании возвращает dict с контактами."""
    result = {
        "name": company["name"],
        "site": company["site"],
        "contacts_url": "",
        "emails": "",
        "phones": "",
    }
    if not company["site"]:
        return result

    base = "https://" + company["site"] if not company["site"].startswith("http") else company["site"]

    # 1. Собираем контакты с главной
    emails, phones = await extract_contacts_from_page(page, base)

    # 2. Пробуем найти страницу контактов
    contacts_url = ""
    for sel in CONTACT_LINK_SELECTORS:
        link = page.locator(sel)
        if await link.count() > 0:
            href = await link.first.get_attribute("href")
            if href:
                contacts_url = urljoin(base, href)
                break

    # 3. Если нашли — идём и добираем контакты
    if contacts_url and contacts_url != base:
        e2, p2 = await extract_contacts_from_page(page, contacts_url)
        emails |= e2
        phones |= p2
    else:
        contacts_url = base

    result["contacts_url"] = contacts_url
    result["emails"] = "; ".join(sorted(emails))
    result["phones"] = "; ".join(sorted(phones))
    return result


async def main():
    # Читаем работодателей
    with open(INPUT_CSV, "r", encoding="utf-8-sig") as f:
        companies = list(csv.DictReader(f))

    print(f"Загружено {len(companies)} компаний из {INPUT_CSV}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=False)
        page = await browser.new_page()

        results = []
        for idx, comp in enumerate(companies, 1):
            print(f"[{idx}/{len(companies)}] {comp['name']} ({comp['site'] or '—'})")
            try:
                res = await process_company(page, comp)
            except Exception as e:
                print(f"    Ошибка: {e}")
                res = {
                    "name": comp["name"], "site": comp["site"],
                    "contacts_url": "", "emails": "", "phones": ""
                }
            results.append(res)

        await browser.close()

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=["name", "site", "contacts_url", "emails", "phones"]
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"\nГотово. Сохранено {len(results)} строк в {OUTPUT_CSV}")


if __name__ == "__main__":
    asyncio.run(main())