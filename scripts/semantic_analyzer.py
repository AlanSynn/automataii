#!/usr/bin/env python3
"""
Semantic Analyzer for God Class Refactoring
Analyzes Python code to identify semantic clusters for module extraction.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

# Try to import sentence_transformers for local embeddings
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


@dataclass(frozen=True)
class CodeChunk:
    """Represents a function/method in the source code."""
    name: str
    line_start: int
    line_end: int
    source: str
    docstring: str | None
    decorators: tuple[str, ...]
    is_private: bool
    calls: frozenset[str]  # Functions this chunk calls
    class_name: str | None = None

    @property
    def chunk_id(self) -> str:
        """Unique identifier for this chunk."""
        return f"{self.name}:{self.line_start}"

    @property
    def semantic_text(self) -> str:
        """Text used for semantic embedding."""
        parts = [self.name.replace("_", " ")]
        if self.docstring:
            parts.append(self.docstring)
        # Add function body keywords
        words = re.findall(r'\b[a-z_][a-z0-9_]*\b', self.source.lower())
        unique_words = set(words) - {"self", "return", "if", "else", "for", "while", "in", "and", "or", "not", "none", "true", "false"}
        parts.extend(list(unique_words)[:50])  # Limit to 50 unique words
        return " ".join(parts)


@dataclass
class AnalysisResult:
    """Result of semantic analysis."""
    file_path: str
    total_lines: int
    total_chunks: int
    chunks: list[CodeChunk]
    num_clusters: int
    cluster_assignments: list[int]  # chunk index -> cluster id
    cluster_analyses: list[dict]
    overall_cohesion: float
    embeddings: list[list[float]] | None = None


class CallGraphVisitor(ast.NodeVisitor):
    """AST visitor to extract function calls."""

    def __init__(self) -> None:
        self.calls: set[str] = set()

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            self.calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            # For self.method_name() calls
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
                self.calls.add(node.func.attr)
        self.generic_visit(node)


def extract_chunks(source_code: str, file_path: str) -> list[CodeChunk]:
    """Extract all function/method definitions as CodeChunks."""
    tree = ast.parse(source_code)
    lines = source_code.splitlines()
    chunks: list[CodeChunk] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    chunk = _extract_function_chunk(item, lines, class_name)
                    chunks.append(chunk)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Top-level functions (not in a class)
            if not any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree)):
                chunk = _extract_function_chunk(node, lines, None)
                chunks.append(chunk)

    # Sort by line number
    chunks.sort(key=lambda c: c.line_start)
    return chunks


def _extract_function_chunk(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    lines: list[str],
    class_name: str | None
) -> CodeChunk:
    """Extract a CodeChunk from a function AST node."""
    line_start = node.lineno
    line_end = node.end_lineno or node.lineno
    source = "\n".join(lines[line_start - 1:line_end])

    # Get docstring
    docstring = ast.get_docstring(node)

    # Get decorators
    decorators = tuple(
        ast.unparse(d) if hasattr(ast, 'unparse') else str(d)
        for d in node.decorator_list
    )

    # Extract function calls
    call_visitor = CallGraphVisitor()
    call_visitor.visit(node)

    return CodeChunk(
        name=node.name,
        line_start=line_start,
        line_end=line_end,
        source=source,
        docstring=docstring,
        decorators=decorators,
        is_private=node.name.startswith("_"),
        calls=frozenset(call_visitor.calls),
        class_name=class_name,
    )


def compute_embeddings_local(chunks: list[CodeChunk]) -> np.ndarray:
    """Compute embeddings using local sentence-transformers model."""
    if not HAS_SENTENCE_TRANSFORMERS:
        raise ImportError("sentence-transformers not installed. Run: pip install sentence-transformers")

    model = SentenceTransformer("all-MiniLM-L6-v2")
    texts = [chunk.semantic_text for chunk in chunks]
    embeddings = model.encode(texts, show_progress_bar=True)
    return np.array(embeddings)


def compute_embeddings_tfidf(chunks: list[CodeChunk]) -> np.ndarray:
    """Compute TF-IDF based embeddings (fallback, no external dependencies)."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    texts = [chunk.semantic_text for chunk in chunks]
    vectorizer = TfidfVectorizer(max_features=500, stop_words='english')
    embeddings = vectorizer.fit_transform(texts).toarray()
    return embeddings


def cluster_chunks(
    embeddings: np.ndarray,
    method: str = "kmeans",
    n_clusters: int | None = None,
    min_cohesion: float = 0.5
) -> tuple[list[int], int]:
    """Cluster chunks based on embeddings."""
    from sklearn.cluster import KMeans, DBSCAN
    from sklearn.metrics import silhouette_score

    n_samples = embeddings.shape[0]

    if n_clusters is None:
        # Auto-determine number of clusters using silhouette score
        best_score = -1
        best_k = 2
        max_k = min(10, n_samples // 3)

        for k in range(2, max_k + 1):
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embeddings)
            score = silhouette_score(embeddings, labels)
            if score > best_score:
                best_score = score
                best_k = k

        n_clusters = best_k

    if method == "kmeans":
        clusterer = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = clusterer.fit_predict(embeddings)
    elif method == "dbscan":
        clusterer = DBSCAN(eps=0.5, min_samples=2)
        labels = clusterer.fit_predict(embeddings)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    else:
        raise ValueError(f"Unknown clustering method: {method}")

    return [int(l) for l in labels], n_clusters


def analyze_clusters(
    chunks: list[CodeChunk],
    labels: list[int],
    embeddings: np.ndarray
) -> tuple[list[dict], float]:
    """Analyze each cluster and suggest module names."""
    from sklearn.metrics.pairwise import cosine_similarity

    unique_labels = sorted(set(labels))
    cluster_analyses = []
    cohesion_scores = []

    for cluster_id in unique_labels:
        if cluster_id == -1:  # DBSCAN noise
            continue

        cluster_indices = [i for i, l in enumerate(labels) if l == cluster_id]
        cluster_chunks = [chunks[i] for i in cluster_indices]
        cluster_embeddings = embeddings[cluster_indices]

        # Calculate cohesion (average pairwise similarity)
        if len(cluster_indices) > 1:
            sim_matrix = cosine_similarity(cluster_embeddings)
            # Get upper triangle (exclude diagonal)
            upper_tri = sim_matrix[np.triu_indices_from(sim_matrix, k=1)]
            cohesion = float(np.mean(upper_tri))
        else:
            cohesion = 1.0

        cohesion_scores.append(cohesion)

        # Extract common patterns for module name suggestion
        all_words = []
        for chunk in cluster_chunks:
            # Extract meaningful words from function names
            words = re.findall(r'[a-z]+', chunk.name.lower())
            all_words.extend(words)

        # Find most common meaningful words
        word_counts: dict[str, int] = {}
        skip_words = {"self", "get", "set", "is", "has", "do", "on", "handle", "init", "update", "create"}
        for word in all_words:
            if word not in skip_words and len(word) > 2:
                word_counts[word] = word_counts.get(word, 0) + 1

        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        top_words = [w for w, _ in sorted_words[:3]]

        # Suggest module name
        if top_words:
            suggested_name = "_".join(top_words) + "_module"
        else:
            suggested_name = f"cluster_{cluster_id}_module"

        cluster_analyses.append({
            "cluster_id": cluster_id,
            "chunk_ids": [chunks[i].chunk_id for i in cluster_indices],
            "chunk_names": [chunks[i].name for i in cluster_indices],
            "line_ranges": [(chunks[i].line_start, chunks[i].line_end) for i in cluster_indices],
            "suggested_module_name": suggested_name,
            "cohesion_score": round(cohesion, 3),
            "size": len(cluster_indices),
            "total_lines": sum(chunks[i].line_end - chunks[i].line_start + 1 for i in cluster_indices),
        })

    overall_cohesion = float(np.mean(cohesion_scores)) if cohesion_scores else 0.0
    return cluster_analyses, round(overall_cohesion, 3)


def analyze_file(
    file_path: str,
    provider: str = "tfidf",
    method: str = "kmeans",
    n_clusters: int | None = None,
    output_path: str | None = None
) -> AnalysisResult:
    """Main entry point: analyze a Python file and cluster its functions."""
    path = Path(file_path)
    source_code = path.read_text()
    total_lines = len(source_code.splitlines())

    # Extract chunks
    chunks = extract_chunks(source_code, file_path)
    print(f"Extracted {len(chunks)} code chunks from {file_path}")

    if len(chunks) < 2:
        raise ValueError("Need at least 2 functions to cluster")

    # Compute embeddings
    if provider == "local":
        embeddings = compute_embeddings_local(chunks)
    else:  # tfidf fallback
        embeddings = compute_embeddings_tfidf(chunks)

    print(f"Computed embeddings with shape {embeddings.shape}")

    # Cluster
    labels, n_clusters_found = cluster_chunks(embeddings, method, n_clusters)
    print(f"Found {n_clusters_found} clusters")

    # Analyze clusters
    cluster_analyses, overall_cohesion = analyze_clusters(chunks, labels, embeddings)

    result = AnalysisResult(
        file_path=str(path.absolute()),
        total_lines=total_lines,
        total_chunks=len(chunks),
        chunks=chunks,
        num_clusters=n_clusters_found,
        cluster_assignments=labels,
        cluster_analyses=cluster_analyses,
        overall_cohesion=overall_cohesion,
        embeddings=embeddings.tolist() if embeddings is not None else None,
    )

    # Save output
    if output_path:
        output_data = {
            "file_path": result.file_path,
            "total_lines": result.total_lines,
            "total_chunks": result.total_chunks,
            "num_clusters": result.num_clusters,
            "overall_cohesion": result.overall_cohesion,
            "cluster_analyses": result.cluster_analyses,
            "chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "name": c.name,
                    "line_start": c.line_start,
                    "line_end": c.line_end,
                    "is_private": c.is_private,
                    "calls": list(c.calls),
                    "cluster": int(labels[i]),  # Convert numpy int to Python int
                }
                for i, c in enumerate(chunks)
            ],
        }
        Path(output_path).write_text(json.dumps(output_data, indent=2))
        print(f"Analysis saved to {output_path}")

    return result


def print_analysis_report(result: AnalysisResult) -> None:
    """Print a human-readable analysis report."""
    print("\n" + "=" * 60)
    print("SEMANTIC ANALYSIS REPORT")
    print("=" * 60)
    print(f"File: {result.file_path}")
    print(f"Total Lines: {result.total_lines}")
    print(f"Total Functions: {result.total_chunks}")
    print(f"Clusters Found: {result.num_clusters}")
    print(f"Overall Cohesion: {result.overall_cohesion:.3f}")
    print("-" * 60)

    for cluster in sorted(result.cluster_analyses, key=lambda x: x["size"], reverse=True):
        print(f"\n📦 Cluster {cluster['cluster_id']}: {cluster['suggested_module_name']}")
        print(f"   Cohesion: {cluster['cohesion_score']:.3f} | Size: {cluster['size']} functions | {cluster['total_lines']} lines")
        print(f"   Functions:")
        for name in cluster["chunk_names"]:
            print(f"     - {name}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Semantic code analyzer for god class refactoring")
    parser.add_argument("file_path", help="Path to Python file to analyze")
    parser.add_argument("-o", "--output", help="Output JSON file path")
    parser.add_argument("--provider", choices=["local", "tfidf"], default="tfidf",
                        help="Embedding provider (default: tfidf)")
    parser.add_argument("--method", choices=["kmeans", "dbscan"], default="kmeans",
                        help="Clustering method (default: kmeans)")
    parser.add_argument("--clusters", type=int, default=None,
                        help="Number of clusters (default: auto)")

    args = parser.parse_args()

    result = analyze_file(
        args.file_path,
        provider=args.provider,
        method=args.method,
        n_clusters=args.clusters,
        output_path=args.output,
    )

    print_analysis_report(result)
