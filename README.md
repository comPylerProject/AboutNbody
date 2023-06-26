<h3 align="center">
How much faster is PyPy than CPython: a simple study on <em>nbody</em>
</h3>

---

Using the *nbody* benchmark provided by [*nbabel*](https://github.com/paugier/nbabel/blob/reply-zwart2020/py/bench_purepy_Particle.py), PyPy is hundreds of times faster than CPython. However, according to the code provided by [*pyperformace*](https://github.com/python/pyperformance/blob/1.0.6/pyperformance/data-files/benchmarks/bm_nbody/run_benchmark.py) (which originates from the [Computer Language Benchmarks Game](https://benchmarksgame-team.pages.debian.net/benchmarksgame/program/nbody-python3-1.html) project), we measured that PyPy is just 12.8 times faster than CPython. What causes this difference? The following text will conduct a simple study on this issue.

---





# The N-body problem

In physics, the N-body problem is the problem of predicting the individual motions of a group of celestial objects interacting with each other gravitationally. Since analytical solutions do not exist for $N\geq3$, numerical integration is applied. The simple principle is as follows.

1. Update the position of each body based on its velocity.
2. Using the law of universal gravitation, calculate the acceleration based on the position.
3. Update the velocity of each body based on the acceleration.
4. Repeat the above procedures.

The input to the problem is the masses, initial positions, and initial velocities of $N$ objects. The result is their state after time $T$. Given the time interval for each step, the complexity of the problem is $O(N^2T)$, because it is necessary to calculate the acceleration generated between every two of the $N$ bodies.





# Different code, different results

In this section, we start from the code provided by *nbabel*, and compare the the running time consumption of PyPy and CPython after altering the design pattern or some details. Ultimately, the result is close to that of *pyperformance*. 



## Version A: *nbabel*'s implementation

Let's run this benchmark using PyPy:

``` 
pypy3 nbody-A.py ./data/input256 10
```

The source file [nbody-A.py](nbody-A.py) in this repository is identical to the code implemented by [*nbabel*](https://github.com/paugier/nbabel/blob/reply-zwart2020/py/bench_purepy_Particle.py). Here `./data/input256` is the file path to the input data (there are also other input data available under the [data/](data/) directory), which contains the initial state of 256 bodies. The second argument `10` means $T=10$. The code fixes the time of each evolution step as 0.001, so there are a total of 10000 steps.



Then, run it using CPython (we use CPython 3.10):

```
python3.10 nbody-A.py ./data/input256 10
```

Is it quite slow? Yes, it is. If you don't want to wait too long, you can replace `10` with a smaller number, and remember to multiply the corresponding coefficient when calculating the time consumption in the end, as the amount of computation is proportional to $T$.



Our result on Intel(R) Xeon(R) Gold 6226R CPU:

| PyPy's time consumption | CPython's consumption | speedup |
| ----------------------- | --------------------- | ------- |
| 4.6s                    | 1488.6s               | 325.0   |



## Version B: minor modifications change a lot

Using [nbody-B.py](nbody-B.py) for measurements again, our results are as follows:

| PyPy's time consumption | CPython's consumption | speedup |
| ----------------------- | --------------------- | ------- |
| 8.4s                    | 672.0s                | 80.1    |

PyPy got slower, while CPython got faster, and all of this is just because we added a few minor modifications.

- First we added `__slot__` to `Point3D` and `Particle` classes, which can make attribute access more efficient (for both PyPy and CPython).
- Then we commented a few lines to changed the `position`, `velocity`, `acceleration`, and `acceleration1` into normal attributes of `Particle`, because *nbabel* implemented a trick with the property mechanism to improve PyPy's attribute access speed, but it makes CPython much slower.

```diff
@@ -5,8 +5,10 @@
 from datetime import timedelta
 
 
 class Point3D:
+    __slots__ = ('x', 'y', 'z')
+
     def __init__(self, x, y, z):
         self.x = x
         self.y = y
         self.z = z
@@ -64,13 +66,14 @@
 class Particle:
     """
     A Particle has mass, position, velocity and acceleration.
     """
+    __slots__ = ('mass', 'position', 'velocity', 'acceleration', 'acceleration1')
 
-    position = make_inlined_point("position")
-    velocity = make_inlined_point("velocity")
-    acceleration = make_inlined_point("acceleration")
-    acceleration1 = make_inlined_point("acceleration1")
+    # position = make_inlined_point("position")
+    # velocity = make_inlined_point("velocity")
+    # acceleration = make_inlined_point("acceleration")
+    # acceleration1 = make_inlined_point("acceleration1")
 
     def __init__(self, mass, x, y, z, vx, vy, vz):
         self.mass = mass
         self.position = Point3D(x, y, z)
```



## Version C: efficient for both CPython and PyPy

Can we implement a piece of code ourselves that runs faster both with PyPy and CPython? Yes, it is [nbody-C.py](nbody-C.py). Compared to nbody-A.py, it runs significantly faster with CPython. When using PyPy, its improvement is insignificant, but at least, it's not worse.

| PyPy's time consumption | CPython's consumption | speedup |
| ----------------------- | --------------------- | ------- |
| 4.5s                    | 218.3s                | 48.1    |

As for what we did, a rough summary is as follows.

- We removed the `Point3D` class, and embed the three components of velocity and acceleration in the `Particle` class directly, thus reducing the overhead by turning the double attribute access into a single access.
- Accordingly, when performing vector calculations, we manually operate on the three components, which also eliminates the function call overhead caused by the overloaded operators of custom types.
- When calculating squares, use `x*x` instead of `x**2`. We found that when `x` is a float number, PyPy will automatically optimize `x**2` into `x*x`, while CPython will honestly perform the exponentiation operations. Changing `x**2` in Python code to `x*x`, PyPy will keep its speed, while CPython will be faster.

`Point3D` encapsulates a three-dimensional vector. It does make the code more elegant, but it is too heavy for the N-body problem. In fact, nbody-C.py is not only more efficient than nbody-A.py, but also shorter.



## Version D: another minor modification with big impact

When calculating the acceleration between any pair of bodies, we need to calculate the distance cubed. Technically, it is always necessary to first calculate the distance squared using the Pythagorean theorem, but then there is some disagreement between *nbabel* and *pyperformance* on how to solve the distance cubed. *nbabel*'s method is to compute the root of the squared result and then multiply the two, while *pyperformance*'s way is to directly raise the squared result to the power of 1.5. We tried to introduce *pyperformance*'s approach into our implementation, or in other words, we applied the following modification to nbody-C.py and implemented [nbody-D.py](nbody-D.py).

```diff
-                distance_square = dx * dx + dy * dy + dz * dz
-                distance_cube = distance_square * sqrt(distance_square)
+                distance_cube = (dx * dx + dy * dy + dz * dz) ** 1.5
```

The two approaches are equivalent in a purely mathematical sense. Intuitively speaking, there is no essential difference, and this modification only involves two lines of code. However,  it ends up having a particularly large impact on PyPy's time consumption.

| PyPy's time consumption | CPython's consumption | speedup |
| ----------------------- | --------------------- | ------- |
| 13.4s                   | 219.1s                | 16.3    |

We found that `sqrt(x)` runs faster than `x**0.5` for both PyPy and CPython. The former is a square root calculation, which is more efficiently supported by both the interpreter and hardware, while the latter is treated as a regular exponentiation calculation. For PyPy, the speed difference is significant, but for CPython, the difference is unremarkable, and is almost offset by the overhead of one extra multiplication. In other words, PyPy optimizes `sqrt(x)` better than `x**0.5` (or `x**1.5`)

We guess that the authors of *nbabel* may have realized this, thus opting for the `sqrt` approach, whereas the author of *pyperformance* may have chosen to compute 1.5th power for the sake of simplicity.



## Version E: use tuple instead of class

*nbabel* defines a custom class `Particle` to encapsulate the state of each particle, while *pyperformance* directly uses `tuple`. We modified nbody-D.py and implemented [nbody-E.py](nbody-E.py), where the key changes are as follows.

```diff
不值得注意-class Particle:
-    __slots__ = ('mass', 'px', 'py', 'pz', 'vx', 'vy', 'vz', 'ax', 'ay', 'az', 'oax', 'oay', 'oaz')
-
-    def __init__(self, mass, x, y, z, vx, vy, vz):
-        self.mass = mass
-        self.px, self.py, self.pz = x, y, z
-        self.vx, self.vy, self.vz = vx, vy, vz
-        self.ax, self.ay, self.az = 0.0, 0.0, 0.0
-        self.oax, self.oay, self.oaz = 0.0, 0.0, 0.0
+def Particle(mass, px, py, pz, vx, vy, vz):
+    return (mass, [px, py, pz], [vx, vy, vz], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
```

PyPy got slower and CPython got faster, but not by much.

| PyPy's time consumption | CPython's consumption | speedup |
| ----------------------- | --------------------- | ------- |
| 14.6s                   | 207.8s                | 14.2    |

Now, the speedup is very close to the result of *pyperformance* (i.e., 12.8). As for the slight remaining difference, we discovered that it was mainly due to the difference in data scale, as the input data in *pyperformance* consists of $N=5$ bodies. In addition, there are some differences in code details here and there.

In fact, there exists another difference between *nbabel* and *pyperformance*: the former is based on [the leapfrog method](https://en.wikipedia.org/wiki/Leapfrog_integration) while the latter relies on [the Euler method](https://en.wikipedia.org/wiki/Euler_method). Therefore, although they are all solving N-body problems, strictly speaking, their computational tasks are not completely equivalent. This does not affect the speedup of the result much, but in *pyperformance*'s task, there's no need to store the acceleration vector, which explains why it use `tuple` to store the state of each particle.





# Summary

| version | PyPy's time consumption | CPython's consumption | speedup |
| ------- | ----------------------- | --------------------- | ------- |
| A       | 4.6s                    | 1488.6s               | 325.0   |
| B       | 8.4s                    | 672.0s                | 80.1    |
| C       | 4.5s                    | 218.3s                | 48.1    |
| D       | 13.4s                   | 219.1s                | 16.3    |
| E       | 14.6s                   | 207.8s                | 14.2    |

**C** is the most efficient implementation, and if we regard it as the base point, *nbabel* and *pyperformance* diverge in different directions as they prefer different grammars.

- **B** makes heavier use of object-oriented syntax, resulting in increased overhead for attribute access and function call (especially for CPython). Subsequently, **A** (i.e., *nbabel*) introduces some tricks to accelerate attribute access for PyPy, but with side effects for CPython.
- By replacing `x*sqrt(x)` with `x**1.5`, we obtain **D**, where the optimization effect of PyPy is reduced. Additionally, using `tuple` to store the state of each particle instead of `class`, **E** brings the results closer to *pyperformance*.

In fact, two other benchmarks in *pyperformance*, [*richards*](https://github.com/python/pyperformance/blob/1.0.6/pyperformance/data-files/benchmarks/bm_richards/run_benchmark.py) and [*raytrace*](https://github.com/python/pyperformance/blob/1.0.6/pyperformance/data-files/benchmarks/bm_raytrace/run_benchmark.py), emphasize the use of object-oriented syntax, and PyPy does achieve higher speedups on them. To some extent, they make up for the regret that *nbody* in pyperformance does not use object-oriented syntax.





# How about GraalPy

| version | GraalPy's time consumption | speedup |
| ------- | -------------------------- | ------- |
| A       | 522.9                      | 2.8     |
| B       | 58.6                       | 11.5    |
| C       | 12.6                       | 17.3    |
| D       | 23.8                       | 9.2     |
| E       | 27.6                       | 7.5     |

We also use GraalPy to implement the same experiment, and the results are shown in the table above. From **C** to **D** to **E**, the change trend of GraalPy is similar to that of PyPy, but from **C** to **B** to **A**, they are the opposite. This is easy to explain, different Python implementations are good at handling different language features.
