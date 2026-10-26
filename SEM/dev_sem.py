"""Gera o GDS das janelas de SEM a partir de um CSV.

Cada linha é um retângulo na camada 200 (SEM Imaging). COORDX e COORDY
são o centro, em µm, no referencial do chip: a main inclui o GDS com
origem (0, 0), como as tags.

Regras do NanoSOI Design Center para a camada 200:

- retângulo com aspecto largura:altura = 4:3; a altura sai da WIDTH
- largura mínima 0,5 µm (o DRC recusa menos que isso)
- largura máxima recomendada 50 µm
- o dispositivo de interesse fica no centro
- polígonos podem se sobrepor e podem ser aninhados; a magnificação
  é o tamanho da caixa (imagem sempre 2048 × 1536 px)
- dentro do quadrado de 9 × 9 mm centrado na origem

As larguras 40, 20, 12, 8 e 4 µm são as do SEM_Example.GDS da ANT,
aninhadas no y-branch.

Comando para executar o script:

    ` uv run python SEM/dev_sem.py `
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import photonforge as pf
import siepic_forge as siepic

LADO_UM = 9000.0
LIMITE_UM = LADO_UM / 2.0
CAMADA_SEM = "SEM Imaging"
LARGURA_MIN_UM = 0.5
LARGURA_MAX_UM = 50.0
ASPECTO = 4.0 / 3.0
COLUNAS = ("SEM", "WIDTH", "COORDX", "COORDY")

PASTA = Path(__file__).resolve().parent
ARQUIVOS_CSV = {PASTA / "SEM_chip_Lucivaldo.csv"}

tech = siepic.ebeam()
pf.config.default_technology = tech


def _nome_celula(*partes: object) -> str:
    """Garantir que o nome da célula seja único e sem quebra de linha."""
    bruto = "_".join(str(parte) for parte in partes).replace("\n", "_")
    limpo = "".join(c if c.isalnum() or c in "-_." else "_" for c in bruto)
    while "__" in limpo:
        limpo = limpo.replace("__", "_")
    return limpo.strip("_")


@dataclass(frozen=True)
class Janela:
    nome: str
    largura: float
    centro: tuple[float, float]
    rotulo: str

    @property
    def altura(self) -> float:
        return self.largura / ASPECTO


def _exigir_no_die(x0: float, y0: float, x1: float, y1: float, nome: str) -> None:
    if x0 < -LIMITE_UM or y0 < -LIMITE_UM or x1 > LIMITE_UM or y1 > LIMITE_UM:
        raise ValueError(
            f"{nome} sai do quadrado de {LADO_UM:g}×{LADO_UM:g} µm "
            f"(limites ±{LIMITE_UM:g} µm): "
            f"({x0:.3f}, {y0:.3f}) a ({x1:.3f}, {y1:.3f}) µm"
        )


@pf.parametric_component
def janela_sem(
    *,
    nome: str = "SEM",
    largura: float = 20.0,
    centro: tuple[float, float] = (0.0, 0.0),
) -> pf.Component:
    """Retângulo 4:3 na camada 200, centrado na coordenada do CSV."""
    largura_um = float(largura)
    if largura_um < LARGURA_MIN_UM:
        raise ValueError(
            f"largura {largura_um:g} µm é menor que {LARGURA_MIN_UM:g} µm"
        )
    if largura_um > LARGURA_MAX_UM:
        raise ValueError(
            f"largura {largura_um:g} µm passa de {LARGURA_MAX_UM:g} µm, "
            "o máximo recomendado para a camada 200"
        )

    x = float(centro[0])
    y = float(centro[1])
    altura_um = largura_um / ASPECTO
    x0, x1 = x - largura_um / 2.0, x + largura_um / 2.0
    y0, y1 = y - altura_um / 2.0, y + altura_um / 2.0
    _exigir_no_die(x0, y0, x1, y1, str(nome))

    componente = pf.Component(
        _nome_celula("sem", nome, f"{largura_um:g}", f"{x:g}", f"{y:g}")
    )
    componente.add(
        CAMADA_SEM,
        pf.Rectangle(center=(x, y), size=(largura_um, altura_um)),
    )
    return componente


def ler_janelas(caminho: Path) -> list[Janela]:
    """Lê SEM, WIDTH, COORDX, COORDY e LABEL. WIDTH é a largura em µm."""
    with caminho.open(newline="", encoding="utf-8-sig") as arquivo:
        leitor = csv.DictReader(arquivo, skipinitialspace=True)
        colunas = leitor.fieldnames or ()
        faltando = [coluna for coluna in COLUNAS if coluna not in colunas]
        if faltando:
            raise ValueError(f"{caminho.name} sem as colunas {', '.join(faltando)}")

        janelas = []
        for linha in leitor:
            nome = (linha.get("SEM") or "").strip()
            if not nome:
                continue
            janelas.append(
                Janela(
                    nome=nome,
                    largura=float(linha["WIDTH"]),
                    centro=(float(linha["COORDX"]), float(linha["COORDY"])),
                    rotulo=(linha.get("LABEL") or "").strip(),
                )
            )

    if not janelas:
        raise ValueError(f"nenhuma janela em {caminho}")
    return janelas


def montar_layout(janelas: list[Janela], nome: str) -> tuple[pf.Component, list[pf.Component]]:
    """Monta as janelas já nas coordenadas do chip."""
    janelas_desenho = [
        janela_sem(nome=janela.nome, largura=janela.largura, centro=janela.centro)
        for janela in janelas
    ]
    layout = pf.Component(nome)
    for janela in janelas_desenho:
        layout.add_reference(janela)
    return layout, janelas_desenho


def exportar_gds(layout: pf.Component, destino: Path) -> pf.Component:
    """Grava só a camada 200 e confere o que voltou do arquivo."""
    pf.write_layout(destino, layout)
    conferido = pf.load_layout(destino, technology=tech)[layout.name]
    camadas = conferido.layers(include_dependencies=True)
    if camadas != {(200, 0)}:
        raise RuntimeError(f"{destino.name} saiu com as camadas {sorted(camadas)}")
    if conferido.bounds(layers=[CAMADA_SEM]) is None:
        raise RuntimeError(f"o GDS {destino.name} não tem SEM Imaging")
    return conferido


def _relatar(
    caminho: Path,
    janelas: list[Janela],
    destino: Path,
    conferido: pf.Component,
) -> None:
    print(caminho.name)
    for janela in janelas:
        x, y = janela.centro
        print(
            f"  {janela.nome}: {janela.largura:g}×{janela.altura:g} µm "
            f"centrada em ({x:g}, {y:g}) µm"
        )
        if janela.rotulo:
            print(f"    {janela.rotulo}")
    print(destino.resolve())
    print("  bounds do GDS (µm):", conferido.bounds())
    print("  SEM Imaging (µm):", conferido.bounds(layers=[CAMADA_SEM]))
    print("  camadas:", sorted(conferido.layers(include_dependencies=True)))


def gerar_gds(caminhos_csv: Iterable[str | Path]) -> list[Path]:
    """Cria um GDS para cada CSV, com o mesmo nome e na mesma pasta."""
    caminhos = sorted({Path(caminho).resolve() for caminho in caminhos_csv})
    if not caminhos:
        raise ValueError("nenhum CSV informado")

    destinos = []
    for caminho in caminhos:
        if caminho.suffix.lower() != ".csv":
            raise ValueError(f"esperado um arquivo CSV: {caminho}")
        if not caminho.is_file():
            raise FileNotFoundError(caminho)

        janelas = ler_janelas(caminho)
        layout, _ = montar_layout(janelas, caminho.stem)
        destino = caminho.with_suffix(".gds")
        conferido = exportar_gds(layout, destino)
        _relatar(caminho, janelas, destino, conferido)
        destinos.append(destino)
    return destinos


def main() -> None:
    gerar_gds(ARQUIVOS_CSV)


if __name__ == "__main__":
    main()
