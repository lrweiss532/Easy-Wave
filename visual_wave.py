from easy_wave import AWG_Writer, REAL_CHANNELS
from wave_library import Empty
import pyqtgraph as pg
def plot_wave(wave, plot_zeros=True, downsample=10, downsample_mode='peak'):
    win = pg.GraphicsWindow()
    cs = lambda ch: ['y','b','#FF00FF','g'][ch.value[0]-1]
    plt = win.addPlot()
    plt.hideAxis('left')

    # Optimize for large data
    plt.setClipToView(True)
    if downsample:
        plt.setDownsampling(ds=downsample, auto=True, mode=downsample_mode)

    dy = 0
    offset=3
    for i,ch in enumerate(REAL_CHANNELS):
        if ch in wave.chs or plot_zeros:
            ts, ys = wave.generate(1e9, ch)
            ys = ys.astype(float) + dy
            plt.plot(ts, ys, pen=cs(ch), fillLevel = dy, brush=(50,50,200,100))
            dy -= offset
            if plot_zeros and (i+1)%3==0:
                dy-=1
    
    #Set to zooming limit
    plt.vb.setLimits(yMax=1.5, yMin=dy, xMin=0, xMax=wave.t)
                
    # Add crosshair
    label = pg.TextItem("t=0.000 us", anchor=(0,0))

    vLine = pg.InfiniteLine(angle=90, movable=False)
    plt.addItem(vLine)
    label.setParentItem(plt)
    def mouseMoved(pos):
        if plt.sceneBoundingRect().contains(pos):
            mousePoint = plt.vb.mapSceneToView(pos)
            if 0<mousePoint.x()<wave.t:
                label.setText("t={:.3f} us".format(mousePoint.x()*1e6))
                vLine.setPos(mousePoint.x())
#     proxy = pg.SignalProxy(plt_item.scene().sigMouseMoved, rateLimit=60, slot=mouseMoved)
    plt.scene().sigMouseMoved.connect(mouseMoved)
    
    return win

def plot_line(writer, line, plot_zeros=True, downsample=10, downsample_mode='peak'):
    wave = writer.lines[line-1]['waveform']
    return plot_wave(wave, plot_zeros=plot_zeros, downsample=downsample, downsample_mode=downsample_mode)

def plot_block(writer, block, plot_zeros=True, downsample=10, downsample_mode='peak'):
    if type(block) == int:
        block_name = list(writer.blocks.keys())[block]
    elif type(block) == str:
        block_name = block
    else:
        raise Exception("Unrecongnize type for <block> to be plotted")
    b = writer.blocks[block_name]
    wave = Empty()
    for lname, line in b.items():
        wave += line['waveform']*line['repeat']
        
    return plot_wave(wave, plot_zeros=plot_zeros, downsample=downsample, downsample_mode=downsample_mode)