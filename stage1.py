"""
ЭТАП 1 + 2:
1. Открывает страницу-агрегатор со списком компаний.
2. Нажимает "Загрузить ещё", пока кнопка не исчезнет.
3. Собирает ссылки на разделы компаний (a.agency-name).
4. Заходит в каждый раздел и берёт видимый текст ссылки на сайт (a.profile-info__site).
5. Сохраняет результат в employers.csv
"""

import asyncio
import csv
from playwright.async_api import async_playwright

START_URL = "https://yak-studio.ru/web-studios"   # ← заменить
BASE_URL  = "https://yak-studio.ru/"          # ← заменить

OUTPUT_CSV = "employers.csv"


async def extract_external_site(page):
    """Возвращает домен сайта компании из видимого текста ссылки."""
    site_link = page.locator('a.profile-info__site')
    if await site_link.count() == 0:
        return None
    text = (await site_link.first.inner_text()).strip()
    if not text:
        return None
    text = text.replace("http://", "").replace("https://", "").strip("/")
    return text


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=False)
        page = await browser.new_page()
        await page.goto(START_URL, wait_until="networkidle")

        # --- Подгрузка списка ---
        click_count = 0
        while True:
            load_more = page.locator('a.ajax-more:has-text("Загрузить ещё")')
            if await load_more.count() == 0 or not await load_more.first.is_visible():
                print("Кнопка 'Загрузить ещё' исчезла — всё загружено")
                break

            before = await page.locator('a.agency-name').count()
            try:
                await load_more.first.scroll_into_view_if_needed()
                await load_more.first.click()
                click_count += 1
                print(f"Нажатие #{click_count}, карточек было: {before}")
                await page.wait_for_function(
                    f"document.querySelectorAll('a.agency-name').length > {before}",
                    timeout=10000
                )
            except Exception as e:
                print(f"Остановка подгрузки: {e}")
                break

        # --- Сбор ссылок на разделы компаний ---
        cards = page.locator('a.agency-name')
        total = await cards.count()
        print(f"\nВсего компаний: {total}")

        agency_links = []
        for i in range(total):
            href = await cards.nth(i).get_attribute("href")
            name = (await cards.nth(i).inner_text()).strip()
            if href:
                full_url = href if href.startswith("http") else BASE_URL + href.lstrip("/")
                agency_links.append({"name": name, "agency_url": full_url})

        print(f"Собрано ссылок на разделы: {len(agency_links)}\n")

        # --- Обход разделов и извлечение внешних сайтов ---
        results = []
        for idx, item in enumerate(agency_links, 1):
            try:
                await page.goto(item["agency_url"], wait_until="domcontentloaded", timeout=15000)
                external = await extract_external_site(page)
                results.append({
                    "name": item["name"],
                    "agency_url": item["agency_url"],
                    "site": external or ""
                })
                print(f"[{idx}/{len(agency_links)}] {item['name']} -> {external}")
            except Exception as e:
                print(f"[{idx}] Ошибка на {item['agency_url']}: {e}")
                results.append({
                    "name": item["name"],
                    "agency_url": item["agency_url"],
                    "site": ""
                })

        # --- Сохранение ---
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "agency_url", "site"])
            writer.writeheader()
            writer.writerows(results)

        print(f"\nГотово. Сохранено {len(results)} строк в {OUTPUT_CSV}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())