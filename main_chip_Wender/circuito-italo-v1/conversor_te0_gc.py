"""Par de conversores TE0–TE1 e, à direita, o mesmo acesso sem eles.

Os lados largos (TE1, 1,1 µm) se encontram. A entrada e a saída do bloco
são as portas estreitas (TE0, 0,5 µm). Cada grating coupler fica 12 µm
acima ou abaixo da sua porta: duas curvas de 5 µm e um guia de 2 µm
entre elas. Os acopladores ficam em lados opostos do bloco.

A primeira linha tem um par e, 30 µm à direita, o teste dos dois GCs.
Cada linha de baixo acrescenta um par em série, até cinco. O teste de
GCs se repete ao lado, com as mesmas curvas. Há 30 µm entre as caixas.

    uv run python main_chip_Wender/circuito-italo-v1/conversor_te0_gc.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import photonforge as pf

PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parents[1]
GDS = PASTA / "conversor_te0_gc.gds"
CELULA = "b2b_te0_gc"

RAIO_UM = 5.0
RETO_UM = 2.0
FOLGA_UM = 0.05
LARGURA_UM = 0.5
DESNIVEL_UM = 2.0 * RAIO_UM + RETO_UM
AVANCO_UM = 2.0 * RAIO_UM
FOLGA_CIRCUITOS_UM = 30.0
N_LINHAS = 5

_swg = None
_gc: pf.Component | None = None
_rota_entrada: pf.Component | None = None
_rota_saida: pf.Component | None = None


def _italo():
    global _swg
    if _swg is None:
        caminho = RAIZ / "circuito-italo-v1" / "swg_italo.py"
        spec = importlib.util.spec_from_file_location("swg_italo", caminho)
        if spec is None or spec.loader is None:
            raise ImportError(f"não foi possível carregar {caminho}")
        modulo = importlib.util.module_from_spec(spec)
        sys.modules["swg_italo"] = modulo
        spec.loader.exec_module(modulo)
        _swg = modulo
    return _swg


def _copiar(origem: pf.Component, nome: str) -> pf.Component:
    novo = pf.Component(nome, technology=origem.technology)
    for camada, formas in origem.structures.items():
        novo.add(camada, *(forma.copy() for forma in formas))
    for nome_porta, porta in origem.ports.items():
        novo.add_port(porta.copy(), port_name=nome_porta)
    return novo


_conversor: pf.Component | None = None
_par: pf.Component | None = None
_direto: pf.Component | None = None
_series: dict[int, pf.Component] = {}


def conversor() -> pf.Component:
    """Cópia do conversor assimétrico, com nome que não colide no chip."""
    global _conversor
    if _conversor is None:
        _conversor = _copiar(_italo().conversor_te0_te1(), "b2b_conversor")
    return _conversor


def acoplador() -> pf.Component:
    global _gc
    if _gc is None:
        _gc = _copiar(_italo().acoplador(), "b2b_gc")
    return _gc


def _caminho(sentido: float, sinal: float) -> pf.Path:
    """Sai da porta, faz a curva, anda RETO_UM na vertical e curva de novo."""
    x1 = sentido * AVANCO_UM
    y1 = sinal * DESNIVEL_UM
    if sentido > 0:
        caminho = pf.Path((-FOLGA_UM, 0.0), width=LARGURA_UM)
        caminho.segment((0.0, 0.0))
        caminho.turn(sinal * 90, radius=RAIO_UM, endpoint=(RAIO_UM, sinal * RAIO_UM))
        caminho.segment((RAIO_UM, y1 - sinal * RAIO_UM))
        caminho.turn(-sinal * 90, radius=RAIO_UM, endpoint=(x1, y1))
        caminho.segment((x1 + FOLGA_UM, y1))
    else:
        caminho = pf.Path((FOLGA_UM, 0.0), width=LARGURA_UM)
        caminho.segment((0.0, 0.0))
        caminho.turn(-sinal * 90, radius=RAIO_UM, endpoint=(-RAIO_UM, sinal * RAIO_UM))
        caminho.segment((-RAIO_UM, y1 - sinal * RAIO_UM))
        caminho.turn(sinal * 90, radius=RAIO_UM, endpoint=(x1, y1))
        caminho.segment((x1 - FOLGA_UM, y1))
    return caminho


def rota_entrada() -> pf.Component:
    """Da porta TE0 para a esquerda e 12 µm para cima."""
    global _rota_entrada
    if _rota_entrada is None:
        spec = _italo().SPEC_500
        comp = pf.Component("b2b_rota_entrada", technology=_italo().tech)
        comp.add("Si", _caminho(sentido=-1.0, sinal=1.0))
        comp.add_port(pf.Port((0.0, 0.0), 0, spec), port_name="bloco")
        comp.add_port(pf.Port((-AVANCO_UM, DESNIVEL_UM), 180, spec), port_name="gc")
        _rota_entrada = comp
    return _rota_entrada


def rota_saida() -> pf.Component:
    """Da porta TE0 para a direita e 12 µm para baixo."""
    global _rota_saida
    if _rota_saida is None:
        spec = _italo().SPEC_500
        comp = pf.Component("b2b_rota_saida", technology=_italo().tech)
        comp.add("Si", _caminho(sentido=1.0, sinal=-1.0))
        comp.add_port(pf.Port((0.0, 0.0), 180, spec), port_name="bloco")
        comp.add_port(pf.Port((AVANCO_UM, -DESNIVEL_UM), 0, spec), port_name="gc")
        _rota_saida = comp
    return _rota_saida


def reto(comprimento: float) -> pf.Component:
    """Guia de 0,5 µm no lugar dos dois conversores."""
    spec = _italo().SPEC_500
    fim = float(comprimento)
    comp = pf.Component("b2b_reto", technology=_italo().tech)
    caminho = pf.Path((0.0, 0.0), width=LARGURA_UM)
    caminho.segment((fim, 0.0))
    comp.add("Si", caminho)
    comp.add_port(pf.Port((0.0, 0.0), 180, spec), port_name="esquerda")
    comp.add_port(pf.Port((fim, 0.0), 0, spec), port_name="direita")
    return comp


def bloco() -> pf.Component:
    """Dois conversores com as saídas TE1 unidas. Entrada e saída em TE0."""
    global _par
    if _par is not None:
        return _par
    conv = conversor()
    comp = pf.Component("b2b_par", technology=_italo().tech)
    direto = comp.add_reference(conv)
    virado = comp.add_reference(conv)
    virado.connect("largo", direto["largo"])
    if not direto["largo"].is_connected_to(virado["largo"]):
        raise RuntimeError("as portas TE1 não se encontraram")

    if float(virado["estreito"].center[0]) < float(direto["estreito"].center[0]):
        esquerda, direita = virado, direto
    else:
        esquerda, direita = direto, virado

    centro = esquerda["largo"].center
    comp.add(
        "Si",
        pf.Rectangle(
            corner1=(float(centro[0]) - FOLGA_UM, float(centro[1]) - 0.55),
            corner2=(float(centro[0]) + FOLGA_UM, float(centro[1]) + 0.55),
        ),
    )
    comp.add_port(esquerda["estreito"], port_name="entrada")
    comp.add_port(direita["estreito"], port_name="saida")
    _par = comp
    return comp


def _comprimento_par() -> float:
    par = bloco()
    return float(par.ports["saida"].center[0] - par.ports["entrada"].center[0])


def com_serie(pares: int) -> pf.Component:
    """``pares`` blocos TE0–TE0 em série, com um GC em cada ponta."""
    if pares < 1:
        raise ValueError(f"série de {pares} pares")
    pronta = _series.get(pares)
    if pronta is not None:
        return pronta
    tech = _italo().tech
    gc = acoplador()
    comp = pf.Component(f"b2b_serie_{pares}", technology=tech)
    anterior: pf.Reference | None = None
    primeiro: pf.Reference | None = None
    for _ in range(pares):
        atual = comp.add_reference(bloco())
        if anterior is not None:
            atual.connect("entrada", anterior["saida"])
        else:
            primeiro = atual
        anterior = atual
    if primeiro is None or anterior is None:
        raise RuntimeError("série vazia")
    entrada = comp.add_reference(rota_entrada())
    entrada.connect("bloco", primeiro["entrada"])
    saida = comp.add_reference(rota_saida())
    saida.connect("bloco", anterior["saida"])
    gc_entrada = comp.add_reference(gc)
    gc_entrada.connect("saida", entrada["gc"])
    gc_saida = comp.add_reference(gc)
    gc_saida.connect("saida", saida["gc"])
    _encostar(comp)
    comp.add_port(gc_entrada["saida"], port_name="entrada")
    comp.add_port(gc_saida["saida"], port_name="saida")
    _series[pares] = comp
    return comp


def so_gcs() -> pf.Component:
    """Mesmas curvas, com os dois GCs ligados por um guia reto."""
    global _direto
    if _direto is not None:
        return _direto
    tech = _italo().tech
    comp = pf.Component("b2b_direto", technology=tech)
    guia = comp.add_reference(reto(_comprimento_par()))
    gc = acoplador()
    entrada = comp.add_reference(rota_entrada())
    entrada.connect("bloco", guia["esquerda"])
    saida = comp.add_reference(rota_saida())
    saida.connect("bloco", guia["direita"])
    gc_entrada = comp.add_reference(gc)
    gc_entrada.connect("saida", entrada["gc"])
    gc_saida = comp.add_reference(gc)
    gc_saida.connect("saida", saida["gc"])
    _encostar(comp)
    comp.add_port(gc_entrada["saida"], port_name="entrada")
    comp.add_port(gc_saida["saida"], port_name="saida")
    _direto = comp
    return comp


def circuito() -> pf.Component:
    """Cinco linhas. A de cima tem um par; cada linha de baixo soma um par."""
    comp = pf.Component(CELULA, technology=_italo().tech)
    # A linha 1 fica em cima. As outras descem, com 30 µm entre as caixas.
    y = 0.0
    for pares in range(1, N_LINHAS + 1):
        serie = com_serie(pares)
        teste = so_gcs()
        altura = max(_altura(serie), _altura(teste))
        y -= altura
        colocado = comp.add_reference(serie)
        colocado.translate((0.0, y))
        ao_lado = comp.add_reference(teste)
        ao_lado.translate((_caixa(colocado)[2] + FOLGA_CIRCUITOS_UM, y))
        y -= FOLGA_CIRCUITOS_UM
    _encostar(comp)
    return comp


def _altura(comp: pf.Component) -> float:
    (canto0, canto1) = comp.bounds()
    return float(canto1[1] - canto0[1])


def _encostar(comp: pf.Component) -> None:
    """Leva o canto inferior esquerdo para a origem, como as outras células."""
    (x0, y0), _ = comp.bounds()
    dx, dy = -float(x0), -float(y0)
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return
    for ref in comp.references:
        ref.translate((dx, dy))


def _xy(porta: pf.Port) -> tuple[float, float]:
    centro = porta.center
    return float(centro[0]), float(centro[1])


def _caixa(ref: pf.Reference) -> tuple[float, float, float, float]:
    (canto0, canto1) = ref.bounds()
    return float(canto0[0]), float(canto0[1]), float(canto1[0]), float(canto1[1])


def medidas(comp: pf.Component) -> dict[str, float]:
    """Distâncias entre as portas do bloco e as portas dos acopladores."""
    bloco_ref = _referencia(comp, "b2b_par")
    rota_in = _referencia(comp, "b2b_rota_entrada")
    rota_out = _referencia(comp, "b2b_rota_saida")
    gcs = _referencias(comp, "b2b_gc")
    if len(gcs) != 2:
        raise RuntimeError(f"esperava 2 grating couplers, há {len(gcs)}")
    gcs = sorted(gcs, key=lambda ref: float(ref["saida"].center[1]))
    gc_baixo, gc_cima = gcs
    xe, ye = _xy(bloco_ref["entrada"])
    xs, ys = _xy(bloco_ref["saida"])
    xg_e, yg_e = _xy(rota_in["gc"])
    xg_s, yg_s = _xy(rota_out["gc"])
    return {
        "y_entrada": ye,
        "y_saida": ys,
        "dy_entrada": yg_e - ye,
        "dy_saida": yg_s - ys,
        "dx_entrada": xg_e - xe,
        "dx_saida": xg_s - xs,
        "dy_gcs": _xy(gc_cima["saida"])[1] - _xy(gc_baixo["saida"])[1],
    }


def _referencia(comp: pf.Component, nome: str) -> pf.Reference:
    achadas = _referencias(comp, nome)
    if len(achadas) != 1:
        raise RuntimeError(f"{nome}: esperava 1 referência, há {len(achadas)}")
    return achadas[0]


def _referencias(comp: pf.Component, nome: str) -> list[pf.Reference]:
    return [ref for ref in comp.references if ref.component.name == nome]


def _area(formas) -> float:
    if not formas:
        return 0.0
    return float(sum(forma.area() for forma in formas))


def conferir(comp: pf.Component) -> dict[str, float]:
    if comp.name == CELULA:
        return _conferir_conjunto(comp)
    if comp.name == "b2b_direto":
        return _conferir_direto(comp)
    if comp.name.startswith("b2b_serie_"):
        return _conferir_serie(comp, int(comp.name.removeprefix("b2b_serie_")))
    raise RuntimeError(f"célula desconhecida: {comp.name}")


def _conferir_serie(comp: pf.Component, pares: int) -> dict[str, float]:
    blocos = sorted(
        _referencias(comp, "b2b_par"),
        key=lambda ref: float(ref["entrada"].center[0]),
    )
    if len(blocos) != pares:
        raise RuntimeError(f"{comp.name}: {len(blocos)} pares, esperava {pares}")
    for esquerda, direita in zip(blocos, blocos[1:]):
        if not esquerda["saida"].is_connected_to(direita["entrada"]):
            raise RuntimeError(f"{comp.name}: os pares não estão em série")
        _sem_invasao(esquerda, direita, f"pares de {comp.name}", teto=0.02)
    rota_in = _referencia(comp, "b2b_rota_entrada")
    rota_out = _referencia(comp, "b2b_rota_saida")
    primeiro, ultimo = blocos[0], blocos[-1]
    if not rota_in["bloco"].is_connected_to(primeiro["entrada"]):
        raise RuntimeError(f"{comp.name}: a rota de entrada não encontra o primeiro par")
    if not rota_out["bloco"].is_connected_to(ultimo["saida"]):
        raise RuntimeError(f"{comp.name}: a rota de saída não encontra o último par")
    gc_baixo, gc_cima = _gcs(comp)
    if not gc_cima["saida"].is_connected_to(rota_in["gc"]):
        raise RuntimeError(f"{comp.name}: o GC de entrada não encontra a rota")
    if not gc_baixo["saida"].is_connected_to(rota_out["gc"]):
        raise RuntimeError(f"{comp.name}: o GC de saída não encontra a rota")
    nums = {
        "dy_entrada": _xy(rota_in["gc"])[1] - _xy(primeiro["entrada"])[1],
        "dy_saida": _xy(rota_out["gc"])[1] - _xy(ultimo["saida"])[1],
        "dx_entrada": _xy(rota_in["gc"])[0] - _xy(primeiro["entrada"])[0],
        "dx_saida": _xy(rota_out["gc"])[0] - _xy(ultimo["saida"])[0],
        "dy_gcs": _xy(gc_cima["saida"])[1] - _xy(gc_baixo["saida"])[1],
    }
    _exigir_acessos(nums)
    queda = _xy(primeiro["entrada"])[1] - _xy(ultimo["saida"])[1]
    queda_par = _xy(bloco().ports["entrada"])[1] - _xy(bloco().ports["saida"])[1]
    if abs(queda - pares * queda_par) > 1e-6:
        raise RuntimeError(f"{comp.name}: queda {queda:.4f} µm")
    if abs(nums["dy_gcs"] - (2.0 * DESNIVEL_UM + queda)) > 1e-6:
        raise RuntimeError(f"{comp.name}: GCs a {nums['dy_gcs']:.4f} µm")
    _sem_invasao(primeiro, rota_in, f"entrada de {comp.name}")
    _sem_invasao(ultimo, rota_out, f"saída de {comp.name}")
    _sem_invasao(rota_in, gc_cima, f"GC de entrada de {comp.name}", teto=0.08)
    _sem_invasao(rota_out, gc_baixo, f"GC de saída de {comp.name}", teto=0.08)
    return nums


def _conferir_direto(comp: pf.Component) -> dict[str, float]:
    guia = _referencia(comp, "b2b_reto")
    rota_in = _referencia(comp, "b2b_rota_entrada")
    rota_out = _referencia(comp, "b2b_rota_saida")
    gc_baixo, gc_cima = _gcs(comp)
    if not rota_in["bloco"].is_connected_to(guia["esquerda"]):
        raise RuntimeError("a rota de entrada não encontra o guia reto")
    if not rota_out["bloco"].is_connected_to(guia["direita"]):
        raise RuntimeError("a rota de saída não encontra o guia reto")
    if not gc_cima["saida"].is_connected_to(rota_in["gc"]):
        raise RuntimeError("o GC direto de entrada não encontra a rota")
    if not gc_baixo["saida"].is_connected_to(rota_out["gc"]):
        raise RuntimeError("o GC direto de saída não encontra a rota")
    nums = {
        "dy_entrada": _xy(rota_in["gc"])[1] - _xy(guia["esquerda"])[1],
        "dy_saida": _xy(rota_out["gc"])[1] - _xy(guia["direita"])[1],
        "dx_entrada": _xy(rota_in["gc"])[0] - _xy(guia["esquerda"])[0],
        "dx_saida": _xy(rota_out["gc"])[0] - _xy(guia["direita"])[0],
        "dy_gcs": _xy(gc_cima["saida"])[1] - _xy(gc_baixo["saida"])[1],
        "reto": _xy(guia["direita"])[0] - _xy(guia["esquerda"])[0],
    }
    _exigir_acessos(nums)
    if abs(nums["dy_gcs"] - 2.0 * DESNIVEL_UM) > 1e-6:
        raise RuntimeError(f"GCs diretos separados por {nums['dy_gcs']:.4f} µm")
    if abs(nums["reto"] - _comprimento_par()) > 1e-6:
        raise RuntimeError(f"guia reto mede {nums['reto']:.4f} µm")
    _sem_invasao(guia, rota_in, "reta e entrada", teto=0.04)
    _sem_invasao(guia, rota_out, "reta e saída", teto=0.04)
    _sem_invasao(guia, gc_cima, "reta e GC de cima", teto=0.0)
    _sem_invasao(guia, gc_baixo, "reta e GC de baixo", teto=0.0)
    return nums


def _conferir_conjunto(comp: pf.Component) -> dict[str, float]:
    series = [
        _referencia(comp, f"b2b_serie_{pares}") for pares in range(1, N_LINHAS + 1)
    ]
    testes = sorted(_referencias(comp, "b2b_direto"), key=lambda ref: _caixa(ref)[1])
    if len(testes) != N_LINHAS:
        raise RuntimeError(f"esperava {N_LINHAS} testes de GC, há {len(testes)}")
    for indice, serie in enumerate(series):
        _conferir_serie(serie.component, indice + 1)
    _conferir_direto(testes[0].component)
    series_por_y = sorted(series, key=lambda ref: _caixa(ref)[1])
    for indice, (serie, teste) in enumerate(zip(series_por_y, testes)):
        caixa_s = _caixa(serie)
        caixa_t = _caixa(teste)
        folga = caixa_t[0] - caixa_s[2]
        if abs(folga - FOLGA_CIRCUITOS_UM) > 1e-6:
            raise RuntimeError(f"linha {indice + 1}: folga horizontal {folga:.4f} µm")
        if abs(caixa_s[1] - caixa_t[1]) > 1e-6:
            raise RuntimeError(f"linha {indice + 1}: o teste não acompanha a base")
        _sem_invasao(serie, teste, f"linha {indice + 1}", teto=0.0)
        if indice:
            acima = _caixa(series_por_y[indice - 1])
            vao = caixa_s[1] - acima[3]
            if abs(vao - FOLGA_CIRCUITOS_UM) > 1e-6:
                raise RuntimeError(f"folga vertical {vao:.4f} µm")
    if abs(_caixa(series_por_y[0])[0]) > 1e-6:
        raise RuntimeError("a primeira série não encosta em x = 0")
    return {"linhas": float(N_LINHAS)}


def _gcs(comp: pf.Component) -> tuple[pf.Reference, pf.Reference]:
    gcs = sorted(
        _referencias(comp, "b2b_gc"),
        key=lambda ref: float(ref["saida"].center[1]),
    )
    if len(gcs) != 2:
        raise RuntimeError(f"esperava 2 grating couplers, há {len(gcs)}")
    return gcs[0], gcs[1]


def _exigir_acessos(nums: dict[str, float]) -> None:
    if abs(nums["dy_entrada"] - DESNIVEL_UM) > 1e-6:
        raise RuntimeError(f"desnível da entrada {nums['dy_entrada']:.4f} µm")
    if abs(nums["dy_saida"] + DESNIVEL_UM) > 1e-6:
        raise RuntimeError(f"desnível da saída {nums['dy_saida']:.4f} µm")
    if abs(nums["dx_entrada"] + AVANCO_UM) > 1e-6:
        raise RuntimeError(f"avanço da entrada {nums['dx_entrada']:.4f} µm")
    if abs(nums["dx_saida"] - AVANCO_UM) > 1e-6:
        raise RuntimeError(f"avanço da saída {nums['dx_saida']:.4f} µm")


def _silicio(ref: pf.Reference):
    formas = ref.get_structures("Si")
    if not formas:
        formas = ref.get_structures((1, 0))
    return formas


def _sem_invasao(
    um: pf.Reference,
    outro: pf.Reference,
    nome: str,
    teto: float = 0.04,
) -> None:
    """A folga de 50 nm em cada porta pode se sobrepor. O resto, não."""
    cruz = pf.boolean(_silicio(um), _silicio(outro), "*")
    area = _area(cruz)
    if area > teto:
        raise RuntimeError(f"{nome} invade silício ({area:.4f} µm²)")


def exportar(comp: pf.Component | None = None) -> pf.Component:
    pronto = circuito() if comp is None else comp
    conferir(pronto)
    pf.write_layout(str(GDS), pronto)
    return pronto


def relatorio(comp: pf.Component) -> str:
    (x0, y0), (x1, y1) = comp.bounds()
    linhas = [
        f"célula {comp.name}",
        f"caixa {float(x1) - float(x0):.3f} × {float(y1) - float(y0):.3f} µm",
    ]
    if comp.name == CELULA:
        for pares in range(1, N_LINHAS + 1):
            serie = _referencia(comp, f"b2b_serie_{pares}")
            nums = _conferir_serie(serie.component, pares)
            linhas.append(f"linha {pares}: {pares} par(es), GCs a {nums['dy_gcs']:.3f} µm")
        linhas.append(f"folga entre as caixas: {FOLGA_CIRCUITOS_UM:.3f} µm")
    linhas.append(f"GDS {GDS}")
    return "\n".join(linhas)


if __name__ == "__main__":
    componente = exportar()
    print(relatorio(componente))
