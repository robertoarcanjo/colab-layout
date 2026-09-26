"""Monta o layout de fabricação e passa cada etapa pelo DRC.

Edite só as variáveis desta seção:

- ``PASTA_LUCIVALDO``: pasta do circuito que ocupa a origem da main.
  Atualize quando o Lucivaldo renomear a pasta.
- ``CIRCUITOS_SECUNDARIOS``: um item por circuito incluído, na ordem de
  inclusão. Cada item traz o caminho do GDS (a partir da raiz do
  repositório), a célula e as coordenadas em µm.

A partir da raiz do repositório:

    uv run python main/main.py
"""

from __future__ import annotations

import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from shutil import which
from typing import TypedDict

import photonforge as pf

REPO = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
SAIDA = HERE / "saida"
RELATORIOS = HERE / "relatorios"
DECK = HERE / "drc" / "NanoSOI_Silicon_v10.drc"

# Pasta oficial do Lucivaldo. Troque este caminho se a pasta mudar de nome.
PASTA_LUCIVALDO = "circuito-lucivaldo-v2"
GDS_LUCIVALDO = "CircuitoLucivaldoV2.gds"
CELULA_LUCIVALDO = "TOP"

CELULA_MAIN = "main"
DIE_HALF_UM = 4500.0
CAMADA_SI = (1, 0)
CAMADA_JANELA = (6, 0)


class CircuitoSecundario(TypedDict):
    nome: str
    gds: str
    celula: str
    origem_um: tuple[float, float]


# Cada pessoa acrescenta o próprio circuito nesta lista.
CIRCUITOS_SECUNDARIOS: list[CircuitoSecundario] = [
    {
        "nome": "isa-jose-v1",
        "gds": "circuito-isa-jose-v1/saida/passivo.gds",
        "celula": "mzi_o4_passivo",
        "origem_um": (2300.0, -4400.0),
    },
    {
        "nome": "lucas-v1",
        "gds": "circuito-lucas-v1/MZI_50GHZ_2_stages_Lucas.gds",
        "celula": "TOP",
        "origem_um": (-4100, -4400),
    },
    {
        "nome": "mariana-v1",
        "gds": "circuito-mariana-v1/CircuitoMariana_layout_25_09.gds",
        "celula": "TOP",
        # A TOP da Mariana vai de cerca de (-241, -596) a (620, 14) µm.
        # Mesma borda esquerda do Lucas (x=-4100) e 100 µm acima do bloco dele.
        "origem_um": (-3859.069, -3140.687),
    },
]


# Falhas duras já aceitas no circuito que ocupa a origem da main.
HOST_HARD = frozenset({"design_area", "si_width"})
BASELINE_CATS = ("design_area", "si_width", "si_space")
METAL_CLEAR = (
    "tiw_width",
    "tiw_space",
    "au_width",
    "au_space",
    "tiw_au_space",
    "bp_open_width",
    "bp_open_space",
    "bp_not_in_au",
)
AVISOS = frozenset({"pin_layer", "black_box", "window"})

MAIN_GDS = SAIDA / "main.gds"
MAIN_OAS = SAIDA / "main.oas"

_nome_seq = 0


def localizar_klayout() -> Path:
    encontrado = which("klayout_app.exe") or which("klayout.exe")
    if encontrado:
        return Path(encontrado)
    busca = [Path.home() / "KLayout"]
    for env in ("ProgramFiles", "APPDATA", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            busca.append(Path(base) / "KLayout")
    for root in busca:
        if not root.is_dir():
            continue
        hits = (
            list(root.glob("klayout_app.exe"))
            + list(root.glob("*/klayout_app.exe"))
            + list(root.glob("klayout.exe"))
            + list(root.glob("*/klayout.exe"))
        )
        if hits:
            print(f"KLayout {hits[0]}")
            return hits[0]
    raise FileNotFoundError(
        "KLayout não encontrado. Instale o KLayout e deixe klayout_app.exe "
        "no PATH ou em %APPDATA%\\KLayout."
    )


def gds_lucivaldo() -> Path:
    caminho = REPO / PASTA_LUCIVALDO / GDS_LUCIVALDO
    if not caminho.is_file():
        raise FileNotFoundError(
            f"GDS do Lucivaldo ausente: {caminho}. "
            f"Rode: uv run python {PASTA_LUCIVALDO}/compile.py"
        )
    return caminho


def box(comp: pf.Component) -> tuple[float, float, float, float]:
    blo, bhi = comp.bounds()
    return float(blo[0]), float(blo[1]), float(bhi[0]), float(bhi[1])


def walk_components(comp: pf.Component):
    """Percorre a célula e as dependências que o GDS realmente exporta.

    ``Reference.component`` é um proxy reutilizado: o ``id`` muda a cada
    acesso e não serve para caminhar a hierarquia. ``dependencies()``
    devolve as células estáveis.
    """
    vistos: set[int] = set()
    for cell in (comp, *comp.dependencies()):
        if id(cell) in vistos:
            continue
        vistos.add(id(cell))
        yield cell


def cell_names(comp: pf.Component) -> set[str]:
    return {item.name for item in walk_components(comp)}


def assert_no_layer6(comp: pf.Component) -> None:
    used: set[tuple[int, int]] = set()
    for cell in walk_components(comp):
        used.update(cell.structures.keys())
    if CAMADA_JANELA in used:
        raise RuntimeError("camada 6/0 presente — exige aprovação ANT")


def carregar_celula(gds: Path, celula: str) -> pf.Component:
    if not gds.is_file():
        raise FileNotFoundError(f"GDS ausente: {gds}")
    cells = pf.load_layout(str(gds))
    if celula not in cells:
        raise KeyError(
            f"célula {celula} ausente em {gds.name}. Células: {sorted(cells)}"
        )
    return cells[celula]


def _nome_unico(prefixo: str) -> str:
    global _nome_seq
    _nome_seq += 1
    return f"{prefixo}_{_nome_seq}"


def _only_layer(src: pf.Component, layer: tuple[int, int], name: str) -> pf.Component:
    flat = src.copy()
    flat.flatten()
    out = pf.Component(_nome_unico(name))
    for geom in flat.structures.get(layer, ()):
        out.add(layer, geom)
    return out


def silicon_overlap(
    atual: pf.Component,
    bloco: pf.Component,
    origem: tuple[float, float],
) -> int:
    host_si = _only_layer(atual, CAMADA_SI, "host_si")
    bloco_si = _only_layer(bloco, CAMADA_SI, "bloco_si")
    hit = pf.boolean(
        pf.Reference(host_si),
        pf.Reference(bloco_si, origin=origem),
        "*",
    )
    return len(hit)


def montar(
    host: pf.Component,
    inclusoes: list[tuple[pf.Component, tuple[float, float]]],
) -> pf.Component:
    main = pf.Component(_nome_unico(CELULA_MAIN))
    main.name = CELULA_MAIN
    main.add_reference(host)
    for bloco, origem in inclusoes:
        main.add_reference(bloco).translate(origem)
    return main


def gravar_gds(main: pf.Component) -> None:
    pf.write_layout(str(MAIN_GDS), main, library_name="MAIN")
    print(f"main {MAIN_GDS} ({MAIN_GDS.stat().st_size / 1024:.1f} kB)")


def gravar_oas(main: pf.Component) -> None:
    pf.write_layout(str(MAIN_OAS), main, library_name="MAIN")
    print(f"OAS salvo em {MAIN_OAS} ({MAIN_OAS.stat().st_size / 1024:.1f} kB)")


def sanitizar(rotulo: str) -> str:
    limpo = rotulo.strip()
    if not limpo:
        raise ValueError("nome de circuito vazio")
    return "".join("_" if c in '<>:"/\\|?*' else c for c in limpo)


def ler_secundario(
    item: CircuitoSecundario,
) -> tuple[str, Path, str, tuple[float, float]]:
    nome = sanitizar(str(item["nome"]))
    gds = REPO / item["gds"]
    celula = str(item["celula"])
    origem = item["origem_um"]
    if len(origem) != 2:
        raise ValueError(f"{nome}: origem_um precisa de x e y em µm")
    return nome, gds, celula, (float(origem[0]), float(origem[1]))


def cabe_no_die(bloco: pf.Component, origem: tuple[float, float], nome: str) -> None:
    x0, y0, x1, y1 = box(bloco)
    ox, oy = origem
    xa, ya, xb, yb = x0 + ox, y0 + oy, x1 + ox, y1 + oy
    lim = DIE_HALF_UM
    print(
        f"{nome} em ({ox:.0f}, {oy:.0f}) µm, "
        f"x = {xa:.0f}–{xb:.0f}, y = {ya:.0f}–{yb:.0f}"
    )
    if xa < -lim or ya < -lim or xb > lim or yb > lim:
        raise RuntimeError(
            f"{nome} fora de ±{lim:.0f} µm: "
            f"x = {xa:.0f}–{xb:.0f}, y = {ya:.0f}–{yb:.0f}"
        )


def desambiguar_celulas(bloco: pf.Component, ocupados: set[str], prefixo: str) -> None:
    """Renomeia células do bloco que já existem na main.

    O GDS não aceita duas células com o mesmo nome. O prefixo usa o nome
    do circuito, com hífen trocado por sublinhado.
    """
    tag = prefixo.replace("-", "_")
    celulas = list(walk_components(bloco))
    reservados = set(ocupados) | {cell.name for cell in celulas}
    for cell in celulas:
        if cell.name not in ocupados:
            continue
        base = f"{tag}__{cell.name}"
        novo = base
        n = 2
        while novo in reservados:
            novo = f"{base}_{n}"
            n += 1
        print(f"célula {cell.name} de {prefixo} renomeada para {novo}")
        cell.name = novo
        reservados.add(novo)


def conferir_inclusao(
    atual: pf.Component,
    bloco: pf.Component,
    origem: tuple[float, float],
    nome: str,
) -> None:
    assert_no_layer6(bloco)
    cabe_no_die(bloco, origem, nome)
    desambiguar_celulas(bloco, cell_names(atual), nome)
    clash = cell_names(atual) & cell_names(bloco)
    if clash:
        raise RuntimeError(
            f"nomes de célula repetidos entre a main e {nome}: {sorted(clash)}"
        )
    n_hit = silicon_overlap(atual, bloco, origem)
    print(f"interseção de silício (1/0) com {nome} = {n_hit}")
    if n_hit:
        raise RuntimeError(
            f"silício de {nome} intercepta o que já está na main: {n_hit} polígonos"
        )


def parse_lyrdb(path: Path) -> tuple[dict[str, int], dict[str, str]]:
    root = ET.parse(path).getroot()
    descricoes: dict[str, str] = {}
    for cat in root.findall("./categories/category"):
        nome = cat.findtext("name")
        if nome:
            descricoes[nome] = cat.findtext("description") or ""
    counts: dict[str, int] = {}
    for item in root.findall("./items/item"):
        nome = item.findtext("category")
        if nome:
            counts[nome] = counts.get(nome, 0) + 1
    return counts, descricoes


def executar_drc(klayout: Path, gds: Path, lyrdb: Path) -> tuple[dict[str, int], dict[str, str]]:
    if lyrdb.exists():
        lyrdb.unlink()
    cmd = [
        str(klayout),
        "-b",
        "-nc",
        "-r",
        str(DECK),
        "-rd",
        f"gdsfile={gds.as_posix()}",
        "-rd",
        f"resultsfile={lyrdb.as_posix()}",
    ]
    print("DRC", gds.name, "->", lyrdb.name)
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"KLayout DRC saiu com código {proc.returncode}")
    if not lyrdb.is_file():
        raise FileNotFoundError(f"relatório DRC ausente: {lyrdb}")
    return parse_lyrdb(lyrdb)


def falhas_duras(counts: dict[str, int], descricoes: dict[str, str]) -> dict[str, int]:
    duras: dict[str, int] = {}
    for cat, n in counts.items():
        if n <= 0:
            continue
        texto = descricoes.get(cat, "")
        if cat in AVISOS or texto.startswith("Warning:"):
            continue
        duras[cat] = n
    return duras


def relatar(
    titulo: str,
    counts: dict[str, int],
    descricoes: dict[str, str],
    path: Path,
    baseline: dict[str, int] | None,
) -> dict[str, int]:
    total = sum(counts.values())
    print(f"DRC {titulo}: {total} marcadores")
    for cat in sorted(counts):
        if counts[cat]:
            print(f"  {cat} = {counts[cat]}")
    extra = {
        cat: n
        for cat, n in falhas_duras(counts, descricoes).items()
        if cat not in HOST_HARD
    }
    linhas = [titulo, ""]
    for cat in sorted(counts):
        if counts[cat]:
            linhas.append(f"{cat} = {counts[cat]}")
    linhas.append("")
    linhas.append("falha dura fora da origem: " + (str(extra) if extra else "nenhuma"))
    if baseline is None:
        for cat in BASELINE_CATS:
            linhas.append(f"baseline {cat}: {counts.get(cat, 0)}")
    else:
        for cat, expected in baseline.items():
            linhas.append(
                f"baseline {cat}: medido {counts.get(cat, 0)}, origem {expected}"
            )
    metal = {cat: counts.get(cat, 0) for cat in METAL_CLEAR if counts.get(cat, 0)}
    linhas.append("metal: " + (str(metal) if metal else "sem erro"))
    path.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(path)
    if extra:
        raise RuntimeError(f"DRC {titulo}: {extra}")
    if metal:
        raise RuntimeError(f"DRC {titulo}: metal {metal}")
    if baseline is not None:
        for cat, expected in baseline.items():
            got = counts.get(cat, 0)
            if got != expected:
                raise RuntimeError(
                    f"DRC {titulo}: {cat} = {got}, a main do Lucivaldo tinha {expected}"
                )
    return {cat: counts.get(cat, 0) for cat in BASELINE_CATS}


def limpar_relatorios() -> None:
    RELATORIOS.mkdir(parents=True, exist_ok=True)
    for antigo in RELATORIOS.iterdir():
        if antigo.suffix in {".txt", ".lyrdb"}:
            antigo.unlink()


def rodar_drc(
    klayout: Path,
    titulo: str,
    rotulo: str,
    indice: int,
    baseline: dict[str, int] | None,
) -> dict[str, int]:
    base = f"{indice:02d}_DRC_{sanitizar(rotulo)}"
    txt = RELATORIOS / f"{base}.txt"
    lyrdb = RELATORIOS / f"{base}.lyrdb"
    counts, descricoes = executar_drc(klayout, MAIN_GDS, lyrdb)
    return relatar(titulo, counts, descricoes, txt, baseline)


def main() -> None:
    if not DECK.is_file():
        raise FileNotFoundError(f"deck DRC ausente: {DECK}")
    SAIDA.mkdir(parents=True, exist_ok=True)
    limpar_relatorios()
    klayout = localizar_klayout()

    host = carregar_celula(gds_lucivaldo(), CELULA_LUCIVALDO)
    assert_no_layer6(host)

    inclusoes: list[tuple[pf.Component, tuple[float, float]]] = []
    secundarios: list[tuple[str, pf.Component, tuple[float, float]]] = []
    for item in CIRCUITOS_SECUNDARIOS:
        nome, gds, celula, origem = ler_secundario(item)
        bloco = carregar_celula(gds, celula)
        secundarios.append((nome, bloco, origem))

    indice = 0
    main_comp = montar(host, inclusoes)
    assert_no_layer6(main_comp)
    gravar_gds(main_comp)
    baseline = rodar_drc(
        klayout,
        "main Lucivaldo",
        PASTA_LUCIVALDO,
        indice,
        None,
    )
    indice += 1

    for nome, bloco, origem in secundarios:
        atual = montar(host, inclusoes)
        conferir_inclusao(atual, bloco, origem, nome)
        inclusoes.append((bloco, origem))
        main_comp = montar(host, inclusoes)
        assert_no_layer6(main_comp)
        gravar_gds(main_comp)
        rodar_drc(klayout, f"main com {nome}", nome, indice, baseline)
        indice += 1

    main_comp = montar(host, inclusoes)
    assert_no_layer6(main_comp)
    gravar_gds(main_comp)
    rodar_drc(klayout, "main final", "main", indice, baseline)
    gravar_oas(main_comp)


if __name__ == "__main__":
    main()
