import asyncio
from metrics_api.main import get_all_jsonls_from_dir
import os

async def main():
    repo_url = "https://github.com/julia8873/EDII-alumno1"
    os.environ["GITHUB_TOKEN_AGENT"] = os.environ.get("GITHUB_TOKEN_AGENT", "")
    print("logs/interacciones:")
    logs = await get_all_jsonls_from_dir(repo_url, "logs/interacciones")
    for l in logs: print(l.get('timestamp', 'No timestamp'))
    print("\nokf/interacciones:")
    okf = await get_all_jsonls_from_dir(repo_url, "okf/interacciones")
    for o in okf: print(o.get('timestamp', 'No timestamp'))

asyncio.run(main())
