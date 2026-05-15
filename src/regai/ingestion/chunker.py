import re
from regai.ingestion.models import Block, NormalizedDocument, Chunk

TARGET_MIN = 800
TARGET_MAX = 1200
HARD_MAX = 1500


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _split_oversized_block(block: Block) -> list[Block]:
    token_count = estimate_tokens(block.text)
    if token_count <= HARD_MAX:
        return [block]

    parts: list[str] = []
    current = ""
    for sentence in re.split(r"(?<=[.!?])\s+", block.text):
        candidate = (current + " " + sentence).strip() if current else sentence
        if estimate_tokens(candidate) > HARD_MAX and current:
            parts.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        parts.append(current)

    if len(parts) <= 1:
        max_chars = HARD_MAX * 4
        parts = [block.text[i:i + max_chars] for i in range(0, len(block.text), max_chars)]

    sub_blocks = []
    offset = block.char_start
    for p in parts:
        sub_blocks.append(Block(
            section_id=block.section_id,
            section_path=block.section_path,
            heading=block.heading,
            text=p,
            block_type=block.block_type,
            char_start=offset,
            char_end=offset + len(p),
        ))
        offset += len(p) + 1
    return sub_blocks if sub_blocks else [block]


def chunk_document(doc: NormalizedDocument, document_hash: str, regulation_id: str) -> list[Chunk]:
    sections: dict[str, list[Block]] = {}
    section_order: list[str] = []
    for block in doc.blocks:
        if block.section_id not in sections:
            section_order.append(block.section_id)
        sections.setdefault(block.section_id, []).append(block)

    chunks: list[Chunk] = []
    global_index = 0

    for section_id in section_order:
        raw_blocks = sections[section_id]

        blocks: list[Block] = []
        for b in raw_blocks:
            blocks.extend(_split_oversized_block(b))

        buffer: list[Block] = []
        buffer_tokens = 0

        for block in blocks:
            block_tokens = estimate_tokens(block.text)

            if not buffer:
                buffer.append(block)
                buffer_tokens = block_tokens
                continue

            if buffer_tokens + block_tokens > HARD_MAX:
                chunks.append(_make_chunk(buffer, document_hash, regulation_id, section_id, global_index))
                global_index += 1
                buffer = [block]
                buffer_tokens = block_tokens
            elif buffer_tokens >= TARGET_MIN and buffer_tokens + block_tokens > TARGET_MAX:
                chunks.append(_make_chunk(buffer, document_hash, regulation_id, section_id, global_index))
                global_index += 1
                buffer = [block]
                buffer_tokens = block_tokens
            else:
                buffer.append(block)
                buffer_tokens += block_tokens

        if buffer:
            chunks.append(_make_chunk(buffer, document_hash, regulation_id, section_id, global_index))
            global_index += 1

    return chunks


def _make_chunk(
    blocks: list[Block],
    document_hash: str,
    regulation_id: str,
    section_id: str,
    chunk_index: int,
) -> Chunk:
    text = "\n\n".join(b.text for b in blocks)
    token_count = estimate_tokens(text)
    first = blocks[0]
    last = blocks[-1]

    return Chunk(
        id=f"{document_hash}:{section_id}:{chunk_index}",
        regulation_id=regulation_id,
        document_hash=document_hash,
        chunk_index=chunk_index,
        section_id=section_id,
        section_path=first.section_path,
        heading=first.heading,
        text=text,
        token_count=token_count,
        char_start=first.char_start,
        char_end=last.char_end,
        block_type=first.block_type,
    )
