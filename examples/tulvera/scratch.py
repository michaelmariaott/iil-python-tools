from sardine import *
import taichi as ti
import tulvera as tul
import numpy as np

ti.init(arch=ti.vulkan)
x=1920
y=1080
n=1024
c.bpm = 250
c.link()
world = tul.World(x, y, n)
# window = ti.ui.Window("World", (x, y))
# canvas = window.get_canvas()

@swim
def gui_loop(d=0.5, i=0):
    world.process()
    # world.canvas.set_image(world.boids.world.to_numpy()[0])
    world.window.show()
    a(gui_loop, d=1/16, i=i+1)

# world.pause()
# world.play()
# world.reset()
# world.speed()

# world.draw('Boids', 'draw', x, y)
# world.draw('Noise', 'draw', x, y)
# world.draw('All',   'draw', x, y)

# # allocating on the fly?

