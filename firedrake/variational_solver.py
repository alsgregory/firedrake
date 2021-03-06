from __future__ import absolute_import
import weakref
import ufl

from pyop2.profiling import timed_function, profile

from firedrake import solving_utils
from firedrake import ufl_expr
from firedrake.petsc import PETSc


__all__ = ["LinearVariationalProblem",
           "LinearVariationalSolver",
           "NonlinearVariationalProblem",
           "NonlinearVariationalSolver"]


class NonlinearVariationalProblem(object):
    """Nonlinear variational problem F(u; v) = 0."""

    def __init__(self, F, u, bcs=None, J=None,
                 Jp=None,
                 form_compiler_parameters=None,
                 nest=None):
        """
        :param F: the nonlinear form
        :param u: the :class:`.Function` to solve for
        :param bcs: the boundary conditions (optional)
        :param J: the Jacobian J = dF/du (optional)
        :param Jp: a form used for preconditioning the linear system,
                 optional, if not supplied then the Jacobian itself
                 will be used.
        :param dict form_compiler_parameters: parameters to pass to the form
            compiler (optional)
        :param nest: indicate if matrices on mixed spaces should be
               built as monolithic operators (suitable for direct
               solves), or as nested blocks (suitable for fieldsplit
               preconditioning).  If not provided, uses the default
               given by :data:`parameters["matnest"]`.
        """
        from firedrake import solving

        # Extract and check arguments
        u = solving._extract_u(u)
        bcs = solving._extract_bcs(bcs)

        # Store input UFL forms and solution Function
        self.F = F
        # Use the user-provided Jacobian. If none is provided, derive
        # the Jacobian from the residual.
        self.J = J or ufl_expr.derivative(F, u)
        self.Jp = Jp
        self.u = u
        self.bcs = bcs

        self._nest = nest
        # Store form compiler parameters
        self.form_compiler_parameters = form_compiler_parameters
        self._constant_jacobian = False

    @property
    def dm(self):
        return self.u.function_space()._dm


class NonlinearVariationalSolver(object):
    """Solves a :class:`NonlinearVariationalProblem`."""

    _id = 0

    def __init__(self, problem, **kwargs):
        """
        :arg problem: A :class:`NonlinearVariationalProblem` to solve.
        :kwarg nullspace: an optional :class:`.VectorSpaceBasis` (or
               :class:`.MixedVectorSpaceBasis`) spanning the null
               space of the operator.
        :kwarg solver_parameters: Solver parameters to pass to PETSc.
            This should be a dict mapping PETSc options to values.  For
            example, to set the nonlinear solver type to just use a linear
            solver:
        :kwarg options_prefix: an optional prefix used to distinguish
               PETSc options.  If not provided a unique prefix will be
               created.  Use this option if you want to pass options
               to the solver from the command line in addition to
               through the :data:`solver_parameters` dict.

        .. code-block:: python

            {'snes_type': 'ksponly'}

        PETSc flag options should be specified with `bool` values. For example:

        .. code-block:: python

            {'snes_monitor': True}
        """
        parameters, nullspace, options_prefix = solving_utils._extract_kwargs(**kwargs)

        # Do this first so __del__ doesn't barf horribly if we get an
        # error in __init__
        if options_prefix is not None:
            self._opt_prefix = options_prefix
            self._auto_prefix = False
        else:
            self._opt_prefix = 'firedrake_snes_%d_' % NonlinearVariationalSolver._id
            self._auto_prefix = True
            NonlinearVariationalSolver._id += 1

        assert isinstance(problem, NonlinearVariationalProblem)

        ctx = solving_utils._SNESContext(problem)

        self.snes = PETSc.SNES().create()

        self.snes.setOptionsPrefix(self._opt_prefix)

        # Mixed problem, use jacobi pc if user has not supplied one.
        if ctx.is_mixed:
            parameters.setdefault('pc_type', 'jacobi')

        # Allow command-line arguments to override dict parameters
        opts = PETSc.Options()
        for k, v in opts.getAll().iteritems():
            if k.startswith(self._opt_prefix):
                parameters[k[len(self._opt_prefix):]] = v

        self._problem = problem

        self._ctx = ctx
        self.snes.setDM(problem.dm)

        ctx.set_function(self.snes)
        ctx.set_jacobian(self.snes)
        ctx.set_nullspace(nullspace, problem.J.arguments()[0].function_space()._ises)

        self.parameters = parameters

    def __del__(self):
        # Remove stuff from the options database
        # It's fixed size, so if we don't it gets too big.
        if self._auto_prefix and hasattr(self, '_opt_prefix'):
            opts = PETSc.Options()
            for k in self.parameters.iterkeys():
                del opts[self._opt_prefix + k]
            delattr(self, '_opt_prefix')

    @property
    def parameters(self):
        return self._parameters

    @parameters.setter
    def parameters(self, val):
        assert isinstance(val, dict), 'Must pass a dict to set parameters'
        self._parameters = val
        solving_utils.update_parameters(self, self.snes)

    @timed_function("SNES solver execution")
    @profile
    def solve(self):
        dm = self.snes.getDM()
        dm.setAppCtx(weakref.proxy(self._ctx))
        dm.setCreateMatrix(self._ctx.create_matrix)

        # Apply the boundary conditions to the initial guess.
        for bc in self._problem.bcs:
            bc.apply(self._problem.u)

        # User might have updated parameters dict before calling
        # solve, ensure these are passed through to the snes.
        solving_utils.update_parameters(self, self.snes)

        with self._problem.u.dat.vec as v:
            self.snes.solve(None, v)

        solving_utils.check_snes_convergence(self.snes)


class LinearVariationalProblem(NonlinearVariationalProblem):
    """Linear variational problem a(u, v) = L(v)."""

    def __init__(self, a, L, u, bcs=None, aP=None,
                 form_compiler_parameters=None,
                 nest=None,
                 constant_jacobian=True):
        """
        :param a: the bilinear form
        :param L: the linear form
        :param u: the :class:`.Function` to solve for
        :param bcs: the boundary conditions (optional)
        :param aP: an optional operator to assemble to precondition
                 the system (if not provided a preconditioner may be
                 computed from ``a``)
        :param dict form_compiler_parameters: parameters to pass to the form
            compiler (optional)
        :param nest: indicate if matrices on mixed spaces should be
               built as monolithic operators (suitable for direct
               solves), or as nested blocks (suitable for fieldsplit
               preconditioning).  If not provided, uses the default
               given by :data:`parameters["matnest"]`.
        :param constant_jacobian: (optional) flag indicating that the
                 Jacobian is constant (i.e. does not depend on
                 varying fields).  If your Jacobian can change, set
                 this flag to :data:`False`.
        """

        # In the linear case, the Jacobian is the equation LHS.
        J = a
        F = ufl.action(J, u) - L

        super(LinearVariationalProblem, self).__init__(F, u, bcs, J, aP,
                                                       form_compiler_parameters=form_compiler_parameters, nest=nest)
        self._constant_jacobian = constant_jacobian


class LinearVariationalSolver(NonlinearVariationalSolver):
    """Solves a :class:`LinearVariationalProblem`."""

    def __init__(self, *args, **kwargs):
        """
        :arg problem: A :class:`LinearVariationalProblem` to solve.
        :kwarg solver_parameters: Solver parameters to pass to PETSc.
            This should be a dict mapping PETSc options to values.
        :kwarg nullspace: an optional :class:`.VectorSpaceBasis` (or
               :class:`.MixedVectorSpaceBasis`) spanning the null
               space of the operator.
        :kwarg options_prefix: an optional prefix used to distinguish
               PETSc options.  If not provided a unique prefix will be
               created.  Use this option if you want to pass options
               to the solver from the command line in addition to
               through the :data:`solver_parameters` dict.
        """
        super(LinearVariationalSolver, self).__init__(*args, **kwargs)

        self.parameters.setdefault('snes_type', 'ksponly')
        self.parameters.setdefault('ksp_rtol', 1.0e-7)
        solving_utils.update_parameters(self, self.snes)
