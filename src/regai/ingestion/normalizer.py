import re
from regai.ingestion.models import Block, NormalizedDocument


def normalize(raw_text: str, title: str = "") -> NormalizedDocument:
    paragraphs = re.split(r"\n\s*\n", raw_text)
    blocks = []
    char_offset = 0
    section_counter = 0
    current_heading = ""
    current_section_path = ""
    current_section_id = "0"

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        lines = para.split("\n")
        first_line = lines[0].strip()
        m = re.match(r"^(#{1,3})\s+(.+)$", first_line)

        if m:
            body = "\n".join(lines[1:]).strip()
            has_body = len(body) > 0
            if has_body:
                section_counter += 1
                current_section_id = str(section_counter)
                current_heading = m.group(2).strip()
                current_section_path = current_heading
                blocks.append(Block(
                    section_id=current_section_id,
                    section_path=current_section_path,
                    heading=current_heading,
                    text=body,
                    block_type="paragraph",
                    char_start=char_offset,
                    char_end=char_offset + len(body),
                ))
                char_offset += len(body) + 1
            else:
                current_heading = m.group(2).strip()
                current_section_path = current_heading
        else:
            blocks.append(Block(
                section_id=current_section_id,
                section_path=current_section_path,
                heading=current_heading,
                text=para,
                block_type="paragraph",
                char_start=char_offset,
                char_end=char_offset + len(para),
            ))
            char_offset += len(para) + 1

    if not blocks:
        blocks.append(Block(
            section_id="0",
            section_path="",
            heading="",
            text=raw_text.strip(),
            block_type="paragraph",
            char_start=0,
            char_end=len(raw_text.strip()),
        ))

    return NormalizedDocument(title=title, blocks=blocks)
