#!/usr/bin/env python3
import os
import sys
import tomllib
import glob

import re

def find_tomls(base_dirs):
    tomls = []
    for d in base_dirs:
        for root, _, files in os.walk(d):
            if "pyproject.toml" in files:
                tomls.append(os.path.join(root, "pyproject.toml"))
    return tomls

def build_graph(tomls, workspace_root):
    graph = {}
    
    # 1. Parse from pyproject.toml
    for t in tomls:
        with open(t, "rb") as f:
            data = tomllib.load(f)
            name = data.get("project", {}).get("name")
            if not name:
                continue
            deps = data.get("project", {}).get("dependencies", [])
            clean_deps = []
            for d in deps:
                pkg = d.split(">")[0].split("<")[0].split("=")[0].split("~")[0].strip()
                clean_deps.append(pkg)
            if name not in graph:
                graph[name] = []
            graph[name].extend(clean_deps)

    # 2. Parse from integracion-bdc.md table
    md_path = os.path.join(workspace_root, "bdc-trazabilidad", "docs", "integracion-bdc.md")
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("|") and "->" in line:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 3:
                        direction = parts[1]
                        if "->" in direction:
                            left, right = [x.strip() for x in direction.split("->")]
                            # llm-wiki-assistant -> bdc-trazabilidad means bdc-trazabilidad depends on llm-wiki-assistant
                            provider, consumer = left, right
                            if consumer not in graph:
                                graph[consumer] = []
                            graph[consumer].append(provider)
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
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    base_dirs = [
        os.path.join(workspace_root, "bdc-trazabilidad"),
        os.path.join(workspace_root, "llm-wiki-assistant")
    ]
    
    print("Analizando dependencias en pyproject.toml y docs/integracion-bdc.md...")
    tomls = find_tomls(base_dirs)
        
    graph = build_graph(tomls, workspace_root)
    
    cycle = has_cycle(graph)
    if cycle:
        print("[ERROR] Dependencia cíclica detectada en el grafo:")
        print(" -> ".join(cycle))
        sys.exit(1)
        
    print("[OK] Grafo limpio. No se detectaron ciclos.")
    sys.exit(0)
