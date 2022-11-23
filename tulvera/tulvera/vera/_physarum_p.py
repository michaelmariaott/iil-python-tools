import numpy as np
import taichi as ti

from ._particle import Particles

@ti.data_oriented
class PhysarumP(Particles):
    def __init__(self,
                 x=1024,
                 y=1024,
                 n=1024,
                 sense_angle=0.20 * np.pi,
                 sense_dist=4.0,
                 evaporation=0.97,
                 move_angle=0.1 * np.pi,
                 move_step=2.0,
                 substep=8):
        super().__init__(x, y, n)
        self._ang = ti.field(dtype=ti.f32, shape=(self._n))
        self._i = 0
        self.world = ti.field(dtype=ti.f32, shape=(1, self._x, self._y))
        # self.world = ti.Vector.field(1, dtype=ti.f32, shape=(self._x, self._y))
        self.sense_angle = ti.field(ti.f32, ())
        self.sense_dist  = ti.field(ti.f32, ())
        self.evaporation = ti.field(ti.f32, ())
        self.move_angle  = ti.field(ti.f32, ())
        self.move_step   = ti.field(ti.f32, ())
        self.substep     = ti.field(ti.i32, ())
        self.sense_angle[None] = sense_angle
        self.sense_dist[None]  = sense_dist
        self.evaporation[None] = evaporation
        self.move_angle[None]  = move_angle
        self.move_step[None]   = move_step
        self.substep[None]     = substep
        self.randomise()

    @ti.kernel
    def randomise(self):
        for i in self._pos:
            self._pos[i] = ti.Vector([ti.random()*self._x, ti.random()*self._y])
            self._ang[i] = ti.random() * np.pi * 2.0

    @ti.func
    def sense(self, pos, ang):
        p = pos + ti.Vector([ti.cos(ang), ti.sin(ang)]) * self.sense_dist[None]
        px = ti.cast(p[0], ti.i32) % self._x
        py = ti.cast(p[1], ti.i32) % self._y
        return self.world[0, px, py]

    @ti.func
    def move(self):
        for i in self._pos:
            pos, ang = self._pos[i], self._ang[i]
            l = self.sense(pos, ang - self.sense_angle[None])
            c = self.sense(pos, ang)
            r = self.sense(pos, ang + self.sense_angle[None])
            if l < c < r:
                ang += self.move_angle[None]
            elif l > c > r:
                ang -= self.move_angle[None]
            elif c < l and c < r:
                ang += self.move_angle[None] * (2 * (ti.random() < 0.5) - 1)
            pos += ti.Vector([ti.cos(ang), ti.sin(ang)]) * self.move_step[None]
            self._pos[i], self._ang[i] = pos, ang

    @ti.func
    def deposit(self):
        for i in self._pos:
            ipos = self._pos[i].cast(int)
            iposx = ti.cast(ipos[0], ti.i32) % self._x
            iposy = ti.cast(ipos[1], ti.i32) % self._y
            self.world[0, iposx, iposy] += 1.0

    @ti.func
    def diffuse(self):
        for i, j in ti.ndrange(self._x, self._y):
            a = 0.0
            for di in ti.static(range(-1, 2)):
                for dj in ti.static(range(-1, 2)):
                    a += self.world[0, (i + di) % self._x, (j + dj) % self._y]
            a *= self.evaporation[None] / 9.0
            self.world[0, i, j] = a

    @ti.kernel
    def step(self):
        self.move()
        self.deposit()
        self.diffuse()

    def process(self):
        for _ in range(int(self.substep[None])):
            self.step()
            self._i += 1

# `jurigged -v tulvera/tulvera/vera/_physarum.py`
def update(p):
    pass
    # p.sense_angle[None] = 0.2 * np.pi

def main():
    ti.init(arch=ti.vulkan)
    x = 1920
    y = 1080
    n = 2048
    physarum = PhysarumP(x, y, n)
    physarum.pause = False
    world = ti.Vector.field(3, dtype=ti.i32, shape=(x, y))
    window = ti.ui.Window("Physarum", (x, y))
    canvas = window.get_canvas()
    while window.running:
        physarum.process()
        # update(physarum) # jurigged
        canvas.set_image(physarum.world.to_numpy()[0])
        window.show()

if __name__ == '__main__':
    main()
