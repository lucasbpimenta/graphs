"""Harmonizacao de nomes de empresas: nome bruto -> empresa canonica -> grupo economico.

Regras ordenadas (a primeira que casar vence). `revisar=True` marca mapeamentos que
dependem de informacao societaria ainda nao confirmada (ver item E do prompt de busca).
Empresas que nao casam com nenhuma regra ficam com o proprio nome limpo e `regra='auto'`.
"""
import re
import unicodedata

# (regex sobre a chave normalizada, empresa canonica, revisar)
REGRAS = [
    (r"petrobras|petroleo brasileiro", "Petrobras", False),
    (r"nova petroleo", "Nova Petróleo", False),
    (r"petrosynergy", "Petrosynergy", False),
    (r"petro ?reconcavo", "PetroRecôncavo", False),
    (r"reconcavo e&p", "PetroRecôncavo", True),
    (r"\besso\b|exxon", "ExxonMobil", False),
    (r"\bshell\b", "Shell", False),
    (r"^bg\b|british gas", "BG", False),
    (r"statoil|equinor", "Equinor", False),
    (r"\bhydro\b", "Hydro", False),
    (r"totalenergies|totalfinaelf|\btotal\b|\belf\b", "TotalEnergies", False),
    (r"maersk", "Maersk Oil", False),
    (r"chevron|texaco", "Chevron", False),
    (r"british[- ]borneo", "British-Borneo", False),
    (r"^bp\b|bp energy|bp brasil", "BP", False),
    (r"repsol sinopec|repsol ypf", "Repsol Sinopec", False),
    (r"repsol", "Repsol", False),
    (r"sinochem", "Sinochem", False),
    (r"sinopec", "Sinopec", False),
    (r"petrogal|galp", "Galp", False),
    (r"cnodc|cnpc|petrochina", "CNPC", False),
    (r"cnooc", "CNOOC", False),
    (r"\bqpi\b|qatar", "QatarEnergy", False),
    (r"petronas", "Petronas", False),
    (r"ecopetrol", "Ecopetrol", False),
    (r"ongc", "ONGC", False),
    (r"brava energia", "Brava Energia", False),
    (r"^3r\b", "3R Petroleum", False),
    (r"enauta|queiroz galvao|\bqgep\b", "Enauta", False),
    (r"petro rio int", "Petro Rio Internacional (2007)", True),  # nao confundir com a PRIO (ex-HRT)
    (r"petro ?rio|^prio\b|^hrt\b", "PRIO", False),
    (r"brasoil", "Brasoil", True),
    (r"seacrest|karavan", "Seacrest", False),
    (r"origem", "Origem Energia", False),
    (r"ogx maranhao|parnaiba gas natural", "Eneva", True),
    (r"eneva", "Eneva", False),
    (r"ogx|dommo", "OGX/Dommo", False),
    (r"imetame", "Imetame", False),
    (r"orteng", "Orteng", False),
    (r"^sipet", "Sipet", False),
    (r"cemig|companhia energetica de minas", "CEMIG", False),
    (r"codemig|desenvolvimento (economico )?de minas", "Codemig", False),
    (r"karoon", "Karoon", False),
    (r"geopark", "GeoPark", False),
    (r"alvopetro", "Alvopetro", False),
    (r"petro[- ]victory", "Petro-Victory", False),
    (r"elysian", "Elysian Petroleum", False),
    (r"phoenix", "Phoenix Óleo & Gás", False),
    (r"mandacaru", "Mandacaru Energia", False),
    (r"cowan", "Cowan", True),  # Construtora Cowan x Cowan Petroleo e Gas
    (r"petra energia", "Petra Energia", False),
    (r"gdf suez|engie", "Engie", False),
    (r"kerr[- ]?mc ?gee", "Kerr-McGee", False),
    (r"anadarko", "Anadarko", False),
    (r"ocean energy|^ocean$", "Ocean Energy", False),
    (r"unocal", "Unocal", False),
    (r"santa fe", "Santa Fe Snyder", False),
    (r"enterprise", "Enterprise Oil", False),
    (r"newfield", "Newfield", False),
    (r"^sk\b", "SK", False),
    (r"devon", "Devon", False),
    (r"hess", "Hess", False),
    (r"agip|\beni\b", "Eni", False),
    (r"coastal", "Coastal", False),
    (r"el ?pass?o", "El Paso", False),
    (r"encana|encanbrasil|enca brasil|pan ?canadian", "Encana", False),
    (r"\bibv\b", "IBV Brasil", False),
    (r"vale do rio doce|\bcvrd\b", "Vale", False),
    (r"odebrech", "Odebrecht", False),
    (r"inpex", "Inpex", False),
    (r"mitsui", "Mitsui", False),
    (r"jx nippon", "JX Nippon", False),
    (r"pttep", "PTTEP", False),
    (r"sonangol", "Sonangol", False),
    (r"nexen", "Nexen", False),
    (r"partex", "Partex", False),
    (r"perenco", "Perenco", False),
    (r"panoro", "Panoro Energy", False),
    (r"barra energia", "Barra Energia", False),
    (r"^bw\b", "BW Energy", False),
    (r"norse", "Norse Energy", False),
    (r"murphy", "Murphy", False),
    (r"wintershall", "Wintershall", False),
    (r"neptune", "Neptune Energy", False),
    (r"premier oil", "Premier Oil", False),
    (r"cepsa", "Cepsa", False),
    (r"bhp", "BHP", False),
    (r"canacol", "Canacol", False),
    (r"gran tierra", "Gran Tierra", False),
    (r"trident", "Trident Energy", False),
    (r"woodside", "Woodside", False),
    (r"rosneft", "Rosneft", False),
    (r"phillips", "ConocoPhillips", False),
    (r"brazalta", "Brazalta", False),
    (r"silver marli[nm]", "Silver Marlin", False),
    (r"nord oil", "Nord Oil and Gas", False),
    (r"vipetro", "Vipetro", False),
    (r"^bgm\b", "BGM", False),
    (r"^delp\b", "Delp", False),
    (r"^carmo\b", "Carmo Energy", False),
    (r"^petroil\b", "Petroil", False),
    (r"great oil", "Great Oil", False),
    (r"pacific brasil", "Pacific Brasil", False),
    (r"geopar", "Geopar - Geosol", False),
    (r"bertek", "Bertek", False),
    # grafia do leilao difere da carteira/cessoes (verificado em 16/10/2026)
    # TOG Brasil = nome fantasia de Trayectoria Petroleo & Gas do Brasil Ltda (mesmo CNPJ 18.709.581/0001-09)
    (r"trayectoria|^tog brasil", "TOG Brasil", False),
    # Norteoleum (CNPJ 12.456.210/0001-78) e recuperanda do Grupo UTC (RJ 2017); mesmo grupo
    # confirmado, mesma PJ provavel mas nao comprovada (o "Cedente" das cessoes da ANP diz UTC)
    (r"norteoleum", "UTC", True),
    # Tarmar = Magellan Energia e Participacoes Ltda (razao social atual, CNPJ 40.194.755/0001-99)
    (r"tarmar|magellan energia", "Tarmar", False),
    # Reconcavo Energia Ltda (CNPJ 23.923.453/0001-95): afiliada da Tarmar, indicada para assinar
    # REC-T-152 e REC-T-180 da 13a Rodada (2016), sem cessao; grupo em GRUPOS.
    # Nao confundir com Reconcavo E&P S.A.
    (r"reconcavo energia", "Recôncavo Energia", False),
    # mesmo nome-base, mas entidades possivelmente distintas -> confirmar
    (r"w ?washington", "W. Washington", True),
    (r"ouro preto", "Ouro Preto", True),
    (r"^utc\b", "UTC", True),
    (r"^great (energy|108|42)\b", "Great Energy", True),
    (r"aurizonia", "Aurizônia", True),
    (r"rio ventura", "3R Petroleum", True),
]

# Fusoes/aquisicoes entre empresas distintas: empresa -> (grupo adquirente, ano de efeito).
# Antes do ano, a empresa conta como grupo proprio; a partir dele, como o adquirente.
EVENTOS = {
    "BG": ("Shell", 2016),
    "Maersk Oil": ("TotalEnergies", 2018),
    "Hydro": ("Equinor", 2007),
    "Kerr-McGee": ("Anadarko", 2006),
    "Ocean Energy": ("Devon", 2003),
    "Coastal": ("El Paso", 2001),
    "3R Petroleum": ("Brava Energia", 2024),
    "Enauta": ("Brava Energia", 2024),
    "YPF": ("Repsol", 2000),  # OPA da Repsol concluida em jun/1999, depois da 1a Rodada
    "Santa Fe Snyder": ("Devon", 2000),
    "British-Borneo": ("Eni", 2000),
    "Enterprise Oil": ("Shell", 2002),
    "Unocal": ("Chevron", 2005),
    "Anadarko": ("Occidental", 2019),
}

# Grupos economicos estaticos (mesmo controlador durante todo o periodo).
GRUPOS = {
    "Repsol Sinopec": "Repsol",  # JV Repsol 60% / Sinopec 40% desde 2010 -- revisar
    "CEMIG": "Governo de Minas Gerais",
    "Codemig": "Governo de Minas Gerais",
    "Recôncavo Energia": "Tarmar",  # Tarmar (Magellan) no QSA; afiliada desde 2016
}

SUFIXOS = r"\b(ltda|limitada|ltd|s ?a|s/a|sa|me|inc|eireli|spe)\b"


def limpar(nome):
    """Remove marcadores de operador e pontuacao residual, preservando acentos."""
    s = str(nome).replace("\xa0", " ")
    s = re.sub(r"^\s*\(Operador\)\s*-\s*", "", s)
    s = re.sub(r"^\s*\(\*\)\s*", "", s)
    s = re.sub(r"[\s\-:–]+$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def chave(nome):
    s = unicodedata.normalize("NFKD", limpar(nome)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[.,/()]", " ", s)
    s = re.sub(SUFIXOS, " ", s)
    return re.sub(r"\s+", " ", s).strip()


def canonica(nome):
    """Retorna (empresa, regra, revisar)."""
    k = chave(nome)
    for padrao, empresa, revisar in REGRAS:
        if re.search(padrao, k):
            return empresa, padrao, revisar
    return limpar(nome), "auto", False


def grupo(empresa, ano=None):
    """Grupo economico da empresa no ano dado (sem ano: situacao atual).

    Segue a cadeia de aquisicoes (Kerr-McGee -> Anadarko -> Occidental) ate o ano dado.
    """
    while empresa in EVENTOS:
        adquirente, ano_ev = EVENTOS[empresa]
        if ano is not None and ano < ano_ev:
            break
        empresa = adquirente
    return GRUPOS.get(empresa, empresa)
