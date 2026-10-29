"""표준 라이브러리 SQLite 저장소. 프로젝트 격리와 낙관적 동시성 검사를 제공한다.

웹 서버 DB에 memory JSON을 저장해도 된다. 이 클래스는 로컬/워커용 선택 사항이며
SQL/파일 오류를 숨기지 않는다. LLM을 호출하지 않고 원문·캐시를 로컬에만 저장한다.
"""

import json
import sqlite3

from prolog_ai.memory.source import encode, validate_memory


class MemoryStore:
    def __init__(self, path):
        self.connection = sqlite3.connect(str(path))
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS character_memories "
            "(project_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)"
        )
        self.connection.commit()

    def load(self, project_id: str):
        row = self.connection.execute(
            "SELECT revision, payload FROM character_memories WHERE project_id = ?", (project_id,)
        ).fetchone()
        if row is None:
            return None
        memory = validate_memory(json.loads(row[1]))
        return {"revision": row[0], "memory": memory.model_dump()}

    def save(self, memory: dict, *, expected_revision: int) -> int:
        parsed = validate_memory(memory)
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected_revision은 0 이상의 정수여야 합니다")
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            row = self.connection.execute(
                "SELECT revision FROM character_memories WHERE project_id = ?", (parsed.project_id,)
            ).fetchone()
            current = row[0] if row else 0
            if current != expected_revision:
                raise ValueError("다른 작업이 기억을 갱신했습니다. 다시 읽은 뒤 저장하세요")
            revision = current + 1
            self.connection.execute(
                "INSERT INTO character_memories VALUES (?, ?, ?) "
                "ON CONFLICT(project_id) DO UPDATE SET revision=excluded.revision, payload=excluded.payload",
                (parsed.project_id, revision, encode(parsed.model_dump())),
            )
        return revision

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
