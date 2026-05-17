import html
import sqlite3
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from regai.services.vector_index import VectorIndexService


def _sanitize_fts5(query: str) -> str:
    stripped = query.strip()
    if not stripped:
        return ""
    tokens = stripped.split()
    escaped = []
    for t in tokens:
        if t == "*":
            continue
        has_prefix = t.endswith("*")
        core = t.rstrip("*")
        core_escaped = core.replace('"', '""')
        if has_prefix:
            escaped.append(f'"{core_escaped}"*')
        else:
            escaped.append(f'"{core_escaped}"')
    return " AND ".join(escaped)


def _safe_snippet(raw: str) -> str:
    escaped = html.escape(raw)
    escaped = escaped.replace("&lt;mark&gt;", "<mark>")
    escaped = escaped.replace("&lt;/mark&gt;", "</mark>")
    return escaped


class SearchService:
    def __init__(self, db):
        self.db = db

    def search(
        self,
        user_id: str,
        query: str,
        filters: Optional[dict] = None,
        limit: int = 50,
    ) -> dict:
        filters = dict(filters) if filters else {}
        sanitized = _sanitize_fts5(query)
        if not sanitized:
            return {"results": [], "error": None, "count": 0}

        user_jurisdictions = self.db.execute(
            "SELECT jurisdiction FROM user_jurisdictions WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        allowed = {r["jurisdiction"] for r in user_jurisdictions}

        requested = filters.get("jurisdictions")
        if requested:
            jurisdictions = sorted(set(requested) & allowed)
        else:
            jurisdictions = sorted(allowed)

        if not jurisdictions:
            return {"results": [], "error": None, "count": 0}

        clauses = ["chunks_fts MATCH ?"]
        params: list = [sanitized]

        jur_placeholders = ",".join("?" for _ in jurisdictions)
        clauses.append(f"r.jurisdiction IN ({jur_placeholders})")
        params.extend(jurisdictions)

        if filters.get("regulator"):
            clauses.append("r.regulator = ?")
            params.append(filters["regulator"])

        if filters.get("document_type"):
            clauses.append("r.document_type = ?")
            params.append(filters["document_type"])

        if filters.get("date_from"):
            clauses.append("r.publication_date >= ?")
            params.append(filters["date_from"])

        if filters.get("date_to"):
            clauses.append("r.publication_date <= ?")
            params.append(filters["date_to"])

        where = " AND ".join(clauses)
        sql = f"""
            SELECT c.id AS chunk_id,
                   snippet(chunks_fts, 0, '<mark>', '</mark>', '...', 40) AS snippet,
                   c.heading, c.section_path, c.chunk_index,
                   r.id AS regulation_id, r.title, r.jurisdiction, r.regulator,
                   r.document_type, r.publication_date, r.effective_date, r.source_url
            FROM chunks_fts
            JOIN regulation_chunks c ON chunks_fts.rowid = c.rowid
            JOIN regulations r ON c.regulation_id = r.id
            WHERE {where}
            ORDER BY rank
            LIMIT ?
        """
        params.append(limit)
        try:
            rows = self.db.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            return {"results": [], "error": "fts_unavailable", "count": 0}

        results = []
        for r in rows:
            d = dict(r)
            d["snippet"] = _safe_snippet(d["snippet"])
            results.append(d)
        return {"results": results, "error": None, "count": len(results)}

    def browse(
        self,
        user_id: str,
        filters: Optional[dict] = None,
        limit: int = 50,
    ) -> dict:
        filters = dict(filters) if filters else {}

        user_jurisdictions = self.db.execute(
            "SELECT jurisdiction FROM user_jurisdictions WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        allowed = {r["jurisdiction"] for r in user_jurisdictions}

        requested = filters.get("jurisdictions")
        if requested:
            jurisdictions = sorted(set(requested) & allowed)
        else:
            jurisdictions = sorted(allowed)

        if not jurisdictions:
            return {"results": [], "error": None, "count": 0}

        clauses = []
        params: list = []

        jur_placeholders = ",".join("?" for _ in jurisdictions)
        clauses.append(f"r.jurisdiction IN ({jur_placeholders})")
        params.extend(jurisdictions)

        if filters.get("regulator"):
            clauses.append("r.regulator = ?")
            params.append(filters["regulator"])

        if filters.get("document_type"):
            clauses.append("r.document_type = ?")
            params.append(filters["document_type"])

        if filters.get("date_from"):
            clauses.append("r.publication_date >= ?")
            params.append(filters["date_from"])

        if filters.get("date_to"):
            clauses.append("r.publication_date <= ?")
            params.append(filters["date_to"])

        where = " AND ".join(clauses)
        # Push 10-chunk-per-regulation limit into SQL via window function for true diversity
        sql = f"""
            SELECT * FROM (
                SELECT c.id AS chunk_id,
                       c.text,
                       c.heading, c.section_path, c.chunk_index,
                       r.id AS regulation_id, r.title, r.jurisdiction, r.regulator,
                       r.document_type, r.publication_date, r.effective_date, r.source_url,
                       ROW_NUMBER() OVER (PARTITION BY r.id ORDER BY c.chunk_index) as rn
                FROM regulation_chunks c
                JOIN regulations r ON c.regulation_id = r.id
                WHERE {where}
            ) sub
            WHERE rn <= 10
            ORDER BY r.title, chunk_index
            LIMIT ?
        """
        params.append(limit)

        rows = self.db.execute(sql, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["snippet"] = html.escape(d["text"][:200])
            results.append(d)
        return {"results": results, "error": None, "count": len(results)}

    def semantic_search(
        self,
        user_id: str,
        vector: list[float],
        vector_index: "VectorIndexService",
        filters: Optional[dict] = None,
        limit: int = 50,
    ) -> dict:
        filters = dict(filters) if filters else {}

        user_jurisdictions = self.db.execute(
            "SELECT jurisdiction FROM user_jurisdictions WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        allowed = {r["jurisdiction"] for r in user_jurisdictions}

        requested = filters.get("jurisdictions")
        if requested:
            jurisdictions = sorted(set(requested) & allowed)
        else:
            jurisdictions = sorted(allowed)

        if not jurisdictions:
            return {"results": [], "error": None, "count": 0}

        query_filters = {}
        if filters.get("regulator"):
            query_filters["regulator"] = filters["regulator"]
        if filters.get("document_type"):
            query_filters["document_type"] = filters["document_type"]
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        if date_from or date_to:
            eff = {}
            if date_from:
                eff["$gte"] = date_from
            if date_to:
                eff["$lte"] = date_to
            query_filters["publication_date"] = eff

        try:
            hits = vector_index.query(vector, top_k=limit, filters=query_filters or None)
        except Exception:
            return {"results": [], "error": "vector_unavailable", "count": 0}

        if not hits:
            return {"results": [], "error": None, "count": 0}

        chunk_ids = [h.id for h in hits]

        jur_placeholders = ",".join("?" for _ in jurisdictions)
        chunk_placeholders = ",".join("?" for _ in chunk_ids)

        sql = f"""
            SELECT c.id AS chunk_id,
                   c.text,
                   c.heading, c.section_path, c.chunk_index,
                   r.id AS regulation_id, r.title, r.jurisdiction, r.regulator,
                   r.document_type, r.publication_date, r.effective_date, r.source_url
            FROM regulation_chunks c
            JOIN regulations r ON c.regulation_id = r.id
            WHERE c.id IN ({chunk_placeholders})
              AND r.jurisdiction IN ({jur_placeholders})
        """
        params = [*chunk_ids, *jurisdictions]

        try:
            rows = self.db.execute(sql, params).fetchall()
        except Exception:
            return {"results": [], "error": "search_unavailable", "count": 0}

        row_by_chunk = {r["chunk_id"]: dict(r) for r in rows}

        results = []
        for hit in hits:
            if hit.id in row_by_chunk:
                d = row_by_chunk[hit.id]
                text = d.pop("text", "")
                d["snippet"] = html.escape(text[:200])
                d["score"] = hit.score
                results.append(d)

        return {"results": results, "error": None, "count": len(results)}

    def hybrid_search(
        self,
        user_id: str,
        query: str,
        vector: list[float],
        vector_index: "VectorIndexService",
        filters: Optional[dict] = None,
        limit: int = 50,
    ) -> dict:
        filters = dict(filters) if filters else {}
        fts_result = self.search(user_id, query, filters=filters, limit=50)
        sem_result = self.semantic_search(user_id, vector, vector_index, filters=filters, limit=50)

        if fts_result["error"] and sem_result["error"]:
            return {"results": [], "error": "search_unavailable", "count": 0}
        if fts_result["error"]:
            sem_result["error"] = fts_result["error"]
            return sem_result
        if sem_result["error"]:
            fts_result["error"] = sem_result["error"]
            return fts_result

        K = 60
        rrf_scores = {}
        for rank, r in enumerate(fts_result["results"]):
            cid = r["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (K + rank + 1)
        for rank, r in enumerate(sem_result["results"]):
            cid = r["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (K + rank + 1)

        top_chunk_ids = [cid for cid, _ in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:limit]]
        if not top_chunk_ids:
            return {"results": [], "error": None, "count": 0}

        user_jurisdictions = self.db.execute(
            "SELECT jurisdiction FROM user_jurisdictions WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        allowed = {r["jurisdiction"] for r in user_jurisdictions}
        requested = filters.get("jurisdictions")
        if requested:
            jurisdictions = sorted(set(requested) & allowed)
        else:
            jurisdictions = sorted(allowed)

        chunk_placeholders = ",".join("?" for _ in top_chunk_ids)
        jur_placeholders = ",".join("?" for _ in jurisdictions)

        sql = f"""
            SELECT c.id AS chunk_id,
                   c.text, c.heading, c.section_path, c.chunk_index,
                   r.id AS regulation_id, r.title, r.jurisdiction, r.regulator,
                   r.document_type, r.publication_date, r.effective_date, r.source_url
            FROM regulation_chunks c
            JOIN regulations r ON c.regulation_id = r.id
            WHERE c.id IN ({chunk_placeholders})
              AND r.jurisdiction IN ({jur_placeholders})
        """
        params = [*top_chunk_ids, *jurisdictions]
        try:
            rows = self.db.execute(sql, params).fetchall()
        except Exception:
            return {"results": [], "error": "search_unavailable", "count": 0}

        row_by_chunk = {r["chunk_id"]: dict(r) for r in rows}
        results = []
        for cid in top_chunk_ids:
            if cid in row_by_chunk:
                d = row_by_chunk[cid]
                text = d.pop("text", "")
                d["snippet"] = html.escape(text[:200])
                d["rrf_score"] = rrf_scores[cid]
                results.append(d)
        return {"results": results, "error": None, "count": len(results)}
