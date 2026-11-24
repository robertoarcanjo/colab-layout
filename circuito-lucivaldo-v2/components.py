from pathlib import Path
import gdsfactory as gf
from sympy import comp



folder =  str(Path(__file__).resolve().parent / "Components")
folder = r'C:\Users\luciv\Documents\Lucivaldo\R&D\Components'
gf.gpdk.PDK.activate()


@gf.cell
def wirebondingTemplate() -> gf.Component:
    filename = folder + '/Wirebonding_Template.gds'
    cellname = 'Wirebonding_Template'
    comp = gf.import_gds(filename, cellname=cellname)

    pad_width = 205.0      # extensão do pad na direção perpendicular à rota
    pad_length = 405.0     # extensão do pad na direção da rota
    n_pads_col = 22
    y0 = -4150.0
    pitch_y = 400.0
    x_left = -4600.0
    x_right = 4600.0

    port_id = 1

    for i in range(n_pads_col):
        y = y0 + i * pitch_y
        comp.add_port(
            name=f'e{port_id}',
            center=(x_left + pad_length / 2, y),
            width=pad_width,
            orientation=0,
            layer=(12, 0),
            port_type='electrical',
        )
        port_id += 1


    for i in range(n_pads_col):
        y = y0 + i * pitch_y
        comp.add_port(
            name=f'e{port_id}',
            center=(x_right - pad_length / 2, y),
            width=pad_width,
            orientation=180,
            layer=(12, 0),
            port_type='electrical',
        )
        port_id += 1

    return comp


@gf.cell
def wirebondingFiberBondingTemplate() -> gf.Component:
    filename = folder + '/Wirebonding_FiberBonding_Layout.gds'
    cellname = 'Wirebonding_FiberBonding_Layout'
    comp = gf.import_gds(filename, cellname=cellname)


    pad_width = 205.0
    pad_length = 405.0
    n_pads_col = 22
    y0 = -4150.0
    pitch_y = 400.0
    x_left = -4600.0
    x_right = 4600.0

    port_id = 1

    for i in range(n_pads_col):
        y = y0 + i * pitch_y
        comp.add_port(
            name=f'e{port_id}',
            center=(x_left + pad_length / 2, y),
            width=pad_width,
            orientation=0,
            layer=(12, 0),
            port_type='electrical',
        )
        port_id += 1

    for i in range(n_pads_col):
        y = y0 + i * pitch_y
        comp.add_port(
            name=f'e{port_id}',
            center=(x_right - pad_length / 2, y),
            width=pad_width,
            orientation=180,
            layer=(12, 0),
            port_type='electrical',
        )
        port_id += 1


    gc_width = 0.5
    gc_pitch = 250.0
    n_gc = 8
    x0_gc = -875.0
    y_bottom = -4331.42
    y_top = 4331.42

    port_id_o = 1
    for i in range(n_gc):
        x = x0_gc + i * gc_pitch
        comp.add_port(
            name=f'o{port_id_o}',
            center=(x, y_bottom),
            width=gc_width,
            orientation=90,
            layer=(1, 0),
            port_type='optical',
        )
        port_id_o += 1
    
    for i in range(n_gc):
        x = x0_gc + i * gc_pitch
        comp.add_port(
            name=f'o{port_id_o}',
            center=(x, y_top),
            width=gc_width,
            orientation=270,
            layer=(1, 0),
            port_type='optical',
        )
        port_id_o += 1

    ## y branches
    comp.add_port(name='o17', center=(-x0_gc + 3.5 - 0.75, y_top - 14.8), width=0.5, orientation=270, layer=(1, 0), port_type='optical') ## upper
    comp.add_port(name='o0', center=(-x0_gc+ 3.5 -0.75, y_bottom + 14.8), width=0.5, orientation=180, layer=(1, 0), port_type='optical') ## lower
    return comp

@gf.cell
def dc50_50() -> gf.Component:
    filename= folder + '/DirectionalCoupler_TE_5050.gds'
    cellname= 'DirectionalCoupler_TE_5050'

    comp = gf.import_gds(filename, cellname=cellname)
    
    comp.add_port(name='o1', center=(-11.45, 5.26 - 5.51/2), width=0.5, orientation=180, layer=(1,0), port_type='optical')
    comp.add_port(name='o2', center=(-11.45, 0.25- 5.51/2), width=0.5, orientation=180, layer=(1,0), port_type='optical')
    comp.add_port(name='o3', center=(11.45, 5.26- 5.51/2), width=0.5, orientation=0, layer=(1,0), port_type='optical')
    comp.add_port(name='o4', center=(11.45, 0.25- 5.51/2), width=0.5, orientation=0, layer=(1,0), port_type='optical')

    return comp


@gf.cell

def dc_adiabatic_TM() -> gf.Component:
    filename= folder + '/ebeam_adiabatic_tm1550.gds'
    cellname= 'ebeam_adiabatic_tm1550'

    comp = gf.import_gds(filename, cellname=cellname)

    comp.add_port(name='o1', center=(0.1, 1.5), width=0.5, orientation=180, layer=(1,0), port_type='optical')
    comp.add_port(name='o2', center=(0.1,-1.5), width=0.5, orientation=180, layer=(1,0), port_type='optical')
    comp.add_port(name='o3', center=(217.8, 1.5), width=0.5, orientation=0, layer=(1,0), port_type='optical')
    comp.add_port(name='o4', center=(217.8, -1.5), width=0.5, orientation=0, layer=(1,0), port_type='optical')

    return comp

@gf.cell
def gcTE8deg() -> gf.Component:
    filename= folder + '/GratingCoupler_TE_Oxide_8degrees.gds'
    cellname= 'GratingCoupler_TE_Oxide_8degrees'

    comp = gf.import_gds(filename, cellname=cellname)

    comp.add_port(name='o1', center=(0, 0.05), width=0.5, orientation=270, layer=(1,0), port_type='optical')

    return comp

@gf.cell
def gcEbeam() -> gf.Component:
    filename= folder + '/ebeam_gc_te1550.gds'
    cellname= 'ebeam_gc_te1550'

    comp = gf.import_gds(filename, cellname=cellname)

    comp.add_port(name='o1', center=(0, 0), width=0.5, orientation=0, layer=(1,0), port_type='optical')

    return comp
@gf.cell
def bragg(id,pd) -> gf.Component:

    filename = folder + f'/ebeam_bragg_te1550_{id}_{pd}.gds'
    cellname = f'ebeam_bragg_te1550_{id}_{pd}'

    comp = gf.import_gds(filename, cellname=cellname)
    pd = pd/1e3
    ## pd*id é o comprimento da grade pq id é o nmr de periodos
    comp.add_port(name='o1', center=(0, 0), width=0.5, orientation=180, layer=(1,0), port_type='optical')
    comp.add_port(name='o2', center=(pd*id, 0), width=0.5, orientation=0, layer=(1,0), port_type='optical')

    return comp

@gf.cell
def terminatorTE() -> gf.Component:
    filename= folder + '/ebeam_terminator_te1550.gds'
    cellname= 'ebeam_terminator_te1550'

    comp = gf.import_gds(filename, cellname=cellname)

    comp.add_port(name='o1', center=(0, 0), width=0.5, orientation=0, layer=(1,0), port_type='optical')

    return comp

@gf.cell
def yEbeam() -> gf.Component:
    filename = folder + '/ebeam_y_1550.gds'
    cellname = 'ebeam_y_1550'

    comp = gf.import_gds(filename, cellname=cellname)

    comp.add_port(name='o1', center=(-7.4,0), width=0.5, orientation=180, layer=(1,0), port_type='optical')
    comp.add_port(name='o2', center=(7.4, -2.75), width=0.5, orientation=0, layer=(1,0), port_type='optical')
    comp.add_port(name='o3', center=(7.4, 2.75), width=0.5, orientation=0, layer=(1,0), port_type='optical')

    return comp

@gf.cell
def phaseShifter() -> gf.Component:
    filename = folder + '/PhaseShifterTM_200microns.gds'
    cellname = 'PhaseShifterTM_200microns'

    comp = gf.import_gds(filename, cellname=cellname)

    pad_width = 80
    comp.add_port(name='o1', center=(0, 254.25), width=0.5, orientation=180, layer=(1, 0), port_type='optical')
    comp.add_port(name='o2', center=(0, 127.5), width=0.5, orientation=180, layer=(1,0), port_type='optical')
    comp.add_port(name='o3', center=(0, 0.25), width=0.5, orientation=180, layer=(1,0), port_type='optical')

    comp.add_port(
        name='e1',
        center=(837, 330.75 - pad_width / 2),
        width=pad_width,
        orientation=0,
        layer=(12, 0),
        port_type='electrical',
    )
    comp.add_port(
        name='e2',
        center=(837,230.75 - pad_width/2),
        width=pad_width,
        orientation=0,
        layer=(12, 0),
        port_type='electrical',
    )
    comp.add_port(
        name='e3',
        center=(837, 130.75 - pad_width / 2),
        width=pad_width,
        orientation=0,
        layer=(12, 0),
        port_type='electrical',
    )
    return comp


@gf.cell
def phaseShifter1000u() -> gf.Component:
    filename = folder + '/PhaseShifterTM_1000microns.gds'
    cellname = 'PhaseShifterTM_1000microns'

    comp = gf.import_gds(filename, cellname=cellname)

    pad_width = 86
    boxlength = 1640

    comp.add_port(name='o1', center=(0, 254.25), width=0.5, orientation=180, layer=(1, 0), port_type='optical')
    comp.add_port(name='o2', center=(0, 127.25), width=0.5, orientation=180, layer=(1,0), port_type='optical')
    comp.add_port(name='o3', center=(0, 0.25), width=0.5, orientation=180, layer=(1,0), port_type='optical')


    comp.add_port(
        name='e1',
        center=(boxlength - pad_width / 2, 333.75 ),
        width=pad_width,
        orientation=90,
        layer=(12, 0),
        port_type='electrical',
    )
    comp.add_port(
        name='e2',
        center=(boxlength,233.75 - pad_width/2),
        width=pad_width,
        orientation=0,
        layer=(12, 0),
        port_type='electrical',
    )
    comp.add_port(
        name='e3',
        center=(boxlength - pad_width / 2, 47.75),
        width=pad_width,
        orientation= 270,
        layer=(12, 0),
        port_type='electrical',
    )
    return comp


@gf.cell
def phaseShifter1000u2x2() -> gf.Component:
    filename = folder + '/PhaseShifterTM_1000microns_2x2.gds'
    cellname = 'PhaseShifterTM_1000microns_2x2'

    comp = gf.import_gds(filename, cellname=cellname)

    pad_width = 86
    boxlength = 1720

    comp.add_port(
        name='o1',
        center=(0, 254.25),
        width=0.5,
        orientation=180,
        layer=(1, 0),
        port_type='optical'
    )
    comp.add_port(
        name='o2',
        center=(0, 127.25),
        width=0.5,
        orientation=180,
        layer=(1, 0),
        port_type='optical'
    )
    comp.add_port(
        name='o3',
        center=(0, 0.25),
        width=0.5,
        orientation=180,
        layer=(1, 0),
        port_type='optical'
    )
    comp.add_port(
        name='o4',
        center=(0, 381.25),
        width=0.5,
        orientation=180,
        layer=(1, 0),
        port_type='optical')

    comp.add_port(
        name='e1',
        center=(boxlength  - pad_width / 2, 333.75),
        width=pad_width,
        orientation=90,
        layer=(12, 0),
        port_type='electrical',
    )
    comp.add_port(
        name='e2',
        center=(boxlength,233.75 - pad_width/2),
        width=pad_width,
        orientation=0,
        layer=(12, 0),
        port_type='electrical',
    )
    comp.add_port(
        name='e3',
        center=(boxlength - pad_width / 2, 47.75),
        width=pad_width,
        orientation=-90,
        layer=(12, 0),
        port_type='electrical',
    )
    return comp


@gf.cell
def phaseShifter1000u2x2_Erick(device) -> gf.Component:
    if device == 1:
        filename = folder + '/PhaseShifterTM_1000microns_2x2_Erick.gds'
        cellname = 'PhaseShifterTM_1000microns_2x2_Erick'
    else:
        filename = folder + '/PhaseShifterTM_1000microns_2x2_Erick2.gds'
        cellname = 'PhaseShifterTM_1000microns_2x2_Erick2'

    comp = gf.import_gds(filename, cellname=cellname)

    pad_width = 86
    boxlength = 1720

    comp.add_port(
        name='o1',
        center=(0, 254.25),
        width=0.5,
        orientation=180,
        layer=(1, 0),
        port_type='optical'
    )
    comp.add_port(
        name='o2',
        center=(0, 127.25),
        width=0.5,
        orientation=180,
        layer=(1, 0),
        port_type='optical'
    )
    comp.add_port(
        name='o3',
        center=(0, 0.25),
        width=0.5,
        orientation=180,
        layer=(1, 0),
        port_type='optical'
    )
    comp.add_port(
        name='o4',
        center=(0, 381.25),
        width=0.5,
        orientation=180,
        layer=(1, 0),
        port_type='optical')

    comp.add_port(
        name='e1',
        center=(boxlength  - pad_width / 2, 333.75),
        width=pad_width,
        orientation=90,
        layer=(12, 0),
        port_type='electrical',
    )
    comp.add_port(
        name='e2',
        center=(boxlength,233.75 - pad_width/2),
        width=pad_width,
        orientation=0,
        layer=(12, 0),
        port_type='electrical',
    )
    comp.add_port(
        name='e3',
        center=(boxlength - pad_width / 2, 47.75),
        width=pad_width,
        orientation=-90,
        layer=(12, 0),
        port_type='electrical',
    )
    return comp




def phaseShifter2x2() -> gf.Component:
    filename = folder + '/PhaseShifterTM_200microns_2x2.gds'
    cellname = 'PhaseShifterTM_200microns2x2'

    comp = gf.import_gds(filename, cellname=cellname)

    pad_width = 86
    comp.add_port(
        name='o1',
        center=(0, 254.25),
        width=0.5,
        orientation=180,
        layer=(1, 0),
        port_type='optical'
    )
    comp.add_port(
        name='o2',
        center=(0, 127.5),
        width=0.5,
        orientation=180,
        layer=(1,0),
        port_type='optical'
    )
    comp.add_port(
        name='o3',
        center=(0, 0.25),
        width=0.5,
        orientation=180,
        layer=(1,0),
        port_type='optical'
    )
    comp.add_port(
        name='o4',
        center=(0, 381.25),
        width=0.5,
        orientation=180,
        layer=(1, 0),
        port_type='optical')

    comp.add_port(
        name='e1',
        center=(837- pad_width / 2, 333.75 - pad_width / 2),
        width=pad_width,
        orientation=0,
        layer=(12, 0),
        port_type='electrical',
    )
    comp.add_port(
        name='e2',
        center=(837,230.75 - pad_width/2),
        width=pad_width,
        orientation=0,
        layer=(12, 0),
        port_type='electrical',
    )
    comp.add_port(
        name='e3',
        center=(837- pad_width / 2, 133.75 - pad_width / 2),
        width=pad_width,
        orientation=0,
        layer=(12, 0),
        port_type='electrical',
    )
    return comp