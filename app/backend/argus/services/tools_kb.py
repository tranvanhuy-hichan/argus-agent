"""Tool kb_search: tìm trong kho tài liệu người dùng đã thêm và trả đoạn kèm nguồn để agent trích dẫn."""
from . import knowledge
from .tools import tool


def format_hits(hits: list[dict]) -> str:
    out = []
    for i, h in enumerate(hits, start=1):
        text = " ".join(h["text"].split())
        out.append(f"[{i}] thẻ nguồn: [[src:{h['doc_id']}|{h['name']}|{h['loc']}]]\n{text[:900]}")
    return "\n\n".join(out)


@tool("kb_search", "Tìm trong kho tài liệu của người dùng (PDF, Word, Excel, PowerPoint, văn bản đã thêm ở mục Tài liệu). "
      "Mỗi đoạn trả về kèm một thẻ nguồn dạng [[src:...]]; khi trả lời chèn nguyên văn thẻ đó ở cuối ý tương ứng.",
      {"query": ("string", "câu hỏi hoặc từ khóa cần tìm trong tài liệu"), "limit": ("integer", "số đoạn tối đa (mặc định 6)")}, required=["query"])
def kb_search(ctx, query, limit=6):
    return format_hits(knowledge.search(query, int(limit))) or "không tìm thấy đoạn nào liên quan trong kho tài liệu"
