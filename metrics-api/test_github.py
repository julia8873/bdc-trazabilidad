import asyncio
import httpx
import os

async def main():
    repo_url = "https://github.com/julia8873/EDII-alumno1"
    token = os.environ.get("GITHUB_TOKEN_AGENT", "")
    print(f"Token present: {bool(token)}")
    url = "https://api.github.com/repos/julia8873/EDII-alumno1/contents/okf/interacciones?ref=main"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        print("Status:", resp.status_code)
        if resp.status_code != 200:
            print("Response:", resp.text)
        else:
            files = resp.json()
            if not isinstance(files, list): files = [files]
            for f in files: print(f["name"])

asyncio.run(main())
