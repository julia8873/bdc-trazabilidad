#!/usr/bin/env python3
import os
import sys
import tomllib
import glob

def find_tomls(base_dirs):
    tomls = []
    for d in base_dirs:
        for root, _, files in os.walk(d):
            if "pyproject.toml" in files:
                tomls.append(os.path.join(root, "pyproject.toml"))
    return tomls

def build_graph(tomls):
    graph = {}
    for t in tomls:
        with open(t, "rb") as f:
            data = tomllib.load(f)
            name = data.get("project", {}).get("name")
            if not name:
                continue
            deps = data.get("project", {}).get("dependencies", [])
            # Extract basic package name assuming PEP 508 format (e.g. "pkg>=1.0" -> "pkg")
            clean_deps = []
            for d in deps:
                pkg = d.split(">")[0].split("<")[0].split("=")[0].split("~")[0].strip()
                clean_deps.append(pkg)
            graph[name] = clean_deps
    return graph

def has_cycle(graph):
    visited = set()
    rec_stack = set()
    path = []

    def dfs(node):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if neighbor in graph: # Only follow local packages
                    cycle_path = dfs(neighbor)
                    if cycle_path:
                        return cycle_path
            elif neighbor in rec_stack:
                return path + [neighbor]
                
        rec_stack.remove(node)
        path.pop()
        return None

    for node in graph:
        if node not in visited:
            cycle = dfs(node)
            if cycle:
                return cycle
    return None

if __name__ == "__main__":
    # Scan both repositories
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    base_dirs = [
        os.path.join(workspace_root, "bdc-trazabilidad"),
        os.path.join(workspace_root, "llm-wiki-assistant")
    ]
    
    print("Analizando dependencias en pyproject.toml...")
    tomls = find_tomls(base_dirs)
    if not tomls:
        print("[OK] No se encontraron manifiestos.")
        sys.exit(0)
        
    graph = build_graph(tomls)
    
    cycle = has_cycle(graph)
    if cycle:
        print("[ERROR] Dependencia cíclica detectada en el grafo de módulos:")
        print(" -> ".join(cycle))
        sys.exit(1)
        
    print("[OK] Grafo limpio. No se detectaron ciclos.")
    sys.exit(0)
