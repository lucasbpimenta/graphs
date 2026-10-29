"""Monta a base harmonizada a partir dos arquivos da ANP em data/raw.

Saidas (UTF-8) em data/processed:
  participacoes_atuais.csv  contrato x empresa, carteira vigente (relacao-concessionarios)
  ofertas_vencedoras.csv    bloco x empresa, composicao no leilao (R1-R17, sem a 8a, que foi anulada)
  cessoes.csv               processo x situacao (antes/apos) x empresa
  empresas_aliases.csv      nome bruto -> empresa canonica -> grupo (para revisao manual)
"""
import re
from pathlib import Path

import pandas as pd

from empresas import canonica, chave, grupo, limpar

RAIZ = Path(__file__).resolve().parents[1]
RAW, OUT = RAIZ / "data" / "raw", RAIZ / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)


def ler(nome):
    df = pd.read_csv(RAW / nome, sep=";", encoding="latin-1", dtype=str).dropna(how="all")
    df.columns = [c.strip() for c in df.columns]
    return df.apply(lambda s: s.str.strip())


def num(s):
    """'1.234,56' ou '12,5' ou '47.5' ou 'R$6.750.000' -> float."""
    if pd.isna(s):
        return None
    s = str(s).replace("R$", "").strip()
    if "," in s or s.count(".") > 1:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def id_contrato(s):
    """Numero do contrato sem pontuacao, preservando sufixos de desmembramento (A, B)."""
    return re.sub(r"[^0-9A-Za-z]", "", str(s)).upper() if pd.notna(s) else None


def chave_contrato(s):
    """Numero do processo do contrato -> 'NNNNNN/AAAA[S]' (sequencial, ano, sufixo de desmembramento).

    Une os formatos das duas bases: '48610.009275/2005-71', '48000.003570/97-01 (BS-1)',
    '48610.215453/2022-09_OP3_BE', '486100038822000' (sem digito verificador) etc.
    """
    if pd.isna(s):
        return None
    s = str(s).split("(")[0].split("_")[0].upper()
    suf = re.search(r"([A-Z])\s*$", s)
    suf = suf.group(1) if suf else ""
    m = re.search(r"(\d{5})\.(\d{4,6})/(\d{2,4})", s.replace("48.000.", "48000."))
    if m:
        seq, resto = m.group(2), m.group(3)
    else:
        d = re.sub(r"\D", "", s)
        seq, resto = d[5:11], d[11:]
        if len(resto) not in (2, 4, 6) or len(d) < 13:
            return None
        if not (len(resto) in (4, 6) and 1995 <= int(resto[:4]) <= 2030):
            resto = resto[:2]
    ano = int(resto[:4]) if len(resto) >= 4 else int(resto[:2])
    ano = ano if ano > 1900 else (1900 + ano if ano > 50 else 2000 + ano)
    return f"{int(seq):06d}/{ano}{suf}"


# Regime e ano do leilao por codigo BID da relacao de concessionarios.
# ano=None: a confirmar (item G do prompt de busca).
def regime_bid(bid):
    if bid == "BID0":
        return "rodada_zero", 1998
    if bid in ("BID13AM",) or bid.startswith("AM") or bid.endswith("_AM"):
        anos = {"AM1": 2005, "AM2": 2006, "BID13AM": 2015, "OP1_AM": 2019, "OP2_AM": 2020, "OP4_AM": 2023}
        return "acumulacoes_marginais", anos.get(bid)
    m = re.fullmatch(r"BID(\d+)", bid)
    if m:
        anos = {1: 1999, 2: 2000, 3: 2001, 4: 2002, 5: 2003, 6: 2004, 7: 2005, 9: 2007, 10: 2008,
                11: 2013, 12: 2013, 13: 2015, 14: 2017, 15: 2018, 16: 2019, 17: 2021}
        return "rodada_concessao", anos.get(int(m.group(1)))
    m = re.fullmatch(r"OP(\d)_BE", bid)
    if m:
        return "oferta_permanente_concessao", {1: 2019, 2: 2020, 3: 2022, 4: 2023, 5: 2025}[int(m.group(1))]
    m = re.fullmatch(r"PP(\d)", bid)
    if m:
        return "partilha_rodada", {1: 2013, 2: 2017, 3: 2017, 4: 2018, 5: 2018, 6: 2019}[int(m.group(1))]
    m = re.fullmatch(r"OPP(\d)", bid)
    if m:
        return "oferta_permanente_partilha", {1: 2022, 2: 2023, 3: 2025}[int(m.group(1))]
    if bid == "CO_2010":
        return "cessao_onerosa", 2010
    if bid.startswith("EXC_CO"):
        return "excedentes_cessao_onerosa", {"EXC_CO_2020": 2019, "EXC_CO_2022": 2021}[bid]
    return "outros", None


ANO_RODADA = {1: 1999, 2: 2000, 3: 2001, 4: 2002, 5: 2003, 6: 2004, 7: 2005, 9: 2007, 10: 2008,
              11: 2013, 12: 2013, 13: 2015, 14: 2017, 15: 2018, 16: 2019, 17: 2021}
aliases = []


def registrar(nome, fonte):
    empresa, regra, revisar = canonica(nome)
    aliases.append((limpar(nome), fonte, empresa, regra, revisar))
    return empresa


# ---------------------------------------------------------------- carteira atual
r = ler("relacao-concessionarios.csv")
r["operador"] = r["Nome"].str.startswith("(Operador)")
r["empresa"] = [registrar(n, "relacao") for n in r["Nome"]]
reg = r["BID"].map(regime_bid)
atual = pd.DataFrame({
    "contrato": r["Número Contrato"].map(id_contrato),
    "chave": r["Número Contrato"].map(chave_contrato),
    "bid": r["BID"],
    "regime": [x[0] for x in reg],
    "ano_leilao": [x[1] for x in reg],
    "area": r["Nome Fantasia"],
    "bacia": r["Bacia"],
    "ambiente": r["Ambiente"],
    "fase": r["Fase"],
    "cnpj": r["CNPJ"].str.zfill(14),
    "nome_bruto": r["Nome"].map(limpar),
    "empresa": r["empresa"],
    "grupo": [grupo(e) for e in r["empresa"]],
    "participacao": r["% Participação"].map(num),
    "operador": r["operador"],
})

# ---------------------------------------------------------------- leiloes R1-R17
# Planilha da ANP com uma aba por rodada, em tres layouts:
#   R1-R4: uma linha por empresa, bloco so na primeira linha, % em fracao na coluna apos "Empresa",
#          operadora marcada com * antes ou depois do nome;
#   R5-R6: consorcio numa celula ("A (60%)*; B (40%)"), as vezes so o nome (=100%), as vezes
#          separado por virgula;
#   R7-R17: consorcio numa celula, como em R5-R6.
PARTE = re.compile(r"^\s*(\*)?\s*(.+?)\s*(?:\(([\d.,]+)\s*%\))?\s*(\*)?\s*$")
SEP = re.compile(r";|(?<=%\))\s*,|(?<=%\)\*)\s*,")


def ler_ofertas_xlsx(path):
    xl = pd.ExcelFile(path)
    linhas = []
    for aba in xl.sheet_names:
        rodada = int(re.search(r"\d+", aba).group())
        df = xl.parse(aba, header=None, dtype=object)
        h = next(i for i in range(10) if str(df.iat[i, 0]).strip() == "Bacia")
        cols = [str(c).strip() for c in df.iloc[h]]
        df = df.iloc[h + 1:].reset_index(drop=True)
        ib = cols.index("Bloco")
        ie = next(i for i, c in enumerate(cols) if c.startswith("Empresa"))
        ibon = next(i for i, c in enumerate(cols) if c.startswith("Bônus"))
        ipem = cols.index("PEM (R$)") if "PEM (R$)" in cols else None
        iset = cols.index("Setor") if "Setor" in cols else None
        if rodada <= 4:
            df["bloco"], df["bacia"] = df[ib].ffill(), df[0].ffill()
            df = df[df[ie].notna() & df[ie + 1].map(lambda v: isinstance(v, (int, float)))]
            for bloco, g in df.groupby("bloco", sort=False):
                if abs(g[ie + 1].astype(float).sum() - 1) > 0.001:
                    raise ValueError(f"R{rodada} {bloco}: participacoes nao somam 100%")
                for _, x in g.iterrows():
                    nome = str(x[ie])
                    linhas.append((rodada, x["bacia"], None, bloco, nome.strip("* "), 100 * float(x[ie + 1]),
                                   "*" in nome, g[ibon].iloc[0], None, len(g)))
        else:
            df = df[df[ib].notna() & df[ie].notna()]
            for _, x in df.iterrows():
                partes = [p for p in SEP.split(str(x[ie])) if p.strip()]
                for p in partes:
                    m = PARTE.match(p)
                    pct = num(m.group(3)) if m.group(3) else (100.0 if len(partes) == 1 else None)
                    linhas.append((rodada, x[0], x[iset] if iset is not None else None, str(x[ib]).strip(),
                                   m.group(2), pct, bool(m.group(1) or m.group(4)) or len(partes) == 1,
                                   x[ibon], x[ipem] if ipem is not None else None, len(partes)))
    return pd.DataFrame(linhas, columns=["rodada", "bacia", "setor", "bloco", "nome", "participacao",
                                         "operador", "bonus", "pem_rs", "n_empresas"])


o = ler_ofertas_xlsx(RAW / "anp_resultados" / "ofertas-vencedoras-rodadas-1-17.xlsx")
o["ano_leilao"] = o["rodada"].map(ANO_RODADA)
o["nome_bruto"] = o["nome"].map(limpar)
o["empresa"] = [registrar(n, "ofertas") for n in o["nome"]]
o["grupo"] = [grupo(e, a) for e, a in zip(o["empresa"], o["ano_leilao"])]
o["bonus"], o["pem_rs"] = o["bonus"].map(num), o["pem_rs"].map(num)
# atributos dos blocos ofertados (so ha para R9-R17)
b = ler("blocos-ofertados-rodadas.csv")
b["rodada"] = b["Rodada de Licitações"].str.extract(r"(\d+)").astype(int)
b = b.rename(columns={"Bloco": "bloco", "Habilitação Mínima": "habilitacao_minima",
                      "Bonus Mínimo": "bonus_minimo", "Localização": "localizacao"})
b["bonus_minimo"] = b["bonus_minimo"].map(num)
ofertas = o.merge(b[["rodada", "bloco", "habilitacao_minima", "bonus_minimo", "localizacao"]],
                  on=["rodada", "bloco"], how="left")[
    ["rodada", "ano_leilao", "bacia", "setor", "bloco", "localizacao", "habilitacao_minima", "bonus_minimo",
     "bonus", "pem_rs", "nome_bruto", "empresa", "grupo", "participacao", "operador", "n_empresas"]]

# ---------------------------------------------------------------- cessoes
c = ler("processos-cessao-contratos.csv")
c["data_aprovacao"] = pd.to_datetime(c["Data da aprovação"], dayfirst=True, errors="coerce")
com_pct = re.compile(r"^(\(\*\))?\s*(.+?)\s*[-–:]?\s*(\d+(?:[.,]\d+)?)\s*%\s*$")
sem_pct = re.compile(r"^(\(\*\))?\s*(.+?)\s+(\d+,\d+)\s*$")
linhas, nao_lidos = [], []
for idx, x in c.iterrows():
    ano = x["data_aprovacao"].year if pd.notna(x["data_aprovacao"]) else None
    m_area = re.search(r"\(([^)]+)\)\s*$", str(x["Contrato"]))
    for situacao, col in (("antes", "Antes da cessão"), ("apos", "Após efetivação da cessão")):
        if pd.isna(x[col]):
            continue
        for parte in re.split(r"\n+", x[col]):
            parte = parte.strip()
            if not parte:
                continue
            m = com_pct.match(parte) or sem_pct.match(parte)
            if m:
                nome, pct, op = m.group(2), num(m.group(3)), bool(m.group(1))
            else:
                nome, pct, op = re.sub(r"^\(\*\)\s*", "", parte), None, parte.startswith("(*)")
                nao_lidos.append(parte)
            emp = registrar(nome, "cessoes")
            linhas.append({
                "registro": idx, "processo": x["Processo de cessão"], "tipo_solicitacao": x["Tipo de solicitação ¹"],
                "muda_composicao": bool(re.search(r"[123]", str(x["Tipo de solicitação ¹"]))),
                "rodada": x["Rodada"], "contrato": id_contrato(str(x["Contrato"]).split("(")[0]),
                "chave": chave_contrato(x["Contrato"]),
                "area": m_area.group(1) if m_area else None, "bacia": x["Bacia"],
                "ambiente": x["Ambiente operacional"], "data_aprovacao": x["data_aprovacao"],
                "ano": ano, "situacao": situacao, "nome_bruto": limpar(nome), "empresa": emp,
                "grupo": grupo(emp, ano), "participacao": pct, "operador": op,
                "cedente": canonica(x["Cedente"])[0] if pd.notna(x["Cedente"]) else None,
                "cessionaria": canonica(x["Cessionária"])[0] if pd.notna(x["Cessionária"]) else None,
            })
cessoes = pd.DataFrame(linhas)

# ---------------------------------------------------------------- aliases
al = (pd.DataFrame(aliases, columns=["nome_bruto", "fonte", "empresa", "regra", "revisar"])
      .groupby(["nome_bruto", "empresa", "regra", "revisar"], as_index=False)
      .agg(fontes=("fonte", lambda s: ",".join(sorted(set(s)))), ocorrencias=("fonte", "size")))
# Sem regra explicita: variantes com a mesma chave (so muda sufixo, acento ou pontuacao)
# viram uma unica empresa, nomeada pela grafia mais frequente.
auto = al[al.regra == "auto"].assign(k=lambda d: d.nome_bruto.map(chave))
rep = (auto.sort_values("ocorrencias", ascending=False).drop_duplicates("k")
       .set_index("k")["nome_bruto"])
unifica = {n: rep[chave(n)] for n in auto.nome_bruto}
al["empresa"] = al["empresa"].replace(unifica)
al["grupo_atual"] = al["empresa"].map(grupo)
al = al.sort_values(["empresa", "nome_bruto"])

for df, ano in ((atual, None), (ofertas, "ano_leilao"), (cessoes, "ano")):
    df["empresa"] = df["empresa"].replace(unifica)
    df["grupo"] = [grupo(e, a) for e, a in zip(df["empresa"], df[ano] if ano else [None] * len(df))]
for col in ("cedente", "cessionaria"):
    cessoes[col] = cessoes[col].map(lambda n: unifica.get(n, n) if isinstance(n, str) else n)


# ---------------------------------------------------------------- lamina d'agua (contratos no mar)
# Corte de 400 m, como nas tabelas da ANP: rasa (0-400 m) ou profunda (profunda ou ultraprofunda).
# Fontes, em ordem: regime legalmente restrito ao polígono do pre-sal; localizacao do bloco nos
# blocos ofertados R5-R17 (cobre os blocos reofertados na OPC); ambiente operacional nas cessoes.
def bloco_n(s):
    return re.sub(r"(_(R\d+|OPP?\d|EXC|AM\d?)|-OPP?\d)$", "", str(s).strip().upper()).replace(" ", "")


def classe_lamina(s):
    s = str(s).lower()
    return "rasa" if "rasa" in s else "profunda" if "profunda" in s else None


loc = {}
xl = pd.ExcelFile(RAW / "anp_resultados" / "blocos-ofertados-rodadas-1-17.xlsx")
for aba in xl.sheet_names:
    df = xl.parse(aba, header=None, dtype=str)
    h = next(i for i in range(10) if str(df.iat[i, 0]).strip() == "Bacia")
    cols = [str(c).strip() for c in df.iloc[h]]
    if "Localização" in cols:
        for blc, lc in df.iloc[h + 1:, [cols.index("Bloco"), cols.index("Localização")]].values:
            if pd.notna(blc) and classe_lamina(lc):
                loc[bloco_n(blc)] = classe_lamina(lc)
# OPC: blocos ainda em oferta (planilha da ANP) e blocos arrematados nos ciclos 4 e 5 (setores AR/AP/AUP)
opc = pd.read_excel(RAW / "anp_opc" / "planilha-blocos-em-oferta-opc-v04.xlsx", header=3, dtype=str)
for blc, lc in opc[["BLOCO", "AMBIENTE OPERACIONAL"]].dropna().values:
    if classe_lamina(lc):
        loc[bloco_n(blc)] = classe_lamina(lc)
for blc, setor in pd.read_csv(RAW / "anp_opc" / "setores_blocos_opc4_opc5.csv")[["bloco", "setor"]].values:
    loc[bloco_n(blc)] = "rasa" if "-AR" in setor else "profunda"
amb_cessao = (cessoes.drop_duplicates("registro")
              .assign(c=lambda d: d.ambiente.map(classe_lamina)).dropna(subset=["c"])
              .groupby("chave").c.agg(lambda s: s.mode()[0]))
PRE_SAL = {"partilha_rodada", "oferta_permanente_partilha", "excedentes_cessao_onerosa", "cessao_onerosa"}


def lamina(r):
    if r.ambiente != "Mar":
        return None, None
    if r.regime in PRE_SAL:
        return "profunda", "pre_sal_legal"
    b = bloco_n(r.area)
    for cand in (b, re.sub(r"(?<=\d)[A-Z]$", "", b)):
        if cand in loc:
            return loc[cand], "blocos_ofertados"
    if r.chave in amb_cessao.index:
        return amb_cessao[r.chave], "cessoes"
    return None, None


lam = [lamina(r) for r in atual.itertuples()]
atual["lamina"], atual["fonte_lamina"] = [x[0] for x in lam], [x[1] for x in lam]
atual["pre_sal_legal"] = atual.regime.isin(PRE_SAL)
# blocos arrematados R1-R17: mar pelo nome do bloco (BM-..., X-M-...), lamina pela localizacao do bloco
ofertas["ambiente"] = ofertas.bloco.map(lambda b: "Mar" if re.search(r"^BM-|-M-", str(b).upper()) else "Terra")
ofertas["lamina"] = [loc.get(bloco_n(b)) if a == "Mar" else None for b, a in zip(ofertas.bloco, ofertas.ambiente)]

atual.to_csv(OUT / "participacoes_atuais.csv", index=False)
ofertas.to_csv(OUT / "ofertas_vencedoras.csv", index=False)
cessoes.to_csv(OUT / "cessoes.csv", index=False)
al.to_csv(OUT / "empresas_aliases.csv", index=False)

# ---------------------------------------------------------------- resumo
print(f"participacoes_atuais: {len(atual)} linhas, {atual.contrato.nunique()} contratos, "
      f"{atual.empresa.nunique()} empresas, {atual.grupo.nunique()} grupos")
print(f"ofertas_vencedoras:   {len(ofertas)} linhas, {len(ofertas.drop_duplicates(['rodada', 'bloco']))} blocos, "
      f"{ofertas.empresa.nunique()} empresas")
print(f"cessoes:              {len(cessoes)} linhas, {cessoes.registro.nunique()} registros, "
      f"{cessoes.empresa.nunique()} empresas; {len(nao_lidos)} entradas sem % reconhecido")
print(f"aliases:              {len(al)} nomes brutos -> {al.empresa.nunique()} empresas; "
      f"{(al.regra == 'auto').sum()} sem regra, {al.revisar.sum()} marcados para revisao")
ob = ofertas.drop_duplicates(["rodada", "bloco"])
print("blocos arrematados R1-R17 por ambiente e lamina:",
      ob.groupby(["ambiente", ob.lamina.fillna("sem_info")]).size().to_dict())
mar = atual[atual.ambiente == "Mar"].drop_duplicates("contrato")
print("lamina d'agua dos contratos no mar (por regime):")
print(mar.assign(lamina=mar.lamina.fillna("sem_info"))
      .pivot_table(index="regime", columns="lamina", values="contrato", aggfunc="size", fill_value=0))
