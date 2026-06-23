from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from server.utils.logger import logger

_GRAPHS_DIR = Path("server/graphs")


def _graph_dir(owner: str, repo: str) -> Path:
    d = _GRAPHS_DIR / f"{owner}_{repo}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def graph_exists(owner: str, repo: str) -> bool:
    return (_GRAPHS_DIR / f"{owner}_{repo}" / "graph.json").exists()


def get_graph_meta(owner: str, repo: str) -> Optional[dict]:
    meta_path = _GRAPHS_DIR / f"{owner}_{repo}" / "meta.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    if graph_exists(owner, repo):
        return {"status": "exists", "owner": owner, "repo": repo}
    return None


async def _build_from_path(owner: str, repo: str, src_path: str, gdir) -> dict:
    """Run the graphify AST pipeline on an already-checked-out repo and persist it."""
    try:
        from graphify.detect import detect
        from graphify.extract import collect_files, extract
        from graphify.build import build_from_json
        from graphify.cluster import cluster
        from graphify.analyze import god_nodes
        from graphify.export import to_json
    except ImportError:
        return {"status": "error", "message": "graphify not installed — run: pip install graphifyy"}

    logger.info(f"[graph_service] Detecting files in {src_path}")
    detection = await asyncio.to_thread(detect, Path(src_path))
    total_files = detection.get("total_files", 0)
    if total_files == 0:
        return {"status": "empty", "message": "No supported files found in repo"}

    code_files = []
    for f in detection.get("files", {}).get("code", []):
        fp = Path(f)
        code_files.extend(collect_files(fp) if fp.is_dir() else [fp])

    logger.info(f"[graph_service] AST extracting {len(code_files)} code files")
    if code_files:
        ast_result = await asyncio.to_thread(extract, code_files)
    else:
        ast_result = {"nodes": [], "edges": [], "input_tokens": 0, "output_tokens": 0}

    G = build_from_json(ast_result)
    if G.number_of_nodes() == 0:
        return {"status": "empty", "message": "Graph is empty after extraction"}

    communities = cluster(G)
    gods = god_nodes(G)
    to_json(G, communities, str(gdir / "graph.json"))

    # Plain-text summary of the codebase for LLM context
    summary_lines = [
        f"Repo: {owner}/{repo}",
        f"Files: {total_files}  |  Nodes: {G.number_of_nodes()}  |  Edges: {G.number_of_edges()}  |  Communities: {len(communities)}",
        "",
        "Core abstractions (most connected):",
    ]
    for g in gods[:8]:
        summary_lines.append(f"  • {g['label']}  [{g.get('source_file', '')}]")
    summary_lines.append("\nCode areas:")
    for cid, members in sorted(communities.items(), key=lambda x: -len(x[1]))[:8]:
        sample = [G.nodes[n].get("label", n) for n in members[:4]]
        summary_lines.append(f"  • {', '.join(sample)} ({len(members)} nodes)")

    meta = {
        "owner": owner, "repo": repo,
        "nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
        "communities": len(communities), "total_files": total_files,
        "god_nodes": [g["label"] for g in gods[:8]],
        "summary": "\n".join(summary_lines),
    }
    (gdir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"[graph_service] Done: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return {"status": "ok", **meta}


async def build_graph(owner: str, repo: str, token: str, repo_path: Optional[str] = None) -> dict:
    """Build/refresh the knowledge graph for a repo.

    If `repo_path` is given, builds from that existing clone (no re-clone) — used
    by the issue-fix flow so we clone once and graph the exact working tree.
    Otherwise clones a shallow copy to a tempdir and builds from that.
    """
    gdir = _graph_dir(owner, repo)

    if repo_path:
        logger.info(f"[graph_service] Building graph from existing clone: {repo_path}")
        return await _build_from_path(owner, repo, repo_path, gdir)

    clone_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
    with tempfile.TemporaryDirectory() as tmpdir:
        logger.info(f"[graph_service] Cloning {owner}/{repo}")
        clone = await asyncio.to_thread(
            subprocess.run,
            ["git", "clone", "--depth", "1", clone_url, tmpdir],
            capture_output=True, text=True,
        )
        if clone.returncode != 0:
            err = clone.stderr.replace(token, "***")
            logger.error(f"[graph_service] Clone failed: {err}")
            return {"status": "error", "message": "Clone failed — check token/repo name"}
        return await _build_from_path(owner, repo, tmpdir, gdir)


def relevant_files(owner: str, repo: str, question: str, limit: int = 5) -> list[str]:
    """Source files of the graph nodes most relevant to the question.

    Used to pull actual code into deep technical answers.
    """
    gpath = _GRAPHS_DIR / f"{owner}_{repo}" / "graph.json"
    if not gpath.exists():
        return []
    try:
        from networkx.readwrite import json_graph

        data = json.loads(gpath.read_text(encoding="utf-8"))
        try:
            G = json_graph.node_link_graph(data, edges="links")
        except TypeError:
            G = json_graph.node_link_graph(data)

        terms = [t.lower() for t in question.split() if len(t) > 3]
        scored = []
        for _nid, ndata in G.nodes(data=True):
            sf = ndata.get("source_file", "")
            if not sf:
                continue
            label = ndata.get("label", "").lower()
            score = sum(1 for t in terms if t in label or t in sf.lower())
            if score > 0:
                scored.append((score, sf))
        scored.sort(reverse=True)

        files: list[str] = []
        for _score, sf in scored:
            if sf not in files:
                files.append(sf)
            if len(files) >= limit:
                break

        # Fallback: no term match → the repo's CORE files (most-connected nodes).
        # These hold the main flows even when the user's wording isn't in the code.
        if not files:
            for nid, _deg in sorted(G.degree(), key=lambda x: -x[1]):
                sf = G.nodes[nid].get("source_file", "")
                if sf and sf not in files:
                    files.append(sf)
                if len(files) >= limit:
                    break
        return files
    except Exception as e:
        logger.error(f"[graph_service] relevant_files failed: {e}")
        return []


def query_graph(owner: str, repo: str, question: str, budget_tokens: int = 1500) -> str:
    """BFS from question-relevant nodes. Returns a compact context string for Claude."""
    gpath = _GRAPHS_DIR / f"{owner}_{repo}" / "graph.json"
    if not gpath.exists():
        return ""
    try:
        import networkx as nx
        from networkx.readwrite import json_graph

        data = json.loads(gpath.read_text(encoding="utf-8"))
        try:
            G = json_graph.node_link_graph(data, edges="links")
        except TypeError:
            G = json_graph.node_link_graph(data)

        terms = [t.lower() for t in question.split() if len(t) > 3]

        # Score nodes by term overlap
        scored = []
        for nid, ndata in G.nodes(data=True):
            label = ndata.get("label", "").lower()
            sf = ndata.get("source_file", "").lower()
            score = sum(1 for t in terms if t in label or t in sf)
            if score > 0:
                scored.append((score, nid))
        scored.sort(reverse=True)
        start_nodes = [nid for _, nid in scored[:3]]

        # Fall back to most-connected nodes if no match
        if not start_nodes:
            start_nodes = [n for n, _ in sorted(G.degree(), key=lambda x: -x[1])[:3]]

        # BFS depth 2
        subgraph_nodes = set(start_nodes)
        frontier = set(start_nodes)
        for _ in range(2):
            nxt = set()
            for n in frontier:
                for nb in G.neighbors(n):
                    if nb not in subgraph_nodes:
                        nxt.add(nb)
            subgraph_nodes.update(nxt)
            frontier = nxt

        lines = [f"[GRAPH: {owner}/{repo} — {G.number_of_nodes()} nodes total]"]
        lines.append("Key nodes:")
        for nid in start_nodes:
            d = G.nodes[nid]
            lines.append(f"  {d.get('label', nid)}  [{d.get('source_file', '')}:{d.get('source_location', '')}]")

        lines.append("\nEdges in subgraph:")
        seen_edges: set = set()
        for nid in subgraph_nodes:
            for nb in G.neighbors(nid):
                if nb in subgraph_nodes:
                    key = tuple(sorted([nid, nb]))
                    if key not in seen_edges:
                        seen_edges.add(key)
                        raw = G[nid][nb]
                        rel = raw.get("relation", "")
                        sf = raw.get("source_file", "")
                        lines.append(
                            f"  {G.nodes[nid].get('label', nid)} --{rel}--> {G.nodes[nb].get('label', nb)}  [{sf}]"
                        )
                        if len(seen_edges) >= 60:
                            break
            if len(seen_edges) >= 60:
                break

        context = "\n".join(lines)
        char_budget = budget_tokens * 4
        if len(context) > char_budget:
            context = context[:char_budget] + "\n[...graph truncated]"
        return context

    except Exception as e:
        logger.error(f"[graph_service] query failed: {e}")
        return ""
