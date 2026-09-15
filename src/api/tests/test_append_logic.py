import asyncio
import base64
import httpx
import respx
import json

class MockGitHubProvider:
    def __init__(self):
        self.org = "test-org"
        self.pat = "fake-pat"
        self.headers = {
            "Authorization": f"token {self.pat}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.api_base = "https://api.github.com"
        
    async def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.api_base, headers=self.headers)

    # EXACT same method as in mapeo-api github_provider.py
    async def crear_commit_archivo(self, repo_url: str, path: str, content: str, message: str) -> str:
        repo_name = repo_url.split('/')[-1].replace('.git', '')
        
        import base64
        
        async with await self._get_client() as client:
            # Check if file exists to get its SHA and current content
            file_res = await client.get(f"/repos/{self.org}/{repo_name}/contents/{path}")
            
            final_content = content
            sha = None
            if file_res.status_code == 200:
                file_data = file_res.json()
                sha = file_data["sha"]
                # Decode existing content and append new content
                existing_content = base64.b64decode(file_data["content"]).decode('utf-8')
                final_content = existing_content + content
                
            encoded_content = base64.b64encode(final_content.encode('utf-8')).decode('utf-8')
            
            data = {
                "message": message,
                "content": encoded_content
            }
            if sha:
                data["sha"] = sha
                
            put_res = await client.put(
                f"/repos/{self.org}/{repo_name}/contents/{path}",
                json=data
            )
            
            if put_res.status_code in (200, 201):
                return put_res.json()["commit"]["sha"]
            else:
                raise Exception(f"Failed to create/update file {path} in {repo_name}: HTTP {put_res.status_code} {put_res.text}")

async def test_append_logic():
    provider = MockGitHubProvider()
    repo_url = "https://github.com/test-org/test-repo.git"
    path = "logs/discrepancias/2026-08-29.jsonl"
    new_content = '{"tipo_discrepancia": "NUEVA", "moodle_user_id": 4}\n'
    message = "Audit: test append"
    
    # Existing content
    existing_content = '{"tipo_discrepancia": "EXISTENTE", "moodle_user_id": 4}\n'
    existing_content_b64 = base64.b64encode(existing_content.encode('utf-8')).decode('utf-8')
    
    print("Iniciando test de append...")
    
    with respx.mock(assert_all_called=True) as mocker:
        # Mock GET to return existing file
        get_route = mocker.get(f"https://api.github.com/repos/test-org/test-repo/contents/{path}")
        get_route.return_value = httpx.Response(200, json={
            "sha": "old-file-sha",
            "content": existing_content_b64
        })
        
        # Mock PUT to verify payload
        put_route = mocker.put(f"https://api.github.com/repos/test-org/test-repo/contents/{path}")
        put_route.return_value = httpx.Response(200, json={
            "commit": {"sha": "new-commit-sha"}
        })
        
        commit_sha = await provider.crear_commit_archivo(repo_url, path, new_content, message)
        print(f"Commit SHA devuelto: {commit_sha}")
        
        assert put_route.called, "El PUT no fue llamado"
        
        request = put_route.calls[0].request
        payload = json.loads(request.content)
        
        sent_content_b64 = payload["content"]
        sent_content = base64.b64decode(sent_content_b64).decode('utf-8')
        
        print("\n--- Contenido enviado al API de GitHub ---")
        print(sent_content, end="")
        print("------------------------------------------")
        
        expected_content = existing_content + new_content
        assert sent_content == expected_content, f"El contenido enviado no coincide con la concatenación esperada.\nEsperado:\n{expected_content}\nEnviado:\n{sent_content}"
        assert payload["sha"] == "old-file-sha", "No se envió el SHA del archivo original para actualizarlo."
        
        print("\n✅ TEST SUPERADO: La lógica de append lee el base64 existente, concatena la nueva línea y hace PUT con ambas.")

if __name__ == "__main__":
    asyncio.run(test_append_logic())
