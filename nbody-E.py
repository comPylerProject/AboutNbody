import sys
from itertools import combinations
from math import sqrt
from time import perf_counter
from datetime import timedelta


def Particle(mass, px, py, pz, vx, vy, vz):
    return (mass, [px, py, pz], [vx, vy, vz], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])


class Cluster(list):
    def get_energy(self):
        ke = 0.0
        for (mass, r, (vx, vy, vz), _, _) in self:
            ke += 0.5 * mass * (vx * vx + vy * vy + vz * vz)
        pe = 0.0
        for (mass1, (px1, py1, pz1), _, _, _), (mass2, (px2, py2, pz2), _, _, _) in combinations(self, 2):
            dx = px1 - px2
            dy = py1 - py2
            dz = pz1 - pz2
            pe -= (mass1 * mass2) / sqrt(dx * dx + dy * dy + dz * dz)
        return ke + pe

    def step(self, dt):
        half_dt_square = 0.5 * dt * dt
        for _, r, (vx, vy, vz), (ax, ay, az), _ in self:
            r[0] += dt * vx + half_dt_square * ax
            r[1] += dt * vy + half_dt_square * ay
            r[2] += dt * vz + half_dt_square * az
        self.accelerate()
        half_dt = 0.5 * dt
        for _, _, v, (ax, ay, az), (oax, oay, oaz) in self:
            v[0] += half_dt * (ax + oax)
            v[1] += half_dt * (ay + oay)
            v[2] += half_dt * (az + oaz)

    def accelerate(self):
        for _, _, _, a, oa in self:
            oa[0], oa[1], oa[2] = a
            a[0], a[1], a[2] = 0.0, 0.0, 0.0

        nb_particules = len(self)
        for i, (mass1, (px1, py1, pz1), _, a1, _) in enumerate(self):
            for i in range(i + 1, nb_particules):
                (mass2, (px2, py2, pz2), _, a2, _) = self[i]
                dx = px1 - px2
                dy = py1 - py2
                dz = pz1 - pz2
                distance_cube = (dx * dx + dy * dy + dz * dz) ** 1.5
                tmp = mass2 / distance_cube
                a1[0] -= tmp * dx
                a1[1] -= tmp * dy
                a1[2] -= tmp * dz
                tmp = mass1 / distance_cube
                a2[0] += tmp * dx
                a2[1] += tmp * dy
                a2[2] += tmp * dz


if __name__ == "__main__":

    t_start = perf_counter()

    try:
        time_end = float(sys.argv[2])
    except IndexError:
        time_end = 10.

    time_step = 0.001
    cluster = Cluster()
    with open(sys.argv[1]) as input_file:
        for line in input_file:
            try:
                cluster.append(Particle(*[float(x) for x in line.split()[1:]]))
            except TypeError:
                pass

    old_energy = energy0 = energy = -0.25
    cluster.accelerate()
    for step in range(1, int(time_end / time_step + 1)):
        cluster.step(time_step)
        if not step % 100:
            energy = cluster.get_energy()
            print(
                f"t = {time_step * step:.2f}, E = {energy:.10f}, "
                f"dE/E = {(energy - old_energy) / old_energy:.10f}"
            )
            old_energy = energy
    print(f"Final dE/E = {(energy - energy0) / energy0:.6e}")

    print(f"run in {timedelta(seconds=perf_counter()-t_start)}")
