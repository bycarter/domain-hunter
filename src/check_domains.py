import asyncio
import aiohttp
import pandas as pd

df = pd.read_csv('data/three_char_words.csv')
tlds = ['io', 'me', 'ai', 'us', 'co', 'to']
semaphore = asyncio.Semaphore(10)

async def check(session, short, tld):
    domain = f"{short}.{tld}"
    url = f"https://rdap.org/domain/{domain}"

    async with semaphore:
        try:
            async with session.get(url, timeout=15) as resp:
                status = 'Available' if resp.status == 404 else 'Taken' if resp.status == 200 else 'Unknown'
        except:
            status = 'Error'

    print(f"{domain}: {status}")
    return {'short_word': short, 'tld': tld, 'domain': domain, 'status': status}

async def main():
    tasks = []
    async with aiohttp.ClientSession() as session:
        for short in df['three_char_word']:
            for tld in tlds:
                tasks.append(check(session, short, tld))
        results = await asyncio.gather(*tasks)

    results_df = pd.DataFrame(results)
    results_df.to_csv('../data/domain_availability.csv', index=False)

if __name__ == "__main__":
    asyncio.run(main())
