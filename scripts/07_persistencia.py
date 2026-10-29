"""Padrao transversal: persistencia de parceiros entre leiloes offshore.

Eventos: leiloes no mar com composicao conhecida no arremate, agregados por ano.
  - rodadas R1-R17: ofertas_vencedoras (composicao oficial, grupo no ano do leilao);
  - OPC, partilha, OPP e excedentes: composicao_adjudicacao (reconstruida; grupo no ano do leilao).
Unidade de analise: par de grupos em que os dois arremataram ao menos um bloco no mar naquele ano.
Desfecho: o par arrematou junto (mesmo bloco ou contrato) naquele ano.
Variavel de interesse: o par ja tinha arrematado junto em algum ano anterior.
Controles: log do numero de unidades arrematadas por cada grupo no ano, par com a Petrobras e
efeitos fixos de ano. Logit com erros agrupados por par.
Saidas em data/processed: persistencia_pares.csv, persistencia_modelo.csv
"""
import warnings
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"
pd.set_option("display.width", 220, "display.max_columns", 20)

# ---------------------------------------------------------------- eventos
of = pd.read_csv(PROC / "ofertas_vencedoras.csv")
of = of[of.ambiente == "Mar"].assign(unidade=lambda d: "R" + d.rodada.astype(str) + "|" + d.bloco)
ad = pd.read_csv(PROC / "composicao_adjudicacao.csv")
OUTROS = {"oferta_permanente_concessao", "partilha_rodada", "oferta_permanente_partilha",
          "excedentes_cessao_onerosa"}
ad = ad[(ad.ambiente == "Mar") & ad.regime.isin(OUTROS) & ad.ano_leilao.notna()].assign(unidade=lambda d: d.contrato)
ev = pd.concat([of[["ano_leilao", "unidade", "grupo"]], ad[["ano_leilao", "unidade", "grupo"]]])
ev = ev.drop_duplicates().astype({"ano_leilao": int})

# ---------------------------------------------------------------- painel de pares
anteriores = set()  # pares que ja arremataram juntos
linhas = []
for ano, e in ev.groupby("ano_leilao"):
    ativos = e.groupby("grupo").unidade.nunique()
    juntos = set()
    for _, g in e.groupby("unidade"):
        juntos |= set(combinations(sorted(set(g.grupo)), 2))
    for u, v in combinations(sorted(ativos.index), 2):
        linhas.append({"ano": ano, "u": u, "v": v, "juntos": int((u, v) in juntos),
                       "ja_juntos": int((u, v) in anteriores),
                       "log_unid_u": np.log(ativos[u]), "log_unid_v": np.log(ativos[v]),
                       "petrobras": int("Petrobras" in (u, v))})
    anteriores |= juntos
pares = pd.DataFrame(linhas)
pares["par"] = pares.u + "|" + pares.v
pares.to_csv(PROC / "persistencia_pares.csv", index=False)

print(f"{ev.ano_leilao.nunique()} anos com leilao no mar, {pares.par.nunique()} pares distintos, "
      f"{len(pares)} observacoes par-ano\n")
print("Taxa de arremate conjunto conforme o historico do par:")
d = pares.groupby("ja_juntos").juntos.agg(["mean", "sum", "size"])
d.index = ["sem parceria anterior", "com parceria anterior"]
print(d.round(3), "\n")
print("Idem, sem os pares com a Petrobras:")
d2 = pares[pares.petrobras == 0].groupby("ja_juntos").juntos.agg(["mean", "sum", "size"])
d2.index = ["sem parceria anterior", "com parceria anterior"]
print(d2.round(3), "\n")

# ---------------------------------------------------------------- modelos
amostra = pares[pares.ano.isin(pares[pares.ja_juntos == 1].ano.unique())]  # anos com pares de historico
specs = {
    "todos": (amostra, "juntos ~ ja_juntos + log_unid_u + log_unid_v + petrobras + C(ano)"),
    "sem_petrobras": (amostra[amostra.petrobras == 0], "juntos ~ ja_juntos + log_unid_u + log_unid_v + C(ano)"),
    "interacao": (amostra, "juntos ~ ja_juntos * petrobras + log_unid_u + log_unid_v + C(ano)"),
}
saida = []
for nome, (d, f) in specs.items():
    r = smf.logit(f, data=d).fit(disp=0, cov_type="cluster", cov_kwds={"groups": pd.factorize(d.par)[0]})
    me = r.get_margeff(at="overall").summary_frame()
    me = me[~me.index.str.startswith("C(ano)")]
    print(f"[{nome}] efeitos marginais medios na probabilidade de arrematar junto "
          f"(n={int(r.nobs)}, pares={d.par.nunique()})")
    print(me.iloc[:, [0, 1, 3]].round(4).to_string())
    print(f"   razao de chances de ja_juntos: {np.exp(r.params['ja_juntos']):.1f}\n")
    saida.append(me.assign(modelo=nome, n=int(r.nobs)))
pd.concat(saida).to_csv(PROC / "persistencia_modelo.csv")
