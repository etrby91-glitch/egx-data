import asyncio, json, os, sys
import pandas as pd
from datetime import date

BASE  = "https://www.egx.com.eg"
PAGE  = BASE + "/ar/InvestorsTypeCharts.aspx"
CSV   = "EGX_History.csv"
GROUP_NAMES = {"1": "اجمالي", "2": "افراد", "3": "مؤسسات"}

async def fetch():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu",
                  "--disable-blink-features=AutomationControlled"]
        )
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            viewport={"width":1280,"height":900}, locale="ar",
            extra_http_headers={"Accept-Language":"ar,en-US;q=0.9"}
        )
        page = await ctx.new_page()
        try:
            await page.goto(PAGE, wait_until="domcontentloaded", timeout=30000)
        except: pass
        await asyncio.sleep(15)
        url = BASE + "/WebService.asmx/GetInvestorTables?Lang=ar&SB=1"
        res = await page.evaluate(
            "async (url) => { try { const r = await fetch(url, {"
            "  method:\"GET\", credentials:\"include\","
            "  headers:{\"Accept\":\"*/*\",\"X-Security-Request\":\"required\",\"X-Requested-With\":\"XMLHttpRequest\"}"
            "}); return {status:r.status, body:await r.text()};"
            "} catch(e){ return {status:0,body:\"ERR:\"+e.message}; } }",
            url
        )
        await browser.close()
        return res.get("body", "")

def build_row(body, today):
    if not body.strip().startswith("["):
        print(f"Bad response: {body[:100]}")
        return None
    raw = json.loads(body)
    rec = {"تاريخ": today}
    for row in raw:
        grp = GROUP_NAMES.get(str(row.get("Group","")), "?")
        typ = row.get("Type","?").strip().replace("أجانب","اجانب")
        rec[grp+"_"+typ+"_شراء"] = row.get("Buy",  0)
        rec[grp+"_"+typ+"_بيع"]  = row.get("Sell", 0)
        rec[grp+"_"+typ+"_صافي"] = row.get("Net",  0)
    return rec

def save(rec):
    today = rec["تاريخ"]
    groups  = ["اجمالي","افراد","مؤسسات"]
    types   = ["مصريين","عرب","اجانب"]
    metrics = ["شراء","بيع","صافي"]
    ordered = ["تاريخ"] + [g+"_"+t+"_"+m for g in groups for t in types for m in metrics]
    ordered = [c for c in ordered if c in rec] + [c for c in rec if c not in ordered]
    df_new = pd.DataFrame([rec])[ordered]
    if os.path.exists(CSV):
        df_old = pd.read_csv(CSV, encoding="utf-8-sig")
        df_old = df_old[df_old["تاريخ"] != today]
        df_all = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_all = df_new
    df_all = df_all.sort_values("تاريخ").reset_index(drop=True)
    df_all.to_csv(CSV, index=False, encoding="utf-8-sig")
    print(f"Saved {today}. Total days: {len(df_all)}")
    return df_all

async def main():
    today = str(date.today())
    print(f"Running for: {today}")
    body = await fetch()
    print(f"Response: {body[:150]}")
    rec = build_row(body, today)
    if rec:
        df = save(rec)
        print(df.tail(3).to_string())
    else:
        print("No data.")
        sys.exit(1)

asyncio.run(main())
