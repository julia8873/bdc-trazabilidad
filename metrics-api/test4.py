import asyncio
import os
import httpx
import json
import base64

async def main():
    github_token = os.getenv("GITHUB_TOKEN_AGENT")
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    owner, repo = "julia8873", "EDII-alumno1"
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/logs/interacciones/2026-08-22.jsonl?ref=main"
    
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers)
        b = r.json().get("content", "")
        if b:
            line = base64.b64decode(b).decode().splitlines()[0]
            print(json.dumps(json.loads(line), indent=2))

asyncio.run(main())
