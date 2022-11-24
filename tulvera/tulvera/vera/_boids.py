# original: https://forum.taichi-lang.cn/t/homework0-boids/563/6

import taichi as ti
import numpy as np
import math

from tulvera.vera._particle import Particles

@ti.data_oriented
class Boids(Particles):
    def __init__(self,
                 x=1024,
                 y=1024,
                 n=1024,
                 separate=0.1,
                 align=1.0,
                 cohere=1.0,
                 dt=1,
                 radius=40.0,
                 speed=3.0):
        super().__init__(x, y, n)
        self._vel  = ti.Vector.field(2, dtype=ti.f32, shape=(self._n))
        # self.world = ti.Vector.field(3, dtype=ti.i32, shape=(self._x, self._y))
        self.world = ti.field(dtype=ti.f32, shape=(1, self._x, self._y))
        self.separate = ti.field(ti.f32, ())
        self.align    = ti.field(ti.f32, ())
        self.cohere   = ti.field(ti.f32, ())
        self.dt       = ti.field(ti.f32, ())
        self.radius   = ti.field(ti.f32, ())
        self.speed    = ti.field(ti.f32, ())
        self.separate[None] = separate
        self.align[None]    = align
        self.cohere[None]   = cohere
        self.dt[None]       = dt
        self.radius[None]   = radius
        self.speed[None]    = speed
        self.randomise()

    @ti.kernel
    def randomise(self):
        for x in range(0, self._n):
            self._pos[x] = ti.Vector([ti.random(ti.f32)*self._x, ti.random(ti.f32)*self._y])
            self._vel[x] = ti.Vector([self.speed[None]*(ti.random(ti.f32)-0.5), self.speed[None]*(ti.random(ti.f32)-0.5)])

    @ti.func
    def move(self):
        for x in range(self._n):
            self._pos[x] = self._pos[x] + self.dt[None] * self._vel[x];
            # TODO: abstract out walls vs wrap? re: membranes
            if (self._pos[x][0] > self._x): self._pos[x][0] = 1
            elif (self._pos[x][1] > self._y): self._pos[x][1] = 1
            elif (self._pos[x][0] < 0): self._pos[x][0] = self._x-1
            elif (self._pos[x][1] < 0): self._pos[x][1] = self._y-1

    @ti.func
    def step(self):
        for i in range(self._n):
            separate = ti.Vector([0.,0.])
            align    = ti.Vector([0.,0.])
            cohere   = ti.Vector([0.,0.])
            n = 0
            for j in range(self._n):
                if i!=j:
                    dis = self._pos[i] - self._pos[j]
                    dis_norm = dis.norm()
                    if dis_norm < self.radius[None]:
                        self._vel[i] += dis.normalized()/dis_norm*self.speed[None]
                        separate += (self._pos[i] - self._pos[j])
                        align    += self._vel[j]
                        cohere   += self._pos[j]
                        n += 1
            if n != 0:
                separate = separate/n * self.separate[None]
                align    = align/n * self.align[None]
                cohere   = (cohere/n - self._pos[i]) * self.cohere[None]
                self._vel[i] += (cohere + align).normalized()
                if self._vel[i].norm() > self.speed[None]:
                    self._vel[i] = self._vel[i].normalized()*self.speed[None]

    @ti.func
    def raster(self):
        rad = 2
        for i,j in ti.ndrange((0, self._x),(0, self._y)):
            # self.world[i, j] = ti.Vector([255,255,255])
            self.world[0, i, j] = 255
        for i in range(self._n):
            xi = ti.cast(self._pos[i][0], ti.i32) - rad
            xj = ti.cast(self._pos[i][0], ti.i32) + rad
            yi = ti.cast(self._pos[i][1], ti.i32) - rad
            yj = ti.cast(self._pos[i][1], ti.i32) + rad
            for x in range(xi, xj):
                for y in range(yi, yj):
                    # self.world[x, y] = ti.Vector([
                    #     255-ti.cast(self._vel[i][1]*255, ti.i32),
                    #     255-ti.cast(self._vel[i].norm()*255, ti.i32),
                    #     255-ti.cast(self._vel[i][0]*255, ti.i32)])
                    self.world[0, x, y] = 0#ti.cast(((3+self._vel[i][1])/6)*64, ti.i32)

    @ti.kernel
    def process(self):
        if self.pause == False:
            self.step()
            self.move()
            self.raster()

# `jurigged -v tulvera/tulvera/vera/_boids_p.py`
def update(b):
    # b.separate[None] = separate
    # b.align[None]    = align
    # b.cohere[None]   = cohere
    # b.dt[None]       = dt
    # b.radius[None]   = radius
    b.speed[None]    = 3.0

def main():
    ti.init(arch=ti.vulkan)
    x = 1920
    y = 1080
    n = 4096
    boids = Boids(x, y, n)
    boids.pause = False
    window = ti.ui.Window("Boids", (x, y))
    canvas = window.get_canvas()
    while window.running:
        boids.process()
        # update(boids) # jurigged: costs 10fps
        canvas.set_image(boids.world.to_numpy()[0])
        window.show()

if __name__ == '__main__':
    main()
