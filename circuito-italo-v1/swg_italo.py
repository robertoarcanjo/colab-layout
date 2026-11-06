"""Reconstrói o circuito do Ítalo e varre o box length do SWG.

Cada faixa tem cinco circuitos. Cada circuito tem dois SWG 1×3 iguais:
um alimentado em TE1 (conversor assimétrico) e outro em TE0 (taper
simétrico). A saída dos dois é sempre TE0, nos três guias de 0,5 µm.

A primeira faixa (a de cima) repete o box length de 40,92 µm. As outras
deslizam um período de 0,22 µm por faixa e, dentro da faixa, um período
por coluna.

No Lucivaldo são 10 faixas: a de cima repete 40,92 µm e as outras nove
varrem. No Wender são 12 faixas, seis em cada coluna. As linhas 1 e 6
repetem 40,92 µm. O sweep das linhas 2 a 5 continua nas linhas 7 a 12,
na coluna da direita, e passa um período do último valor do Lucivaldo.

    uv run python circuito-italo-v1/swg_italo.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

import photonforge as pf
import siepic_forge as siepic

RAIZ = Path(__file__).resolve().parent.parent
PASTA = Path(__file__).resolve().parent
GDS_ORIGINAL = PASTA / "Nanotools_Italo_SWG_original.gds"
GDS_LUCIVALDO = PASTA / "Nanotools_Italo_SWG.gds"
GDS_WENDER = RAIZ / "main_chip_Wender" / "circuito-italo-v1" / "Nanotools_Italo_SWG.gds"
GDS_WENDER_ORIGINAL = (
    RAIZ / "main_chip_Wender" / "circuito-italo-v1" / "Nanotools_Italo_SWG_original.gds"
)

# Período e comprimentos em nm, para a grade de 1 nm fechar sem deriva.
PERIODO_NM = 220
FENDA_SI_NM = 110
TAPER_NM = 60280
CAIXA_NM = 40920
LARGURA_ENTRADA_NM = 1100
LARGURA_CENTRAL_NM = 4000
LARGURA_LATERAL_NM = 1900
LARGURA_SAIDA_NM = 500
FOLGA_NM = 100
N_TAPER = TAPER_NM // PERIODO_NM
N_CAIXA = CAIXA_NM // PERIODO_NM

RAIO_UM = 5.0
PASSO_COLUNA_UM = 328.0
CANAL_UM = 230.0
ENTRADA_X_UM = 42.39
Y_TE1_UM = 58.68
Y_TE0_UM = 176.22
YS_GC_UM = (14.0, 77.0, 140.0, 203.0, 266.0)
PASSO_FAIXA_UM = 400.0
LARGURA_FAIXA_UM = 1622.0
ALTURA_FAIXA_UM = 280.0

tech = siepic.ebeam()
pf.config.default_technology = tech
SPEC_500 = tech.ports["TE_1550_500"]
SPEC_1100 = pf.PortSpec(
    "Strip TE 1550 nm, w=1100 nm",
    1.55,
    SPEC_500.limits,
    num_modes=SPEC_500.num_modes,
    target_neff=SPEC_500.target_neff,
    path_profiles=[(1.1, 0.0, (1, 0))],
)

_acoplador: pf.Component | None = None
_faixas: dict[tuple[int, ...], pf.Component] = {}
_rotas = 0


def um(nm: int) -> float:
    return nm / 1000.0


def caixa_um(periodos: int) -> float:
    return um(periodos * PERIODO_NM)


def centro_um(indice: int) -> float:
    return um((2 * indice + 1) * (PERIODO_NM // 2))


def largura_um(nm: float) -> float:
    return round(nm) / 1000.0


def _reserva_original(destino: Path, origem: Path) -> None:
    if destino.is_file():
        return
    if not origem.is_file():
        raise FileNotFoundError(f"GDS original ausente: {origem}")
    shutil.copy2(origem, destino)


@pf.parametric_component
def mmi_swg(*, box_length: float = 40.92) -> pf.Component:
    """SWG 1×3. A entrada fica em x = 0; as três saídas, à direita."""
    caixa = float(box_length)
    n_caixa = int(round(caixa / um(PERIODO_NM)))
    if n_caixa < 1 or abs(caixa_um(n_caixa) - round(caixa, 3)) > 1e-6:
        raise ValueError(f"box length {caixa} µm não é múltiplo de 0,22 µm")

    n_total = 2 * N_TAPER + n_caixa
    comprimento = um((2 * N_TAPER + n_caixa) * PERIODO_NM)
    x_caixa = um(TAPER_NM)
    x_saida = um(TAPER_NM + n_caixa * PERIODO_NM)
    centro_lateral = um(LARGURA_CENTRAL_NM // 2 + FOLGA_NM + LARGURA_LATERAL_NM // 2)
    meia_caixa = um(
        LARGURA_LATERAL_NM + FOLGA_NM + LARGURA_CENTRAL_NM + FOLGA_NM + LARGURA_LATERAL_NM
    ) / 2.0

    comp = pf.Component(f"MMI_1x3_SWG_{n_caixa}", technology=tech)
    dentes: list[pf.Rectangle] = []
    for indice in range(n_total):
        x = centro_um(indice)
        x0 = round(x - um(FENDA_SI_NM) / 2.0, 3)
        x1 = round(x + um(FENDA_SI_NM) / 2.0, 3)
        if indice < N_TAPER:
            trecho = x / um(TAPER_NM)
            largura = largura_um(
                LARGURA_ENTRADA_NM
                + (LARGURA_CENTRAL_NM - LARGURA_ENTRADA_NM) * trecho
            )
            dentes.append(_retangulo(x0, x1, 0.0, largura))
        elif indice < N_TAPER + n_caixa:
            dentes.append(_retangulo(x0, x1, 0.0, 2.0 * meia_caixa))
        else:
            trecho = (x - x_saida) / um(TAPER_NM)
            central = largura_um(
                LARGURA_CENTRAL_NM
                + (LARGURA_SAIDA_NM - LARGURA_CENTRAL_NM) * trecho
            )
            lateral = largura_um(
                LARGURA_LATERAL_NM
                + (LARGURA_SAIDA_NM - LARGURA_LATERAL_NM) * trecho
            )
            dentes.append(_retangulo(x0, x1, 0.0, central))
            dentes.append(_retangulo(x0, x1, centro_lateral, lateral))
            dentes.append(_retangulo(x0, x1, -centro_lateral, lateral))

    # O núcleo contínuo atravessa as fendas de óxido do taper e entra um
    # slot de silício na caixa, como no GDS de origem.
    nucleo_x1 = round(x_caixa + um(FENDA_SI_NM), 3)
    nucleo_x0 = round(x_saida - um(FENDA_SI_NM), 3)
    dentes.append(
        pf.Rectangle(
            corner1=(0.0, -um(LARGURA_ENTRADA_NM) / 2.0),
            corner2=(nucleo_x1, um(LARGURA_ENTRADA_NM) / 2.0),
        )
    )
    for centro in (-centro_lateral, 0.0, centro_lateral):
        meia = um(LARGURA_SAIDA_NM) / 2.0
        dentes.append(
            pf.Rectangle(
                corner1=(nucleo_x0, centro - meia),
                corner2=(comprimento, centro + meia),
            )
        )
    comp.add("Si", *dentes)
    comp.add_port(pf.Port((0.0, 0.0), 180, SPEC_1100), port_name="entrada")
    comp.add_port(
        pf.Port((comprimento, -centro_lateral), 0, SPEC_500),
        port_name="saida_inf",
    )
    comp.add_port(pf.Port((comprimento, 0.0), 0, SPEC_500), port_name="saida_centro")
    comp.add_port(
        pf.Port((comprimento, centro_lateral), 0, SPEC_500),
        port_name="saida_sup",
    )
    return comp


def _retangulo(x0: float, x1: float, centro_y: float, largura: float) -> pf.Rectangle:
    meia = largura / 2.0
    return pf.Rectangle(
        corner1=(x0, round(centro_y - meia, 3)),
        corner2=(x1, round(centro_y + meia, 3)),
    )


@pf.parametric_component
def conversor_te0_te1() -> pf.Component:
    """Conversor assimétrico. O lado largo (1,1 µm) entra no SWG."""
    comp = pf.Component("conversor_te0_te1", technology=tech)
    comp.add("Si", pf.Rectangle(corner1=(-2.0, 0.0), corner2=(0.0, 1.1)))
    comp.add(
        "Si",
        pf.Polygon([(0.735, 0.0), (0.735, 1.55), (0.0, 1.1), (0.0, 0.0)]),
        pf.Polygon([(7.051, 0.0), (7.051, 2.653), (0.735, 1.55), (0.735, 0.0)]),
        pf.Polygon([(9.668, 0.0), (9.668, 2.828), (7.051, 2.653), (7.051, 0.0)]),
        pf.Polygon([(12.464, 0.0), (12.464, 2.653), (9.668, 2.828), (9.668, 0.0)]),
        pf.Polygon([(15.518, 0.0), (15.518, 1.5), (12.464, 2.653), (12.464, 0.0)]),
        pf.Polygon([(25.464, 0.0), (25.464, 0.5), (15.518, 1.5), (15.518, 0.0)]),
        pf.Rectangle(corner1=(25.464, 0.0), corner2=(27.464, 0.5)),
    )
    comp.add_port(pf.Port((-2.0, 0.55), 180, SPEC_1100), port_name="largo")
    comp.add_port(pf.Port((27.464, 0.25), 0, SPEC_500), port_name="estreito")
    return comp


@pf.parametric_component
def taper_te0(*, length: float = 10.0) -> pf.Component:
    """Taper simétrico de 0,5 µm para 1,1 µm. Preserva o TE0."""
    comp = pf.Component("taper_te0_10um", technology=tech)
    comp.add("Si", pf.Polygon([(0.0, 0.25), (0.0, -0.25), (10.0, -0.55), (10.0, 0.55)]))
    comp.add_port(pf.Port((0.0, 0.0), 180, SPEC_500), port_name="estreito")
    comp.add_port(pf.Port((float(length), 0.0), 0, SPEC_1100), port_name="largo")
    return comp


def acoplador() -> pf.Component:
    """Grating coupler de óxido a 8°, com a porta em (0, 0) apontando para −y."""
    global _acoplador
    if _acoplador is not None:
        return _acoplador
    if not GDS_ORIGINAL.is_file():
        raise FileNotFoundError(f"GDS original ausente: {GDS_ORIGINAL}")
    celulas = pf.load_layout(
        str(GDS_ORIGINAL),
        technology=tech,
        cell_names=["GratingCoupler_TE_Oxide_8degrees-"],
    )
    base = celulas["GratingCoupler_TE_Oxide_8degrees-"]
    comp = pf.Component("gc_te_oxido_8graus", technology=tech)
    for camada, formas in base.structures.items():
        comp.add(camada, *formas)
    comp.add_port(pf.Port((0.0, 0.0), -90, SPEC_500), port_name="saida")
    _acoplador = comp
    return comp


def _nome_rota() -> str:
    global _rotas
    _rotas += 1
    return f"rota_{_rotas}"


def _reto(pai: pf.Component, x0: float, x1: float, y: float) -> None:
    """Guia reto. Entra 50 nm em cada porta para o silício fechar."""
    caminho = pf.Path((x0 - 0.05, y), width=0.5)
    caminho.segment((x1 + 0.05, y))
    trecho = pf.Component(_nome_rota(), technology=tech)
    trecho.add("Si", caminho)
    pai.add_reference(trecho)


def _guia(
    pai: pf.Component,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    recuo: float,
) -> None:
    """Duas curvas de 90° entre portas alinhadas em x, com a vertical deslocada."""
    raio = RAIO_UM
    if abs(y1 - y0) < 2.0 * raio + 0.2:
        raise ValueError(f"desnível {y1 - y0:.2f} µm não cabe o raio {raio}")
    if abs(x1 - x0) < 2.0 * raio + 0.5:
        raise ValueError(f"canal {x1 - x0:.2f} µm não cabe duas curvas de {raio}")
    sentido = 1.0 if x1 > x0 else -1.0
    sinal = 1.0 if y1 > y0 else -1.0
    margem = raio + 0.8
    if sentido > 0:
        x_vert = min(max(x0 + recuo, x0 + margem), x1 - margem)
        xa = x0 - 0.05
        xb = x1 + 0.05
        caminho = pf.Path((xa, y0), width=0.5)
        caminho.segment((x_vert - raio, y0))
        caminho.turn(sinal * 90, radius=raio, endpoint=(x_vert, y0 + sinal * raio))
        caminho.segment((x_vert, y1 - sinal * raio))
        caminho.turn(-sinal * 90, radius=raio, endpoint=(x_vert + raio, y1))
    else:
        x_vert = max(min(x0 - recuo, x0 - margem), x1 + margem)
        xa = x0 + 0.05
        xb = x1 - 0.05
        caminho = pf.Path((xa, y0), width=0.5)
        caminho.segment((x_vert + raio, y0))
        caminho.turn(-sinal * 90, radius=raio, endpoint=(x_vert, y0 + sinal * raio))
        caminho.segment((x_vert, y1 - sinal * raio))
        caminho.turn(sinal * 90, radius=raio, endpoint=(x_vert - raio, y1))
    caminho.segment((xb, y1))
    trecho = pf.Component(_nome_rota(), technology=tech)
    trecho.add("Si", caminho)
    pai.add_reference(trecho)


def coluna(periodos: int) -> pf.Component:
    """Um par de SWG (TE1 embaixo, TE0 em cima) entre duas fileiras de GC."""
    if periodos < 1:
        raise ValueError(f"box de {periodos} períodos é curto demais")
    comp = pf.Component(f"coluna_{periodos}", technology=tech)
    caixa = caixa_um(periodos)
    comprimento = um((2 * N_TAPER + periodos) * PERIODO_NM)
    x_direita = CANAL_UM + (caixa - caixa_um(N_CAIXA))
    gc = acoplador()

    esq: list[pf.Reference] = []
    dire: list[pf.Reference] = []
    for y in YS_GC_UM:
        ref = comp.add_reference(gc)
        ref.origin = (0.0, y)
        ref.rotation = 90
        esq.append(ref)
        ref = comp.add_reference(gc)
        ref.origin = (x_direita, y)
        ref.rotation = -90
        dire.append(ref)

    _reto(comp, 0.0, x_direita, YS_GC_UM[4])

    swg = mmi_swg(box_length=caixa)
    baixo = comp.add_reference(swg)
    baixo.origin = (ENTRADA_X_UM, Y_TE1_UM)
    conv = comp.add_reference(conversor_te0_te1())
    conv.connect("largo", baixo["entrada"])
    _guia(
        comp,
        0.0,
        YS_GC_UM[0],
        float(conv["estreito"].center[0]),
        float(conv["estreito"].center[1]),
        6.5,
    )

    _fanout(comp, baixo, ("saida_inf", "saida_centro", "saida_sup"), dire[:3])

    cima = comp.add_reference(swg)
    cima.rotation = 180
    cima.origin = (ENTRADA_X_UM + comprimento, Y_TE0_UM)
    taper = comp.add_reference(taper_te0())
    taper.connect("largo", cima["entrada"])
    _fanout(comp, cima, ("saida_inf", "saida_centro", "saida_sup"), esq[1:4])
    _guia(
        comp,
        float(taper["estreito"].center[0]),
        float(taper["estreito"].center[1]),
        x_direita,
        YS_GC_UM[3],
        8.0,
    )
    return comp


def _fanout(
    pai: pf.Component,
    swg: pf.Reference,
    portas: tuple[str, str, str],
    gcs: list[pf.Reference],
) -> None:
    ordenadas = sorted(portas, key=lambda nome: float(swg[nome].center[1]))
    alvos = sorted(gcs, key=lambda ref: float(ref["saida"].center[1]))
    for ordem, (nome, gc) in enumerate(zip(ordenadas, alvos)):
        recuo = 16.0 if ordem == 1 else 8.0
        _guia(
            pai,
            float(swg[nome].center[0]),
            float(swg[nome].center[1]),
            float(gc["saida"].center[0]),
            float(gc["saida"].center[1]),
            recuo,
        )


_colunas: dict[int, pf.Component] = {}


def coluna_cache(periodos: int) -> pf.Component:
    if periodos not in _colunas:
        _colunas[periodos] = coluna(periodos)
    return _colunas[periodos]


def periodos_da_faixa(indice: int) -> tuple[int, ...]:
    """Faixa 0: cinco SWG em 186 períodos. As outras deslizam de 0,22 µm."""
    if indice == 0:
        return (N_CAIXA,) * 5
    return tuple(N_CAIXA + (indice - 5) + (coluna_i - 2) for coluna_i in range(5))


def faixa(indice: int) -> pf.Component:
    chave = periodos_da_faixa(indice)
    pronta = _faixas.get(chave)
    if pronta is not None:
        return pronta
    comp = pf.Component("faixa_" + "_".join(str(n) for n in chave), technology=tech)
    x = 40.0
    for periodos in chave:
        ref = comp.add_reference(coluna_cache(periodos))
        ref.origin = (x, 0.0)
        x += PASSO_COLUNA_UM + (caixa_um(periodos) - caixa_um(N_CAIXA))
    _faixas[chave] = comp
    return comp


def _montar(nome: str, posicoes: list[tuple[float, float, int]]) -> pf.Component:
    topo = pf.Component(nome, technology=tech)
    for x, y, indice in posicoes:
        ref = topo.add_reference(faixa(indice))
        ref.origin = (x, y)
    return topo


def posicoes_lucivaldo() -> list[tuple[float, float, int]]:
    """Dez faixas. As seis de cima na coluna x=0; as quatro de baixo, em x=150."""
    n = 10
    posicoes = []
    for indice in range(n):
        k = (n - 1) - indice
        x = 0.0 if k >= 4 else 150.0
        posicoes.append((x, k * PASSO_FAIXA_UM, indice))
    return posicoes


def posicoes_wender() -> list[tuple[float, float, int]]:
    """Doze faixas: seis na esquerda (linhas 1 a 6) e seis na direita (7 a 12).

    As linhas 1 e 6 repetem o box de 40,92 µm. As linhas 2 a 5 varrem, e
    as linhas 7 a 12 continuam esse sweep na coluna da direita.
    """
    # Índice de periodos_da_faixa na ordem das linhas 1..12.
    indices = (0, 1, 2, 3, 4, 0, 5, 6, 7, 8, 9, 10)
    posicoes = []
    for linha, indice in enumerate(indices):
        coluna = 0 if linha < 6 else 1
        altura = linha if linha < 6 else linha - 6
        y = (5 - altura) * PASSO_FAIXA_UM
        posicoes.append((coluna * 1800.0, y, indice))
    return posicoes


def _conferir_faixa(indice: int) -> None:
    comp = faixa(indice)
    (x0, y0), (x1, y1) = comp.bounds()
    extra = sum(caixa_um(n) - caixa_um(N_CAIXA) for n in periodos_da_faixa(indice))
    esperado = LARGURA_FAIXA_UM + extra
    if abs(float(x0)) > 0.02 or abs(float(y0)) > 0.02:
        raise RuntimeError(f"faixa {indice} não começa em (0, 0): {(x0, y0)}")
    if abs(float(x1) - esperado) > 0.05 or abs(float(y1) - ALTURA_FAIXA_UM) > 0.05:
        raise RuntimeError(
            f"faixa {indice} mede {float(x1):.3f} × {float(y1):.3f} µm; "
            f"esperado {esperado:.3f} × {ALTURA_FAIXA_UM:.3f}"
        )


def gerar() -> tuple[pf.Component, pf.Component]:
    _reserva_original(GDS_ORIGINAL, PASTA / "Nanotools_Italo_SWG.gds")
    _reserva_original(GDS_WENDER_ORIGINAL, GDS_WENDER)
    for indice in range(11):
        _conferir_faixa(indice)
    lucivaldo = _montar("TOP", posicoes_lucivaldo())
    wender = _montar("TOP_Wender", posicoes_wender())
    pf.write_layout(str(GDS_LUCIVALDO), lucivaldo)
    pf.write_layout(str(GDS_WENDER), wender)
    _renomear_topo(GDS_WENDER, "TOP_Wender", "TOP")
    return lucivaldo, wender


def _renomear_topo(caminho: Path, atual: str, novo: str) -> None:
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(caminho))
    celula = layout.cell(atual)
    if celula is None:
        raise RuntimeError(f"célula {atual} ausente em {caminho.name}")
    celula.name = novo
    layout.write(str(caminho))


def tabela() -> str:
    linhas = ["faixa  coluna  períodos  box_um"]
    for indice in range(10):
        for coluna_i, periodos in enumerate(periodos_da_faixa(indice)):
            linhas.append(
                f"{indice:5d}  {coluna_i:6d}  {periodos:8d}  {caixa_um(periodos):7.2f}"
            )
    return "\n".join(linhas)


if __name__ == "__main__":
    gerar()
    print(tabela())
    print(f"GDS Lucivaldo: {GDS_LUCIVALDO}")
    print(f"GDS Wender: {GDS_WENDER}")
