from __future__ import absolute_import

import ufl

from pyop2 import op2

import firedrake
from . import utils


__all__ = ["prolong", "restrict", "inject"]


def prolong(coarse, fine):
    cfs = coarse.function_space()
    hierarchy, lvl = utils.get_level(cfs)
    if hierarchy is None:
        raise RuntimeError("Coarse function not from hierarchy")
    if isinstance(hierarchy, firedrake.MixedFunctionSpaceHierarchy):
        for c, f in zip(coarse.split(), fine.split()):
            prolong(c, f)
        return
    op2.par_loop(hierarchy._prolong_kernel,
                 hierarchy._cell_sets[lvl],
                 fine.dat(op2.WRITE, hierarchy.cell_node_map(lvl)[op2.i[0]]),
                 coarse.dat(op2.READ, coarse.cell_node_map()))


def restrict(fine, coarse):
    cfs = coarse.function_space()
    hierarchy, lvl = utils.get_level(cfs)
    if hierarchy is None:
        raise RuntimeError("Coarse function not from hierarchy")
    if isinstance(hierarchy, firedrake.MixedFunctionSpaceHierarchy):
        for f, c in zip(fine.split(), coarse.split()):
            restrict(f, c)
        return

    weights = hierarchy._restriction_weights
    # We hit each fine dof more than once since we loop
    # elementwise over the coarse cells.  So we need a count of
    # how many times we did this to weight the final contribution
    # appropriately.
    if not hierarchy._discontinuous and weights is None:
        if isinstance(hierarchy.ufl_element(), (ufl.VectorElement,
                                                ufl.TensorProductVectorElement)):
            element = hierarchy.ufl_element().sub_elements()[0]
            restriction_fs = firedrake.FunctionSpaceHierarchy(hierarchy._mesh_hierarchy, element)
        else:
            restriction_fs = hierarchy
        weights = firedrake.FunctionHierarchy(restriction_fs)

        k = utils.get_count_kernel(hierarchy.cell_node_map(0).arity)

        # Count number of times each fine dof is hit
        for l in range(1, len(weights)):
            op2.par_loop(k, restriction_fs._cell_sets[l-1],
                         weights[l].dat(op2.INC, weights.cell_node_map(l-1)[op2.i[0]]))
            # Inverse, since we're using as weights not counts
            weights[l].assign(1.0/weights[l])
        hierarchy._restriction_weights = weights

    args = [coarse.dat(op2.INC, coarse.cell_node_map()[op2.i[0]]),
            fine.dat(op2.READ, hierarchy.cell_node_map(lvl))]

    if not hierarchy._discontinuous:
        weight = weights[lvl+1]
        args.append(weight.dat(op2.READ, hierarchy._restriction_weights.cell_node_map(lvl)))
    coarse.dat.zero()
    op2.par_loop(hierarchy._restrict_kernel, hierarchy._cell_sets[lvl],
                 *args)


def inject(fine, coarse):
    cfs = coarse.function_space()
    hierarchy, lvl = utils.get_level(cfs)
    if hierarchy is None:
        raise RuntimeError("Coarse function not from hierarchy")
    if isinstance(hierarchy, firedrake.MixedFunctionSpaceHierarchy):
        for f, c in zip(fine.split(), coarse.split()):
            inject(f, c)
        return
    op2.par_loop(hierarchy._inject_kernel, hierarchy._cell_sets[lvl],
                 coarse.dat(op2.WRITE, coarse.cell_node_map()[op2.i[0]]),
                 fine.dat(op2.READ, hierarchy.cell_node_map(lvl)))
