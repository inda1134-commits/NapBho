import re
from collections import Counter
from typing import Any

def chunk_pages(pages: list[dict], chunk_chars: int = 1100, overlap: int = 150) -> list[dict]:
    chunks = []
    for p in pages:
        text = re.sub(r"\s+", " ", p.get("text", "")).strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_chars)
            chunk = text[start:end]
            chunks.append({"text":chunk, "filename":p["filename"], "page":p["page"]})
            if end == len(text):
                break
            start = max(start + 1, end - overlap)
    return chunks

def keyword_search(chunks: list[dict], query: str, top_k: int = 5) -> list[dict]:
    """한국어 키워드 검색. 구체적인 제도명과 핵심어 일치를 일반 단어보다 우선합니다."""
    terms = list(dict.fromkeys(re.findall(r"[가-힣A-Za-z0-9]{2,}", query.lower())))
    if not terms:
        return []
    scored = []
    for chunk in chunks:
        text = str(chunk.get("text", "")).lower()
        filename = str(chunk.get("filename", "")).lower()
        score = sum(min(text.count(term), 4) * (3 if len(term) >= 4 else 1) for term in terms)
        score += sum(5 for term in terms if term in filename and len(term) >= 3)
        # 긴 제도명 구문 일치에 가산점을 주어 일반적인 '신청/절차' 문서가 앞서지 않게 합니다.
        for phrase in re.findall(r"권리보호\([^)]{2,}\)|[가-힣]{2,12}(?:요청|청구|신청)", query):
            if phrase.lower() in text:
                score += 12
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [dict(c, score=s) for s, c in scored[:top_k]]

def chroma_search(chunks: list[dict], query: str, api_key: str, collection_name: str, persist_path: str, top_k: int = 5) -> list[dict]:
    """OpenAI 임베딩을 사용한 선택적 Chroma 검색. 실패 시 호출자가 키워드 검색으로 폴백."""
    import chromadb
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    chroma = chromadb.PersistentClient(path=persist_path)
    collection = chroma.get_or_create_collection(name=collection_name)
    # 업로드 문서 청크를 현재 컬렉션에 반영. collection은 권리구제 방식별로 구분한다.
    if chunks:
        ids, docs, metas = [], [], []
        for i, c in enumerate(chunks):
            ids.append(f"{c['filename']}::{c['page']}::{i}")
            docs.append(c["text"])
            metas.append({"filename":c["filename"], "page":int(c["page"])})
        # idempotent upsert
        collection.upsert(ids=ids, documents=docs, metadatas=metas)
    emb = client.embeddings.create(model="text-embedding-3-small", input=query).data[0].embedding
    result = collection.query(query_embeddings=[emb], n_results=top_k, include=["documents","metadatas","distances"])
    out = []
    for i, doc in enumerate((result.get("documents") or [[]])[0]):
        meta = (result.get("metadatas") or [[]])[0][i]
        dist = (result.get("distances") or [[]])[0][i]
        source_filename = meta.get("source_filename") or meta.get("filename") or "문서"
        out.append({"text":doc, "filename":source_filename, "source_filename":source_filename, "page":meta.get("page","?"), "score":1-float(dist)})
    return out


def index_documents(chunks: list[dict], api_key: str, collection_name: str, persist_path: str) -> int:
    """PDF 청크를 OpenAI 임베딩과 함께 영구 Chroma 컬렉션에 저장합니다."""
    if not chunks:
        raise ValueError("인덱싱할 텍스트가 없습니다. PDF의 텍스트 추출 가능 여부를 확인하세요.")
    import hashlib
    import chromadb
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    chroma = chromadb.PersistentClient(path=persist_path)
    collection = chroma.get_or_create_collection(name=collection_name)
    ids, docs, metas = [], [], []
    for c in chunks:
        identity = f"{c.get('filename','')}|{c.get('page','')}|{c.get('text','')}"
        ids.append(hashlib.sha256(identity.encode('utf-8')).hexdigest())
        docs.append(c['text'])
        source_filename = str(c.get('filename', '참고자료'))
        metas.append({'filename': source_filename, 'source_filename': source_filename, 'page': int(c.get('page', 0) or 0)})
    batch_size = 64
    for start in range(0, len(docs), batch_size):
        batch_docs = docs[start:start + batch_size]
        response = client.embeddings.create(model="text-embedding-3-small", input=batch_docs)
        embeddings = [item.embedding for item in response.data]
        collection.upsert(ids=ids[start:start + batch_size], documents=batch_docs,
                          metadatas=metas[start:start + batch_size], embeddings=embeddings)
    return len(docs)


def chroma_collection_count(collection_name: str, persist_path: str) -> int:
    """컬렉션이 존재하면 저장된 청크 수를 반환합니다."""
    import chromadb
    chroma = chromadb.PersistentClient(path=persist_path)
    try:
        return int(chroma.get_collection(name=collection_name).count())
    except Exception:
        return 0


def prioritize_route_evidence(results: list[dict], route: str, top_k: int = 8) -> list[dict]:
    """선정된 권리보호 유형과 직접 일치하는 자료를 앞세워 정렬합니다."""
    route_terms = [term for term in re.findall(r"권리보호\([^)]*\)|[가-힣A-Za-z0-9]{2,}", route) if term]
    def rank(item: dict) -> tuple[int, float]:
        body = str(item.get("text", "")).replace(" ", "")
        filename = str(item.get("filename", "")).replace(" ", "")
        exact = 1 if route.replace(" ", "") in body or route.replace(" ", "") in filename else 0
        hits = sum(1 for term in route_terms if term.replace(" ", "") in body or term.replace(" ", "") in filename)
        return (exact * 100 + hits, float(item.get("score", 0) or 0))
    return sorted(results, key=rank, reverse=True)[:top_k]
