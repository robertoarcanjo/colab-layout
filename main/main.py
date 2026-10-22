"""Monta o layout de fabricação e passa cada etapa pelo DRC.

Edite só as variáveis desta seção:

- ``PASTA_LUCIVALDO``: pasta do circuito que ocupa a origem da main.
  Atualize quando o Lucivaldo renomear a pasta.
- ``CIRCUITOS_SECUNDARIOS``: um item por circuito incluído, na ordem de
  inclusão. Cada item traz o caminho do GDS (a partir da raiz do
  repositório), a célula e as coordenadas em µm.
- ``CICLO_NORMAL``: ``True`` executa o processo padrão, com DRC a cada
  inclusão. ``False`` inclui todos os circuitos de uma vez, sem DRC
  intermediário.
- ``DRC_FINAL``: com ``CICLO_NORMAL = False``, ``True`` roda um único
  DRC no layout completo, depois que todos os circuitos entraram.

A partir da raiz do repositório:

    uv run python main/main.py
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from shutil import which
from typing import TypedDict

import gdsfactory as gf
import klayout.lay as lay

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

# True: processo padrão, com DRC a cada inclusão.
# False: todos os circuitos entram de uma vez, sem DRC intermediário.
CICLO_NORMAL = False
# Vale com CICLO_NORMAL = False. True roda um único DRC no layout completo.
DRC_FINAL = False


class CircuitoSecundario(TypedDict):
    nome: str
    gds: str
    celula: str
    origem_um: tuple[float, float]


class OrigemDrc(TypedDict):
    contagens: dict[str, int]
    design_area_um2: float


"""{
        "nome": "isa-jose-v1",
        "gds": "circuito-isa-jose-v1/mzi_O4_2estagios_gc_array.gds",
        "celula": "MZI_O4_GC7",
        # A célula vai de cerca de (-127, -744) a (1215, 743) µm.
        # Os dois blocos ficam lado a lado, com a base em y=-4400,
        # centrados na faixa x=2300–3800 que o passivo ocupava.
        "origem_um": (1140.0, -3260.0),
    },
    {
        "nome": "isa-jose-v1-pdk",
        "gds": "circuito-isa-jose-v1/mzi_O4_2estagios_gc_array_pdk.gds",
        "celula": "MZI_O4_GC7_PDK",
        # 100 µm à direita do bloco anterior. A célula vai de cerca de
        # (-127, -744) a (1224, 743) µm.
        "origem_um": (2800.0, -3450.0),
    },
    {
        "nome": "isa-jose-v1-rota",
        "gds": "circuito-isa-jose-v1/rota_eletrica.gds",
        "celula": "rota_eletrica",
        # Coordenadas absolutas da main. O GDS sai de roteamento_eletrico.py.
        "origem_um": (0.0, 0.0),
    },
"""
# Cada pessoa acrescenta o próprio circuito nesta lista.
CIRCUITOS_SECUNDARIOS: list[CircuitoSecundario] = [
    {
        "nome": "isa-jose-v1",
        "gds": "circuito-isa-jose-v1/circuito_isa_jose.gds",
        "celula": "circuito_isa_jose",
        "origem_um": (0,0),
    },
    {
        "nome": "lucas_d10-v2",
        "gds": "circuitos-lucas-v2/MZI_50GHZ_2_stages_d10_Lucas.gds",
        "celula": "TOP",
        "origem_um": (-4000, -4400),
    },
    {
        "nome": "mariana_d5-v2",
        "gds": "circuito-mariana-v2/CircuitoMariana.gds",
        "celula": "TOP",
        # Aviso de Lucas: Nunca mecha na posição y do de Mariana, o x pode ser modificado a vontade
        "origem_um": (-2400, -3400),
    },
    {
        "nome": "eletrico-lucas-mariana",
        "gds": "circuitos-lucas-v2/circuito-eletrico-lucas-mariana.gds",
        "celula": "TOP",
        # Coordenadas absolutas da main. A célula TOP já cobre cerca de
        # x = -4398 a -1780 µm e y = -4253 a -2448 µm, sobre Lucas d10 e Mariana.
        "origem_um": (0.0, 0.0),
    },
    {
        "nome": "italo-v1",
        "gds": "circuito-italo-v1/Nanotools_Italo_SWG.gds",
        "celula": "TOP",
        # Célula TOP de cerca de (-889, -138) a (733, 142) µm.
        "origem_um": (2390, -1690.00000 + 9*400),
    },
    {
        "nome": "italo-v1",
        "gds": "circuito-italo-v1/Nanotools_Italo_SWG.gds",
        "celula": "TOP",
        # Célula TOP de cerca de (-889, -138) a (733, 142) µm.
        "origem_um": (2390, -1690.00000 + 8*400),
    },
    {
        "nome": "italo-v1",
        "gds": "circuito-italo-v1/Nanotools_Italo_SWG.gds",
        "celula": "TOP",
        # Célula TOP de cerca de (-889, -138) a (733, 142) µm.
        "origem_um": (2390, -1690.00000 + 7*400),
    },
    {
        "nome": "italo-v1",
        "gds": "circuito-italo-v1/Nanotools_Italo_SWG.gds",
        "celula": "TOP",
        # Célula TOP de cerca de (-889, -138) a (733, 142) µm.
        "origem_um": (2390, -1690.00000 + 6*400),
    },
    {
        "nome": "italo-v1",
        "gds": "circuito-italo-v1/Nanotools_Italo_SWG.gds",
        "celula": "TOP",
        # Célula TOP de cerca de (-889, -138) a (733, 142) µm.
        "origem_um": (2390, -1690.00000 + 5*400),
    },
    {
        "nome": "italo-v1",
        "gds": "circuito-italo-v1/Nanotools_Italo_SWG.gds",
        "celula": "TOP",
        # Célula TOP de cerca de (-889, -138) a (733, 142) µm.
        "origem_um": (2390, -1690.00000 + 4*400),
    },
    {
        "nome": "italo-v1",
        "gds": "circuito-italo-v1/Nanotools_Italo_SWG.gds",
        "celula": "TOP",
        # Célula TOP de cerca de (-889, -138) a (733, 142) µm.
        "origem_um": (2540, -1690.00000 + 3*400),
    },
    {
        "nome": "italo-v1",
        "gds": "circuito-italo-v1/Nanotools_Italo_SWG.gds",
        "celula": "TOP",
        # Célula TOP de cerca de (-889, -138) a (733, 142) µm.
        "origem_um": (2540, -1690.00000 + 2*400),
    },
    {
        "nome": "italo-v1",
        "gds": "circuito-italo-v1/Nanotools_Italo_SWG.gds",
        "celula": "TOP",
        # Célula TOP de cerca de (-889, -138) a (733, 142) µm.
        "origem_um": (2540, -1690.00000 + 400),
    },
    {
        "nome": "italo-v1",
        "gds": "circuito-italo-v1/Nanotools_Italo_SWG.gds",
        "celula": "TOP",
        # Célula TOP de cerca de (-889, -138) a (733, 142) µm.
        "origem_um": (2540, -1690.00000),
    },
    {
        "nome": "lucas_d5-v2",
        "gds": "circuitos-lucas-v2/MZI_50GHZ_2_stages_d5_Lucas.gds",
        "celula": "TOP",
        "origem_um": (-4100, 2850),
    },
    {
        "nome": "mariana_d10-v2",
        "gds": "circuito-mariana-v2/CircuitoMariana10um.gds",
        "celula": "TOP",
        "origem_um": (-2400, 4200),
    },
    {
        "nome": "eletrico-lucas-mariana-2",
        "gds": "circuitos-lucas-v2/circuito-eletrico-lucas-mariana-2.gds",
        "celula": "TOP",
        "origem_um": (0.0, 0.0),
    },
    {
        "nome": "isa-jose-hyb",
        "gds": "circuito-isa-jose-v1/hybrid90_ydc_gc_pack.gds",
        "celula": "TOP",
        "origem_um": (-3158, 2200),
    },
    {
        "nome": "tag",
        "gds": "tag-layout/textos_no_quadrado.gds",
        "celula": "textos_no_quadrado",
        "origem_um": (-0, 0),
    },
]

# -1690.00000

# Falhas duras já aceitas no circuito que ocupa a origem da main.
HOST_HARD = frozenset({"design_area", "si_width"})
BASELINE_CATS = ("design_area", "si_width", "si_space")
# O .lyrdb grava coordenadas em µm. A união usa a mesma grade do GDS.
_DBU_RELATORIO = 0.001
# Abaixo disto, a diferença de área é ruído de grade, não metal novo.
_TOLERANCIA_DESIGN_UM2 = 1.0
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

FIGS = REPO / "figs"
MAIN_GDS = SAIDA / "main.gds"
MAIN_OAS = SAIDA / "main.oas"
MAIN_PNG = FIGS / "main.png"
PNG_PX = 4000

# Pinos, DEVREC, black box e o retângulo do die não entram na figura.
CAMADAS_FIGURA_OCULTAS = frozenset({(1, 10), (68, 0), (81, 0), (290, 0), (998, 0)})
# Tons da legenda do PDK NanoSOI. O swatch do silício é muito claro para
# a figura inteira, então o matiz fica e a cor desce. Formato 0xAARRGGBB.
COR_FIGURA = {
    (1, 0): 0xff0033,  # Silicon Full Etch
    (10, 0): 0xff0033,
    (31, 0): 0xff0033,
    (33, 0): 0xff0033,
    (11, 0): 0x0033ff,  # TiW Heater
    (12, 0): 0xcc9900,  # TiW/Au Routing Bilayer
    (13, 0): 0x663300,  # Bond Pad Open
    (200, 0): 0xFFFF0000,  # SEM Imaging
    (201, 0): 0x006633,  # Deep Trench
    (202, 0): 0x006633,  # Deep Trench Handling Exclusion
    (203, 0): 0x006633,  # Thermal Isolation Trenches
    (1, 99): 0xFFF43471,
}

_nome_seq = 0


def localizar_klayout() -> Path:
    encontrado = which("klayout_app.exe") or which("klayout.exe")
    if encontrado:
        return Path(encontrado)
    busca = [Path.home() / "KLayout"]
    for env in ("ProgramFiles", "ProgramFiles(x86)", "APPDATA", "LOCALAPPDATA"):
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
        "no PATH, em Program Files, em Program Files (x86) ou em %APPDATA%\\KLayout."
    )


def gds_lucivaldo() -> Path:
    caminho = REPO / PASTA_LUCIVALDO / GDS_LUCIVALDO
    if not caminho.is_file():
        raise FileNotFoundError(
            f"GDS do Lucivaldo ausente: {caminho}. "
            f"Rode: uv run python {PASTA_LUCIVALDO}/compile.py"
        )
    return caminho


def box(comp: gf.kf.KCell) -> tuple[float, float, float, float]:
    caixa = comp.dbbox()
    return float(caixa.left), float(caixa.bottom), float(caixa.right), float(caixa.top)


def walk_cells(comp: gf.kf.KCell):
    """Percorre a célula e as dependências que o GDS exporta."""
    layout = comp.kcl.layout
    vistos: set[int] = set()
    for indice in (comp.cell_index(), *comp.called_cells()):
        if indice in vistos:
            continue
        vistos.add(indice)
        cell = layout.cell(indice)
        if cell is not None:
            yield cell


def cell_names(comp: gf.kf.KCell) -> set[str]:
    return {cell.name for cell in walk_cells(comp)}


def camadas_usadas(comp: gf.kf.KCell) -> set[tuple[int, int]]:
    layout = comp.kcl.layout
    usadas: set[tuple[int, int]] = set()
    for cell in walk_cells(comp):
        for indice in layout.layer_indexes():
            if cell.shapes(indice).size():
                info = layout.get_info(indice)
                usadas.add((info.layer, info.datatype))
    return usadas


def assert_no_layer6(comp: gf.kf.KCell) -> None:
    if CAMADA_JANELA in camadas_usadas(comp):
        raise RuntimeError("camada 6/0 presente — exige aprovação ANT")


def _descartar_meta_kfactory(layout: gf.kdb.Layout) -> None:
    """Tira do GDS os nomes de enclosure que o kfactory não consegue reler.

    O mesmo perfil pode ser gravado duas vezes, por exemplo ``028523d7`` e
    ``78687732``. A geometria permanece; só a tabela de metadados sai.
    """

    def limpar(dono: gf.kdb.Layout | gf.kdb.Cell) -> None:
        for meta in list(dono.each_meta_info()):
            if meta.name.startswith("kfactory:"):
                dono.remove_meta_info(meta.name)

    limpar(layout)
    for cell in layout.each_cell():
        limpar(cell)


def carregar_celula(gds: Path, celula: str) -> gf.kf.KCell:
    if not gds.is_file():
        raise FileNotFoundError(f"GDS ausente: {gds}")
    layout = gf.kdb.Layout()
    opcoes = gf.kf.utilities.load_layout_options()
    opcoes.warn_level = 0
    layout.read(str(gds), opcoes)
    _descartar_meta_kfactory(layout)
    if layout.cell(celula) is None:
        nomes = sorted(cell.name for cell in layout.each_cell())
        raise KeyError(
            f"célula {celula} ausente em {gds.name}. Células: {nomes}"
        )
    kcl = gf.kf.KCLayout(_nome_unico(gds.stem))
    kcl.assign(layout)
    return kcl[celula]


def _nome_unico(prefixo: str) -> str:
    global _nome_seq
    _nome_seq += 1
    return f"{prefixo}_{_nome_seq}"


# O EdgeProcessor do KLayout 0.30.7 às vezes entra em gs.is_reset no
# merge de um bloco grande (o Ítalo tem ~16 mil polígonos de silício).
# A mesma região aceita o merge na chamada seguinte.
_TENTATIVAS_BOOL = 6


def _sem_travar(acao, descricao: str):
    ultimo: RuntimeError | None = None
    for tentativa in range(1, _TENTATIVAS_BOOL + 1):
        try:
            return acao()
        except RuntimeError as exc:
            ultimo = exc
            if "gs.is_reset" not in str(exc) or tentativa == _TENTATIVAS_BOOL:
                raise
            print(
                f"boolean do KLayout travou ({descricao}); "
                f"tentativa {tentativa + 1} de {_TENTATIVAS_BOOL}"
            )
    raise ultimo


def _regiao(comp: gf.kf.KCell, camada: tuple[int, int]) -> gf.kdb.Region:
    layout = comp.kcl.layout
    indice = layout.layer(camada[0], camada[1])
    return gf.kdb.Region(comp.kdb_cell.begin_shapes_rec(indice))


def _regiao_na_caixa(
    comp: gf.kf.KCell,
    camada: tuple[int, int],
    caixa: gf.kdb.Box,
) -> gf.kdb.Region:
    """Formas da célula que encostam na caixa, no sistema da própria célula."""
    layout = comp.kcl.layout
    indice = layout.layer(camada[0], camada[1])
    formas = comp.kdb_cell.begin_shapes_rec(indice)
    formas.region = caixa
    formas.overlapping = True
    return gf.kdb.Region(formas)


def silicon_overlap(
    atual: gf.kf.KCell,
    bloco: gf.kf.KCell,
    origem: tuple[float, float],
) -> int:
    dbu_bloco = bloco.kcl.layout.dbu
    dbu = atual.kcl.layout.dbu
    if dbu_bloco != dbu:
        raise RuntimeError(
            f"unidade do GDS diferente da main: {bloco.name} "
            f"dbu={dbu_bloco}, main dbu={dbu}"
        )
    dx = int(round(origem[0] / dbu))
    dy = int(round(origem[1] / dbu))
    bloco_si = _regiao(bloco, CAMADA_SI)
    bloco_si.transform(gf.kdb.Trans(dx, dy))
    caixa = bloco_si.bbox()
    if caixa.empty():
        return 0
    # A interseção só pode cair dentro do bloco. O booleano do chip
    # inteiro faz o KLayout abortar (dbEdgeProcessor gs.is_reset)
    # quando a região da Mariana entra.
    margem = gf.kdb.Box(
        caixa.left - 1,
        caixa.bottom - 1,
        caixa.right + 1,
        caixa.top + 1,
    )
    atual_si = _regiao_na_caixa(atual, CAMADA_SI, margem)
    _sem_travar(bloco_si.merge, f"merge de {bloco.name}")
    _sem_travar(atual_si.merge, "merge da main")
    inter = _sem_travar(lambda: atual_si & bloco_si, f"interseção com {bloco.name}")
    return inter.count()


def _copiar_arvore(destino: gf.kdb.Layout, origem: gf.kf.KCell) -> gf.kdb.Cell:
    ocupados = {cell.name for cell in destino.each_cell()}
    conflito = cell_names(origem) & ocupados
    if conflito:
        raise RuntimeError(
            "nomes de célula repetidos ao montar a main: " + str(sorted(conflito))
        )
    novo = destino.create_cell(origem.name)
    novo.copy_tree(origem.kdb_cell)
    return novo


def _instanciar(
    pai: gf.kdb.Cell,
    filho: gf.kdb.Cell,
    origem: tuple[float, float],
    dbu: float,
) -> None:
    dx = int(round(origem[0] / dbu))
    dy = int(round(origem[1] / dbu))
    pai.insert(gf.kdb.CellInstArray(filho.cell_index(), gf.kdb.Trans(dx, dy)))


def montar(
    host: gf.kf.KCell,
    inclusoes: list[tuple[gf.kf.KCell, tuple[float, float]]],
) -> gf.kf.KCell:
    kcl = gf.kf.KCLayout(_nome_unico(CELULA_MAIN))
    dbu = host.kcl.layout.dbu
    kcl.layout.dbu = dbu
    top = kcl.kcell(CELULA_MAIN)
    _instanciar(top.kdb_cell, _copiar_arvore(kcl.layout, host), (0.0, 0.0), dbu)
    for bloco, origem in inclusoes:
        dbu_bloco = bloco.kcl.layout.dbu
        if dbu_bloco != dbu:
            raise RuntimeError(
                f"unidade do GDS diferente da main: {bloco.name} "
                f"dbu={dbu_bloco}, main dbu={dbu}"
            )
        copiado = _copiar_arvore(kcl.layout, bloco)
        _instanciar(top.kdb_cell, copiado, origem, dbu)
    return top


def _opcoes_gravacao() -> gf.kdb.SaveLayoutOptions:
    return gf.kf.save_layout_options(
        libname="MAIN",
        gds2_libname="MAIN",
        gds2_max_cellname_length=320,
        write_context_info=False,
    )


def _gravar(comp: gf.kf.KCell, caminho: Path) -> None:
    comp.kcl.write(
        caminho,
        options=_opcoes_gravacao(),
        set_meta_data=False,
        deduplicate_cell_names=False,
    )


def gravar_gds(main: gf.kf.KCell) -> None:
    _gravar(main, MAIN_GDS)
    print(f"main {MAIN_GDS} ({MAIN_GDS.stat().st_size / 1024:.1f} kB)")


def gravar_oas(main: gf.kf.KCell) -> None:
    _gravar(main, MAIN_OAS)
    print(f"OAS salvo em {MAIN_OAS} ({MAIN_OAS.stat().st_size / 1024:.1f} kB)")


def _cor_opaca(cor: int) -> int:
    """0xRRGGBB ou 0xAARRGGBB viram preenchimento opaco."""
    return 0xFF000000 | (cor & 0xFFFFFF)


def _estilo_figura(vista: lay.LayoutView) -> None:
    it = vista.begin_layers()
    while not it.at_end():
        no = it.current().dup()
        camada = (no.source_layer, no.source_datatype)
        if camada in CAMADAS_FIGURA_OCULTAS:
            no.visible = False
        else:
            cor = COR_FIGURA.get(camada)
            if cor is not None:
                opaca = _cor_opaca(cor)
                no.fill_color = opaca
                no.frame_color = opaca
                no.dither_pattern = 0
                no.transparent = False
            no.visible = True
        vista.replace_layer_node(it, no)
        it.next()


def gravar_png() -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    vista = lay.LayoutView()
    vista.load_layout(str(MAIN_OAS), False)
    vista.max_hier()
    vista.set_config("background-color", "#ffffff")
    vista.set_config("grid-visible", "false")
    vista.set_config("inst-visible", "false")
    vista.set_config("text-visible", "false")
    # true desenha só o contorno. O preenchimento sólido fica no dither 0.
    vista.set_config("no-stipple", "false")
    _estilo_figura(vista)
    vista.zoom_fit()
    vista.save_image(str(MAIN_PNG), PNG_PX, PNG_PX)
    print(f"PNG salvo em {MAIN_PNG} ({MAIN_PNG.stat().st_size / 1024:.1f} kB)")


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


def cabe_no_die(bloco: gf.kf.KCell, origem: tuple[float, float], nome: str) -> None:
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


def desambiguar_celulas(bloco: gf.kf.KCell, ocupados: set[str], prefixo: str) -> None:
    """Renomeia células do bloco que já existem na main.

    O GDS não aceita duas células com o mesmo nome. O prefixo usa o nome
    do circuito, com hífen trocado por sublinhado.
    """
    tag = prefixo.replace("-", "_")
    celulas = list(walk_cells(bloco))
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
    atual: gf.kf.KCell,
    bloco: gf.kf.KCell,
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


def _fmt_um2(area: float) -> str:
    arred = round(area)
    if abs(area - arred) < 0.05:
        return str(int(arred))
    return f"{area:.1f}"


def _vertices_um(texto: str) -> list[tuple[float, float]]:
    if not texto.startswith("polygon:"):
        return []
    inicio = texto.find("(")
    fim = texto.rfind(")")
    if inicio < 0 or fim <= inicio:
        return []
    pontos: list[tuple[float, float]] = []
    for par in texto[inicio + 1 : fim].split(";"):
        par = par.strip()
        if not par:
            continue
        x_txt, y_txt = par.split(",", 1)
        pontos.append((float(x_txt), float(y_txt)))
    return pontos


def _area_design_area(root: ET.Element) -> float:
    """Área da união dos marcadores design_area, em µm².

    O deck corta o mesmo metal em ladrilhos de 100 µm. A contagem sobe
    quando a caixa do layout muda; a união permanece.
    """
    reg = gf.kdb.Region()
    escala = 1.0 / _DBU_RELATORIO
    for item in root.findall("./items/item"):
        if item.findtext("category") != "design_area":
            continue
        for valor in item.findall("./values/value"):
            pontos = _vertices_um(valor.text or "")
            if len(pontos) < 3:
                continue
            reg.insert(
                gf.kdb.Polygon(
                    [
                        gf.kdb.Point(
                            int(round(x * escala)),
                            int(round(y * escala)),
                        )
                        for x, y in pontos
                    ]
                )
            )
    return float(reg.area()) * _DBU_RELATORIO * _DBU_RELATORIO


def parse_lyrdb(path: Path) -> tuple[dict[str, int], dict[str, str], float]:
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
    return counts, descricoes, _area_design_area(root)


# 3221225477 é 0xC0000005, violação de acesso.
# 3221226356 é 0xC0000374, heap corrompido.
# O DRC do KLayout 0.30.7 derruba o processo no Windows de forma
# intermitente, mesmo com uma thread. A pausa deixa o processo morto
# soltar a memória antes da rodada seguinte.
_TRAVOU = {1, 3221225477, -1073741819, 3221226356, -1073740940}
_TENTATIVAS_DRC = 8
_PAUSA_DRC_S = 2.0


def deck_uma_thread() -> Path:
    texto = DECK.read_text(encoding="utf-8")
    ajustado = texto.replace("threads(2)", "threads(1)", 1)
    pasta = Path(tempfile.mkdtemp(prefix="drc-"))
    destino = pasta / DECK.name
    destino.write_text(ajustado, encoding="utf-8", newline="\n")
    return destino


def _cauda_log(log: Path, n: int = 30) -> str:
    if not log.is_file():
        return ""
    linhas = log.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(linhas[-n:])


def _ler_relatorio(
    lyrdb: Path, log: Path, codigo: int
) -> tuple[dict[str, int], dict[str, str], float] | None:
    """Aceita o .lyrdb se o XML fecha.

    O KLayout às vezes morre depois de gravar o relatório. Código 0, ou um
    travamento com a linha de gravação no log, ainda vale.
    """
    if not lyrdb.is_file():
        return None
    if codigo != 0 and codigo not in _TRAVOU:
        return None
    if codigo != 0 and "Writing report database" not in _cauda_log(log, 80):
        return None
    try:
        return parse_lyrdb(lyrdb)
    except ET.ParseError:
        return None


def executar_drc(
    klayout: Path, gds: Path, lyrdb: Path
) -> tuple[dict[str, int], dict[str, str], float]:
    deck = deck_uma_thread()
    log = deck.with_suffix(".log")
    cmd = [
        str(klayout),
        "-b",
        "-nc",
        "-r",
        str(deck),
        "-rd",
        f"gdsfile={gds.as_posix()}",
        "-rd",
        f"resultsfile={lyrdb.as_posix()}",
    ]
    ultimo = 0
    for tentativa in range(1, _TENTATIVAS_DRC + 1):
        if lyrdb.exists():
            lyrdb.unlink()
        print("DRC", gds.name, "->", lyrdb.name)
        with log.open("w", encoding="utf-8", errors="replace") as saida:
            proc = subprocess.run(cmd, check=False, stdout=saida, stderr=subprocess.STDOUT)
        ultimo = proc.returncode
        lido = _ler_relatorio(lyrdb, log, ultimo)
        if lido is not None:
            if ultimo != 0:
                print(
                    f"KLayout encerrou com código {ultimo} "
                    "depois de gravar o relatório; relatório aceito"
                )
            return lido
        if ultimo not in _TRAVOU or tentativa == _TENTATIVAS_DRC:
            break
        print(
            f"KLayout encerrou com código {ultimo}; "
            f"tentativa {tentativa + 1} de {_TENTATIVAS_DRC}"
        )
        time.sleep(_PAUSA_DRC_S)
    cauda = _cauda_log(log)
    detalhe = f"\n{cauda}" if cauda else ""
    raise RuntimeError(f"KLayout DRC saiu com código {ultimo}{detalhe}")


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
    area_design: float,
    path: Path,
    baseline: OrigemDrc | None,
) -> OrigemDrc:
    total = sum(counts.values())
    print(f"DRC {titulo}: {total} marcadores")
    for cat in sorted(counts):
        if counts[cat]:
            print(f"  {cat} = {counts[cat]}")
    if counts.get("design_area"):
        print(f"  design_area área = {_fmt_um2(area_design)} µm²")
    extra = {
        cat: n
        for cat, n in falhas_duras(counts, descricoes).items()
        if cat not in HOST_HARD
    }
    linhas = [titulo, ""]
    for cat in sorted(counts):
        if counts[cat]:
            linhas.append(f"{cat} = {counts[cat]}")
    if counts.get("design_area"):
        linhas.append(f"design_area área = {_fmt_um2(area_design)} µm²")
    linhas.append("")
    linhas.append("falha dura fora da origem: " + (str(extra) if extra else "nenhuma"))
    origem = {cat: counts.get(cat, 0) for cat in BASELINE_CATS}
    if baseline is None:
        linhas.append(
            f"baseline design_area: {origem['design_area']} marcadores, "
            f"{_fmt_um2(area_design)} µm²"
        )
        for cat in BASELINE_CATS:
            if cat == "design_area":
                continue
            linhas.append(f"baseline {cat}: {origem[cat]}")
    else:
        linhas.append(
            "baseline design_area: "
            f"medido {origem['design_area']} marcadores, {_fmt_um2(area_design)} µm²; "
            f"origem {baseline['contagens'].get('design_area', 0)} marcadores, "
            f"{_fmt_um2(baseline['design_area_um2'])} µm²"
        )
        for cat in BASELINE_CATS:
            if cat == "design_area":
                continue
            linhas.append(
                f"baseline {cat}: medido {origem[cat]}, "
                f"origem {baseline['contagens'].get(cat, 0)}"
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
        if abs(area_design - baseline["design_area_um2"]) > _TOLERANCIA_DESIGN_UM2:
            raise RuntimeError(
                f"DRC {titulo}: design_area = {_fmt_um2(area_design)} µm², "
                f"a main do Lucivaldo tinha {_fmt_um2(baseline['design_area_um2'])} µm²"
            )
        for cat in BASELINE_CATS:
            if cat == "design_area":
                continue
            got = origem[cat]
            expected = baseline["contagens"].get(cat, 0)
            if got != expected:
                raise RuntimeError(
                    f"DRC {titulo}: {cat} = {got}, a main do Lucivaldo tinha {expected}"
                )
        n_med = origem["design_area"]
        n_ori = baseline["contagens"].get("design_area", 0)
        if n_med != n_ori:
            print(
                f"  design_area segue: {n_med} marcadores, "
                f"área {_fmt_um2(area_design)} µm² "
                f"(origem {n_ori} marcadores, mesma área)"
            )
    return {"contagens": origem, "design_area_um2": area_design}


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
    baseline: OrigemDrc | None,
) -> OrigemDrc:
    base = f"{indice:02d}_DRC_{sanitizar(rotulo)}"
    txt = RELATORIOS / f"{base}.txt"
    lyrdb = RELATORIOS / f"{base}.lyrdb"
    counts, descricoes, area_design = executar_drc(klayout, MAIN_GDS, lyrdb)
    return relatar(titulo, counts, descricoes, area_design, txt, baseline)


def _carregar_secundarios() -> list[tuple[str, gf.kf.KCell, tuple[float, float]]]:
    secundarios: list[tuple[str, gf.kf.KCell, tuple[float, float]]] = []
    for item in CIRCUITOS_SECUNDARIOS:
        nome, gds, celula, origem = ler_secundario(item)
        bloco = carregar_celula(gds, celula)
        secundarios.append((nome, bloco, origem))
    return secundarios


def _ciclo_normal(
    host: gf.kf.KCell,
    secundarios: list[tuple[str, gf.kf.KCell, tuple[float, float]]],
) -> gf.kf.KCell:
    if not DECK.is_file():
        raise FileNotFoundError(f"deck DRC ausente: {DECK}")
    limpar_relatorios()
    klayout = localizar_klayout()

    inclusoes: list[tuple[gf.kf.KCell, tuple[float, float]]] = []
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
    return main_comp


def _drc_final() -> None:
    """Um DRC no GDS completo, sem a rodada de cada inclusão."""
    if not DECK.is_file():
        raise FileNotFoundError(f"deck DRC ausente: {DECK}")
    limpar_relatorios()
    klayout = localizar_klayout()
    print("DRC_FINAL: um DRC no layout completo")
    rodar_drc(klayout, "main final", "main", 0, None)


def _ciclo_direto(
    host: gf.kf.KCell,
    secundarios: list[tuple[str, gf.kf.KCell, tuple[float, float]]],
) -> gf.kf.KCell:
    """Inclui todos os circuitos de uma vez, sem DRC a cada inclusão."""
    if DRC_FINAL:
        print("CICLO_NORMAL = False: inclusão direta; DRC só no layout completo")
    else:
        print("CICLO_NORMAL = False: inclusão direta, sem DRC")
    inclusoes: list[tuple[gf.kf.KCell, tuple[float, float]]] = []
    for nome, bloco, origem in secundarios:
        atual = montar(host, inclusoes)
        conferir_inclusao(atual, bloco, origem, nome)
        inclusoes.append((bloco, origem))
    main_comp = montar(host, inclusoes)
    assert_no_layer6(main_comp)
    gravar_gds(main_comp)
    return main_comp


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    host = carregar_celula(gds_lucivaldo(), CELULA_LUCIVALDO)
    assert_no_layer6(host)
    secundarios = _carregar_secundarios()
    if CICLO_NORMAL:
        main_comp = _ciclo_normal(host, secundarios)
    else:
        main_comp = _ciclo_direto(host, secundarios)
        if DRC_FINAL:
            _drc_final()
    gravar_oas(main_comp)
    gravar_png()


if __name__ == "__main__":
    main()
