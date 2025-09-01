import sys
sys.path.append('F:\Semantic_search_MVP\src')

import json

from metadata.schema import DocumentMetadata
from metadata.io import save_metadata, load_metadata, list_all_metadata

# Create a metadata object
meta = DocumentMetadata(
    doc_id="abc123",
    title="Test Document",
    authors=["Alice", "Bob"],
    year=2021,
    doc_type="book",
    tags=["economics", "finance"],
    source_path="data/pdfs/test.pdf"
)

# Save it
save_metadata(meta)

# Load it back
m2 = load_metadata("abc123")
print(m2.title, m2.year)

# List all metadata files
# all_metas = list_all_metadata()
# print([m.title for m in all_metas])
