"""Gera o GDS das tags de circuito a partir de um ou mais CSVs.


Comando para executar o script:

    ` uv run python tag-layout/dev_tags.py `
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
LADOS = ("esquerda", "direita", "cima", "baixo")
CAMADA_SILICIO = "Si"
CAMADA_MOLDURA = "Floor Plan-Not Fabricated"
CAMADA_TEXTO = "Text"
LARGURA_MOLDURA_UM = 40.0
TRACO_MINIMO_UM = 0.06
FRACA_DA_ALTURA = 0.025
COLUNAS = ("TAG", "SIZE", "COORDX", "COORDY", "POS")

PASTA = Path(__file__).resolve().parent
ARQUIVOS_CSV = {
    PASTA / "tags_chip_Wender.csv",
    PASTA / "tags_chip_Lucivaldo.csv",
}

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
class Tag:
    texto: str
    tamanho: float
    coordenada: tuple[float, float]
    posicao: str
    rotulo: str


@pf.parametric_component
def caractere(*, texto: str = "A", tamanho: float = 10.0) -> pf.Component:
    """Desenha um texto ASCII na camada de silício (1/0)."""
    texto_str = str(texto)
    if not texto_str.strip():
        raise ValueError("texto não pode ser vazio")
    tamanho_um = float(tamanho)
    if tamanho_um * FRACA_DA_ALTURA < TRACO_MINIMO_UM:
        raise ValueError("Podem existir guias separados por menos de 60 nm.")

    componente = pf.Component(_nome_celula("char", texto_str, f"{tamanho_um:g}"))
    componente.add(CAMADA_SILICIO, *pf.text(texto_str, tamanho_um, typeface=1))
    return componente


def _ancora_do_bloco(limites, lado: str) -> tuple[float, float]:
    """Meio da lateral escolhida do bloco de texto, em µm."""
    (x_min, y_min), (x_max, y_max) = limites
    x_meio = (float(x_min) + float(x_max)) / 2.0
    y_meio = (float(y_min) + float(y_max)) / 2.0
    if lado == "esquerda":
        return float(x_min), y_meio
    if lado == "direita":
        return float(x_max), y_meio
    if lado == "cima":
        return x_meio, float(y_max)
    return x_meio, float(y_min)


@pf.parametric_component
def texto_posicionado(
    *,
    texto: str = "A",
    tamanho: float = 10.0,
    coordenada: tuple[float, float] = (0.0, 0.0),
    posicao: str = "esquerda",
) -> pf.Component:
    """Coloca o texto com a âncora do lado pedido sobre a coordenada."""
    x = float(coordenada[0])
    y = float(coordenada[1])
    if abs(x) > LIMITE_UM or abs(y) > LIMITE_UM:
        raise ValueError(
            f"coordenada ({x:g}, {y:g}) µm fora do quadrado de "
            f"{LADO_UM:g}×{LADO_UM:g} µm com centro na origem "
            f"(limites ±{LIMITE_UM:g} µm)"
        )

    lado = str(posicao).strip().lower()
    if lado not in LADOS:
        raise ValueError("posicao deve ser esquerda, direita, cima ou baixo")

    bloco = caractere(texto=texto, tamanho=tamanho)
    ancora_x, ancora_y = _ancora_do_bloco(bloco.bounds(), lado)

    componente = pf.Component(_nome_celula("texto", lado, f"{x:g}", f"{y:g}"))
    referencia = componente.add_reference(bloco)
    referencia.translate((x - ancora_x, y - ancora_y))

    (x0, y0), (x1, y1) = componente.bounds()
    if (
        float(x0) < -LIMITE_UM
        or float(y0) < -LIMITE_UM
        or float(x1) > LIMITE_UM
        or float(y1) > LIMITE_UM
    ):
        raise ValueError(
            "o bloco de texto ultrapassa o quadrado de "
            f"{LADO_UM:g}×{LADO_UM:g} µm "
            f"(limites do texto: ({float(x0):.2f}, {float(y0):.2f}) a "
            f"({float(x1):.2f}, {float(y1):.2f}) µm)"
        )
    return componente


def ler_tags(caminho: Path) -> list[Tag]:
    """Lê TAG, SIZE, COORDX, COORDY, POS e LABEL. ``\\n`` na TAG vira quebra de linha."""
    with caminho.open(newline="", encoding="utf-8-sig") as arquivo:
        leitor = csv.DictReader(arquivo, skipinitialspace=True)
        colunas = leitor.fieldnames or ()
        faltando = [coluna for coluna in COLUNAS if coluna not in colunas]
        if faltando:
            raise ValueError(f"{caminho.name} sem as colunas {', '.join(faltando)}")

        tags = []
        for linha in leitor:
            texto = (linha.get("TAG") or "").strip().replace("\\n", "\n")
            if not texto:
                continue
            tags.append(
                Tag(
                    texto=texto,
                    tamanho=float(linha["SIZE"]),
                    coordenada=(float(linha["COORDX"]), float(linha["COORDY"])),
                    posicao=(linha.get("POS") or "").strip(),
                    rotulo=(linha.get("LABEL") or "").strip(),
                )
            )

    if not tags:
        raise ValueError(f"nenhum texto em {caminho}")
    return tags


def montar_layout(tags: list[Tag], nome: str) -> tuple[pf.Component, list[pf.Component]]:
    """Monta as tags e a moldura do quadrado. A moldura não vai para o GDS."""
    textos = [
        texto_posicionado(
            texto=tag.texto,
            tamanho=tag.tamanho,
            coordenada=tag.coordenada,
            posicao=tag.posicao,
        )
        for tag in tags
    ]

    layout = pf.Component(nome)
    moldura = pf.Path((-LIMITE_UM, -LIMITE_UM), width=LARGURA_MOLDURA_UM)
    moldura.segment(
        [
            (LIMITE_UM, -LIMITE_UM),
            (LIMITE_UM, LIMITE_UM),
            (-LIMITE_UM, LIMITE_UM),
            (-LIMITE_UM, -LIMITE_UM),
        ]
    )
    layout.add(CAMADA_MOLDURA, moldura)
    for texto in textos:
        layout.add_reference(texto)
    return layout, textos


def exportar_gds(layout: pf.Component, destino: Path) -> pf.Component:
    """Grava o GDS sem a moldura e com rótulos vazios nos cantos do quadrado."""
    layout_gds = layout.copy()
    layout_gds.filter_layers([CAMADA_MOLDURA], keep=False)
    layout_gds.add(
        CAMADA_TEXTO,
        pf.Label("", origin=(-LIMITE_UM, -LIMITE_UM)),
        pf.Label("", origin=(LIMITE_UM, LIMITE_UM)),
    )
    pf.write_layout(destino, layout_gds)

    conferido = pf.load_layout(destino, technology=tech)[layout_gds.name]
    if conferido.get_structures(layer=CAMADA_MOLDURA):
        raise RuntimeError(f"a moldura permanece em {destino}")
    limites_si = conferido.bounds(layers=[CAMADA_SILICIO])
    if limites_si is None:
        raise RuntimeError(f"o GDS {destino.name} não tem silício")
    return conferido


def _relatar(caminho: Path, tags: list[Tag], textos: list[pf.Component], destino: Path, conferido: pf.Component) -> None:
    print(caminho.name)
    for tag, texto in zip(tags, textos):
        kwargs = texto.parametric_kwargs
        x, y = _ancora_do_bloco(texto.bounds(), kwargs["posicao"])
        linhas = str(kwargs["texto"]).replace("\n", " / ")
        print(f"  {linhas}: {kwargs['posicao']} em ({x:.1f}, {y:.1f}) µm")
        if tag.rotulo:
            print(f"    {tag.rotulo}")
    print(destino.resolve())
    print("  bounds do GDS (µm):", conferido.bounds())
    print("  silício (µm):", conferido.bounds(layers=[CAMADA_SILICIO]))
    print("  camadas:", sorted(conferido.layers(include_dependencies=True)))


def gerar_gds(caminhos_csv: Iterable[str | Path]) -> list[Path]:
    """Cria um GDS para cada CSV, com o mesmo nome e na mesma pasta.

    ``caminhos_csv`` é o conjunto de caminhos dos arquivos de tags.
    """
    caminhos = sorted({Path(caminho).resolve() for caminho in caminhos_csv})
    if not caminhos:
        raise ValueError("nenhum CSV informado")

    destinos = []
    for caminho in caminhos:
        if caminho.suffix.lower() != ".csv":
            raise ValueError(f"esperado um arquivo CSV: {caminho}")
        if not caminho.is_file():
            raise FileNotFoundError(caminho)

        tags = ler_tags(caminho)
        layout, textos = montar_layout(tags, caminho.stem)
        destino = caminho.with_suffix(".gds")
        conferido = exportar_gds(layout, destino)
        _relatar(caminho, tags, textos, destino, conferido)
        destinos.append(destino)
    return destinos


def main() -> None:
    gerar_gds(ARQUIVOS_CSV)


if __name__ == "__main__":
    main()
