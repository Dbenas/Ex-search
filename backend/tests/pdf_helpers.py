"""Builds tiny, valid PDFs for extraction tests without extra dependencies."""

Line = str | tuple[str, float]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(lines: list[Line], default_size: float = 11) -> bytes:
    """Single-page PDF; each line is text or (text, font size in points)."""
    ops, y = [], 800.0
    for line in lines:
        text, size = (line, default_size) if isinstance(line, str) else line
        y -= size + 4
        ops.append(f"BT /F1 {size} Tf 50 {y:.1f} Td ({_escape(text)}) Tj ET")
    stream = "\n".join(ops).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return bytes(out)


# Fictitious profile in the layout LinkedIn uses for "Save to PDF":
# name 26pt > main sections 15.75pt > sidebar sections 13pt > text 12pt > details 10.5pt.
LINKEDIN_PROFILE: list[Line] = [
    ("Contato", 13),
    ("joana.prado@example.com", 10.5),
    ("www.linkedin.com/in/joana-", 10.5),
    ("prado-9f8e7d (LinkedIn)", 10.5),
    ("Principais competências", 13),
    ("Fusões e aquisições", 10.5),
    ("Valuation", 10.5),
    ("Joana Prado", 26),
    ("CFO | Tecnologia | Captação e M&A", 12),
    ("São Paulo, Brasil", 12),
    ("Resumo", 15.75),
    ("Executiva de finanças com 17 anos em empresas de tecnologia. Conduziu", 12),
    ("rodadas Series B e C e a venda de uma scale-up para fundo de private equity.", 12),
    ("Experiência", 15.75),
    ("Nuvem Pagamentos", 12),
    ("CFO", 12),
    ("março de 2021 - Present (5 anos 6 meses)", 10.5),
    ("São Paulo, Brasil", 10.5),
    ("Grupo Horizonte", 12),
    ("Diretora de Planejamento Financeiro", 12),
    ("janeiro de 2015 - fevereiro de 2021 (6 anos 2 meses)", 10.5),
    ("Formação acadêmica", 15.75),
    ("Universidade de São Paulo", 12),
    ("Economia · (2004 - 2008)", 10.5),
    ("Page 1 of 1", 9),
]
