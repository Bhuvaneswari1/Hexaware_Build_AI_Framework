"""API embeddings in live mode; a labeled local embedding fixture in demo mode."""
import hashlib
import re
from functools import lru_cache
from langchain_core.embeddings import Embeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from .config import live, RUNTIME
from .business import rows

class DemoEmbeddings(Embeddings):
    def embed_query(self, text):
        vector = [0.0] * 256
        for token in re.findall(r'\w+', text.lower()):
            vector[int(hashlib.sha256(token.encode()).hexdigest(),16) % 256] += 1
        norm = sum(x*x for x in vector) ** 0.5 or 1
        return [x/norm for x in vector]

    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]

@lru_cache(maxsize=2)
def store(is_live):
    if is_live:
        from langchain_openai import OpenAIEmbeddings
        embeddings = OpenAIEmbeddings(model='text-embedding-3-small')
    else:
        embeddings = DemoEmbeddings()
    name = 'hr-policy-live' if is_live else 'hr-policy-demo'
    db = Chroma(collection_name=name, embedding_function=embeddings,
                persist_directory=str(RUNTIME / name))
    policies = rows('policies.csv')
    # Upsert stable IDs: reruns do not duplicate policy chunks.
    db.add_documents([Document(page_content=r['topic'] + ': ' + r['text'],
                     metadata={'policy_id': r['policy_id']}) for r in policies],
                     ids=[r['policy_id'] for r in policies])
    return db

def retrieve(query):
    docs = store(live()).similarity_search(query, k=2)
    return [{'policy_id': d.metadata['policy_id'], 'text': d.page_content} for d in docs]

if __name__ == '__main__':
    store(live())
    print('Indexed four synthetic HR policies.')
