"""Build small valid DOCX files; each row is a list of cell texts for one table row."""
from io import BytesIO

from docx import Document


def make_docx(*paragraphs: str, table: list[list[str]] | None = None) -> bytes:
    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    if table:
        word_table = document.add_table(rows=len(table), cols=len(table[0]))
        for row, values in zip(word_table.rows, table):
            for cell, value in zip(row.cells, values):
                cell.text = value
    output = BytesIO()
    document.save(output)
    return output.getvalue()
