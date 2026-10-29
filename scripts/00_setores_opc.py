"""Gera data/raw/anp_opc/setores_blocos_opc4_opc5.csv a partir dos relatorios de julgamento da CEL.

Blocos arrematados na OPC4 e na OPC5 em setores novos (Pelotas, Foz do Amazonas, parte de Santos)
nao constam da planilha de blocos ofertados R1-R17; o setor (AR, AP, AUP) da a lamina d'agua.
Uso: .venv/bin/python scripts/00_setores_opc.py data/raw/anp_opc
"""
import csv, re, sys
import pypdf

D = sys.argv[1]
linhas = set()
t = " ".join(p.extract_text() for p in pypdf.PdfReader(f"{D}/relatorio-julgamento-parcial.pdf").pages)
for s, b in re.findall(r"(S[A-Z]*-A[RUP]+\d+)\s*([A-Z]+-\s*M-?\s*\d{2,4})", t):
    linhas.add(("OPC4", s, re.sub(r"\s", "", b), "relatorio-julgamento-parcial.pdf (Relatorio 3/2024/SPL-e)"))
# 5o ciclo: transcrito do Quadro 2 do Relatorio 7/2025/SPL-e (ofertas vencedoras, blocos no mar)
OPC5 = {
    "SFZA-AP2": ["FZA-M-188", "FZA-M-190", "FZA-M-194", "FZA-M-196", "FZA-M-265", "FZA-M-267",
                 "FZA-M-334", "FZA-M-336", "FZA-M-403"],
    "SFZA-AP3": ["FZA-M-405", "FZA-M-473", "FZA-M-475", "FZA-M-477", "FZA-M-547", "FZA-M-549",
                 "FZA-M-619", "FZA-M-621"],
    "SFZA-AP4": ["FZA-M-1040", "FZA-M-1042"],
    "SP-AUP3": ["P-M-1670", "P-M-1672", "P-M-1741"],
    "SS-AP4": ["S-M-1358", "S-M-1603", "S-M-1912"],
    "SS-AR3": ["S-M-1038", "S-M-974"],
    "SS-AUP4": ["S-M-1484", "S-M-1605", "S-M-1819", "S-M-1821", "S-M-1914"],
    "SS-AUP5": ["S-M-1617"],
}
for s, bs in OPC5.items():
    for b in bs:
        linhas.add(("OPC5", s, b, "relatorio-complementar-5.pdf (Relatorio 7/2025/SPL-e)"))
with open(f"{D}/setores_blocos_opc4_opc5.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["ciclo", "setor", "bloco", "fonte"])
    w.writerows(sorted(linhas))
print(len(linhas), "linhas")
