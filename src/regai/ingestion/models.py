from dataclasses import dataclass


@dataclass
class Block:
    section_id: str
    section_path: str
    heading: str
    text: str
    block_type: str
    char_start: int
    char_end: int


@dataclass
class NormalizedDocument:
    title: str
    blocks: list[Block]


@dataclass
class Chunk:
    id: str
    regulation_id: str
    document_hash: str
    chunk_index: int
    section_id: str
    section_path: str
    heading: str
    text: str
    token_count: int
    char_start: int
    char_end: int
    block_type: str
